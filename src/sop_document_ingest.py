from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from src.class_registry import ClassRegistry

_STEP_TYPES = {"click", "drag", "validate_pins", "click_sequence", "type_text", "press_key", "wait_ms", "auth_sequence", "input_text", "mold_setup"}
_DOC_SUFFIXES = {".txt", ".md", ".pdf"}


@dataclass
class SOPAtom:
    id: str
    name: str
    type: str
    target: Optional[str] = None
    description: str = ""
    enabled: bool = True
    class_name: Optional[str] = None
    confidence: Optional[float] = None
    source_page: Optional[int] = None
    source_span: Optional[str] = None
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    raw_text: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_step(self) -> Dict[str, Any]:
        step: Dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "enabled": self.enabled,
        }
        if self.target:
            step["target"] = self.target
        if self.class_name:
            step["class_name"] = self.class_name
        if self.confidence is not None:
            step["confidence"] = round(float(self.confidence), 4)
        if self.source_page is not None:
            step["source_page"] = int(self.source_page)
        if self.source_span:
            step["source_span"] = self.source_span
        if self.preconditions:
            step["preconditions"] = list(self.preconditions)
        if self.postconditions:
            step["postconditions"] = list(self.postconditions)
        if self.raw_text:
            step["source_text"] = self.raw_text
        step.update(self.extra)
        return step


@dataclass
class SOPDocumentArtifact:
    version: str
    title: str
    source_path: str
    source_type: str
    raw_text: str
    steps: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "title": self.title,
            "source_path": self.source_path,
            "source_type": self.source_type,
            "raw_text": self.raw_text,
            "steps": self.steps,
            "metadata": self.metadata,
        }


class SOPDocumentIngestor:
    """Read PDF/TXT SOP files and atomize them into schema-ready JSON."""

    def __init__(self, llm: Any | None = None, ocr: Any | None = None) -> None:
        self._llm = llm
        self._ocr = ocr

    def ingest(self, source_path: str | Path) -> SOPDocumentArtifact:
        path = Path(source_path)
        if not path.exists():
            raise FileNotFoundError(f"SOP document not found: {path}")
        if path.suffix.lower() not in _DOC_SUFFIXES:
            raise ValueError(f"Unsupported SOP document type: {path.suffix}")

        source_type = path.suffix.lower().lstrip(".")
        raw_text = self._extract_text(path)
        registry = ClassRegistry.load()
        class_names = registry.class_names()

        if self._llm is not None and raw_text.strip():
            parsed = self._atomize_with_llm(path, raw_text, class_names)
        else:
            parsed = self._atomize_with_rules(raw_text, class_names)

        parsed = self._normalize_artifact(parsed, path, raw_text, source_type)
        self.validate_artifact(parsed)
        return parsed

    def export_json(self, artifact: SOPDocumentArtifact, destination: str | Path) -> Path:
        dest = Path(destination)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(
            json.dumps(artifact.to_json(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return dest

    def _extract_text(self, path: Path) -> str:
        if path.suffix.lower() == ".txt" or path.suffix.lower() == ".md":
            return path.read_text(encoding="utf-8", errors="replace")
        return self._extract_pdf_text(path)

    def _extract_pdf_text(self, path: Path) -> str:
        pages_text: List[str] = []
        try:
            from pypdf import PdfReader  # type: ignore[import]

            reader = PdfReader(str(path))
            for page in reader.pages:
                try:
                    pages_text.append(page.extract_text() or "")
                except Exception:
                    pages_text.append("")
        except Exception:
            pages_text = []

        text = "\n".join(t.strip() for t in pages_text if t and t.strip()).strip()
        if text:
            return text
        return self._ocr_pdf(path)

    def _ocr_pdf(self, path: Path) -> str:
        try:
            import fitz  # type: ignore[import]
        except Exception:
            return ""

        texts: List[str] = []
        doc = fitz.open(str(path))
        try:
            for page in doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                img_bytes = pix.tobytes("png")
                text = self._ocr_page_image(img_bytes)
                if text:
                    texts.append(text)
        finally:
            doc.close()
        return "\n".join(texts).strip()

    def _ocr_page_image(self, image_bytes: bytes) -> str:
        if self._ocr is not None:
            try:
                import cv2  # type: ignore[import]
                import numpy as np  # type: ignore[import]

                arr = np.frombuffer(image_bytes, dtype=np.uint8)
                bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if bgr is not None:
                    scan = getattr(self._ocr, "scan_all", None)
                    if callable(scan):
                        regions = scan(bgr)
                        merged = " ".join(
                            str(getattr(region, "text", "")).strip()
                            for region in regions
                            if str(getattr(region, "text", "")).strip()
                        )
                        if merged.strip():
                            return merged.strip()
            except Exception:
                pass

        try:
            from PIL import Image  # type: ignore[import]
            import pytesseract  # type: ignore[import]
            import io

            image = Image.open(io.BytesIO(image_bytes))
            return pytesseract.image_to_string(image).strip()
        except Exception:
            return ""

    def _atomize_with_llm(
        self, path: Path, raw_text: str, class_names: Sequence[str]
    ) -> Dict[str, Any]:
        system = (
            "You are an offline SOP atomization engine for a factory line. "
            "Convert the uploaded SOP into strict JSON only. "
            "Split compound instructions into atomic steps. "
            "Assign one best matching class_name from the provided registry. "
            "Use only classes from this list: "
            + ", ".join(class_names)
            + ". Return JSON with keys: version, title, source_path, source_type, raw_text, metadata, steps."
        )
        prompt = {
            "source_path": str(path),
            "source_type": path.suffix.lower().lstrip("."),
            "class_names": list(class_names),
            "document_text": raw_text,
            "output_schema": {
                "version": "5.1.0",
                "title": "string",
                "source_path": "string",
                "source_type": "pdf|txt",
                "raw_text": "string",
                "metadata": {"source_file_name": "string", "atomization_notes": "string"},
                "steps": [
                    {
                        "id": "step_001",
                        "name": "string",
                        "type": "click|type_text|press_key|wait_ms|drag|validate_pins|auth_sequence|input_text|mold_setup",
                        "target": "string|null",
                        "description": "string",
                        "enabled": True,
                        "class_name": "string|null",
                        "confidence": 0.0,
                        "source_page": 1,
                        "source_span": "string",
                        "preconditions": [],
                        "postconditions": [],
                    }
                ],
            },
        }
        raw = self._llm.chat(
            system=system,
            history=[{"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}],
            brief=True,
        )
        parsed = self._parse_json_blob(raw)
        if parsed is None:
            return self._atomize_with_rules(raw_text, class_names)
        return parsed

    def _parse_json_blob(self, text: str) -> Optional[Dict[str, Any]]:
        clean = text.strip()
        if clean.startswith("```"):
            clean = clean.strip("`")
            if clean.startswith("json"):
                clean = clean[4:].strip()
        try:
            parsed = json.loads(clean)
        except Exception:
            start = clean.find("{")
            end = clean.rfind("}")
            if start < 0 or end <= start:
                return None
            try:
                parsed = json.loads(clean[start : end + 1])
            except Exception:
                return None
        return parsed if isinstance(parsed, dict) else None

    def _atomize_with_rules(
        self, raw_text: str, class_names: Sequence[str]
    ) -> Dict[str, Any]:
        steps: List[Dict[str, Any]] = []
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        index = 1
        for line in lines:
            if len(line) < 3:
                continue
            step_type = self._infer_step_type(line)
            class_name = self._infer_class_name(line, class_names)
            step = SOPAtom(
                id=f"step_{index:03d}",
                name=line[:80],
                type=step_type,
                target=class_name,
                description=line,
                class_name=class_name,
                confidence=0.5 if class_name else 0.25,
                raw_text=line,
            )
            steps.append(step.to_step())
            index += 1
        title = self._extract_title(lines) or "Imported SOP"
        return {
            "version": "5.1.0",
            "title": title,
            "source_path": "",
            "source_type": "text",
            "raw_text": raw_text,
            "metadata": {"atomization_mode": "rules"},
            "steps": steps,
        }

    def _normalize_artifact(
        self,
        data: Dict[str, Any],
        path: Path,
        raw_text: str,
        source_type: str,
    ) -> SOPDocumentArtifact:
        steps = self._normalize_steps(data.get("steps", []))
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {"note": str(metadata)}
        metadata.setdefault("source_file_name", path.name)
        metadata.setdefault("atomization_mode", "llm" if self._llm is not None else "rules")
        metadata.setdefault("class_registry", ClassRegistry.load().class_names())
        return SOPDocumentArtifact(
            version=str(data.get("version", "5.1.0")),
            title=str(data.get("title", path.stem)),
            source_path=str(path),
            source_type=source_type,
            raw_text=raw_text,
            steps=steps,
            metadata=metadata,
        )

    def _normalize_steps(self, steps: Any) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        if not isinstance(steps, list):
            return normalized
        for idx, item in enumerate(steps, start=1):
            if not isinstance(item, dict):
                continue
            step_type = str(item.get("type", "click")).strip()
            if step_type not in _STEP_TYPES:
                step_type = "click"
            atom = SOPAtom(
                id=str(item.get("id") or f"step_{idx:03d}"),
                name=str(item.get("name") or item.get("description") or f"Step {idx}"),
                type=step_type,
                target=self._sanitize_target(item.get("target")),
                description=str(item.get("description") or item.get("source_text") or ""),
                enabled=bool(item.get("enabled", True)),
                class_name=self._sanitize_target(item.get("class_name")),
                confidence=self._safe_float(item.get("confidence")),
                source_page=self._safe_int(item.get("source_page")),
                source_span=self._safe_text(item.get("source_span")),
                preconditions=self._ensure_string_list(item.get("preconditions")),
                postconditions=self._ensure_string_list(item.get("postconditions")),
                raw_text=str(item.get("source_text") or item.get("raw_text") or ""),
                extra={
                    key: value
                    for key, value in item.items()
                    if key
                    not in {
                        "id",
                        "name",
                        "type",
                        "target",
                        "description",
                        "enabled",
                        "class_name",
                        "confidence",
                        "source_page",
                        "source_span",
                        "preconditions",
                        "postconditions",
                        "source_text",
                        "raw_text",
                    }
                },
            )
            normalized.append(atom.to_step())
        return normalized

    def validate_artifact(self, artifact: SOPDocumentArtifact) -> None:
        if not artifact.steps:
            raise ValueError("SOP document did not produce any steps.")
        for step in artifact.steps:
            if not step.get("id") or not step.get("name"):
                raise ValueError(f"Invalid SOP step: {step!r}")
            if step.get("type") not in _STEP_TYPES:
                raise ValueError(f"Unsupported SOP step type: {step.get('type')!r}")

    def _infer_step_type(self, line: str) -> str:
        lowered = line.lower()
        if any(word in lowered for word in ("wait", "pause", "sleep")):
            return "wait_ms"
        if any(word in lowered for word in ("enter", "type", "input")):
            return "type_text"
        if any(word in lowered for word in ("press", "confirm", "ok", "enter key")):
            return "press_key"
        if any(word in lowered for word in ("drag", "roi", "select area", "box")):
            return "drag"
        if any(word in lowered for word in ("verify", "check", "count")):
            return "validate_pins"
        if any(word in lowered for word in ("login", "recipe", "save", "apply", "open", "click")):
            return "click"
        return "click"

    def _infer_class_name(
        self, line: str, class_names: Sequence[str]
    ) -> Optional[str]:
        lowered = line.lower()
        for class_name in class_names:
            if class_name.lower().replace("_", " ") in lowered:
                return class_name
        aliases = {
            "left mold": "mold_left_label",
            "right mold": "mold_right_label",
            "mold left": "mold_left_label",
            "mold right": "mold_right_label",
            "pin": "connector_pin",
            "login": "login_button",
            "recipe": "recipe_button",
            "apply": "apply_button",
            "save": "save_button",
            "open": "open_icon",
            "image source": "image_source",
        }
        for needle, class_name in aliases.items():
            if needle in lowered and class_name in class_names:
                return class_name
        return None

    def _extract_title(self, lines: Sequence[str]) -> str:
        for line in lines[:5]:
            if len(line) > 4:
                return line.strip(" -:\t")
        return ""

    def _sanitize_target(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _safe_float(self, value: Any) -> Optional[float]:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except Exception:
            return None

    def _safe_int(self, value: Any) -> Optional[int]:
        try:
            if value is None or value == "":
                return None
            return int(value)
        except Exception:
            return None

    def _safe_text(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _ensure_string_list(self, value: Any) -> List[str]:
        if not value:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [value] if value.strip() else []
        return [str(value)]
