"""Multi-pass LLM atomization for SOP Generate (outline → extract → merge → audit)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from src.class_registry import ClassRegistry
from src.sop_document_ingest import SOPDocumentExtraction, SOPSourceRef

_PROGRESS_CALLBACK = Optional[Callable[[str, int, int], None]]

_CANONICAL_ACTION_KINDS = {
    "click",
    "input",
    "wait",
    "drag",
    "auth",
    "validate",
    "review",
}
_AUTOMATION_KINDS = {"automatable", "manual", "conditional", "unknown"}
_MAX_CHUNK_CHARS = 12000
_ROLLING_STEP_COUNT = 3


@dataclass
class CoverageReport:
    total_refs: int
    mapped_refs: int
    unmapped_refs: List[Dict[str, Any]]
    low_confidence_steps: List[str]
    coverage_percent: float

    def to_json(self) -> Dict[str, Any]:
        return {
            "total_refs": self.total_refs,
            "mapped_refs": self.mapped_refs,
            "unmapped_refs": self.unmapped_refs,
            "low_confidence_steps": self.low_confidence_steps,
            "coverage_percent": round(self.coverage_percent, 2),
        }


@dataclass
class AtomizeResult:
    steps: List[Dict[str, Any]]
    coverage_report: CoverageReport
    atomization_mode: str
    warnings: List[str] = field(default_factory=list)
    chunk_count: int = 0


def parse_json_blob(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?\s*", "", clean)
        clean = re.sub(r"\s*```$", "", clean)
    try:
        parsed = json.loads(clean)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass
    start = clean.find("{")
    end = clean.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(clean[start : end + 1])
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def repair_json_with_llm(
    llm: Any, broken_text: str, schema_hint: str
) -> Optional[Dict[str, Any]]:
    system = (
        "You repair malformed JSON. Return ONLY valid JSON matching the requested schema. "
        "No markdown, no commentary."
    )
    prompt = f"Schema hint:\n{schema_hint}\n\nBroken output:\n{broken_text[:8000]}"
    raw = llm.chat_sop_generation(
        system=system,
        history=[{"role": "user", "content": prompt}],
        brief=False,
    )
    return parse_json_blob(raw)


class SOPLLMAtomizer:
    """Four-pass document atomizer with coverage audit."""

    def __init__(
        self, llm: Any | None = None, on_progress: _PROGRESS_CALLBACK = None
    ) -> None:
        self._llm = llm
        self._on_progress = on_progress

    def atomize(self, extraction: SOPDocumentExtraction) -> AtomizeResult:
        refs = extraction.refs or self._build_fallback_refs(extraction.raw_text)
        class_names = ClassRegistry.load().class_names()

        if self._llm is None or not extraction.raw_text.strip():
            steps = self._rule_fallback_steps(extraction.raw_text, refs)
            report = self._audit_coverage(steps, refs)
            return AtomizeResult(
                steps=steps,
                coverage_report=report,
                atomization_mode="rules",
                warnings=["LLM unavailable; used rule-based extraction."],
                chunk_count=len(refs),
            )

        try:
            chunks = self._pass_outline(refs, class_names)
            self._emit_progress("outline", 1, 4)
            extracted: List[Dict[str, Any]] = []
            rolling_summary = ""
            for index, chunk in enumerate(chunks, start=1):
                chunk_steps = self._pass_extract_chunk(
                    chunk,
                    class_names,
                    rolling_summary,
                    extraction,
                )
                extracted.extend(chunk_steps)
                rolling_summary = self._rolling_summary(extracted)
                self._emit_progress("extract", index, len(chunks))
            self._emit_progress("extract", 4, 4)
            merged = self._pass_merge(extracted)
            self._emit_progress("merge", 3, 4)
            report = self._pass_audit(merged, refs)
            self._emit_progress("audit", 4, 4)
            warnings: List[str] = []
            if report.unmapped_refs:
                warnings.append(
                    f"{len(report.unmapped_refs)} source section(s) have no mapped workflow step."
                )
            return AtomizeResult(
                steps=merged,
                coverage_report=report,
                atomization_mode="llm",
                warnings=warnings,
                chunk_count=len(chunks),
            )
        except Exception as exc:
            steps = self._rule_fallback_steps(extraction.raw_text, refs)
            report = self._audit_coverage(steps, refs)
            return AtomizeResult(
                steps=steps,
                coverage_report=report,
                atomization_mode="rules_fallback",
                warnings=[f"LLM atomization failed ({exc}); used rule-based fallback."],
                chunk_count=len(refs),
            )

    def _emit_progress(self, phase: str, current: int, total: int) -> None:
        if self._on_progress is not None:
            self._on_progress(phase, current, total)

    def _build_fallback_refs(self, raw_text: str) -> List[SOPSourceRef]:
        blocks = [
            block.strip() for block in re.split(r"\n\s*\n", raw_text) if block.strip()
        ]
        if not blocks:
            blocks = [line.strip() for line in raw_text.splitlines() if line.strip()]
        refs: List[SOPSourceRef] = []
        for idx, block in enumerate(blocks, start=1):
            refs.append(
                SOPSourceRef(
                    kind="section", index=idx, label=f"Section {idx}", text=block
                )
            )
        return refs

    def _pass_outline(
        self, refs: Sequence[SOPSourceRef], class_names: Sequence[str]
    ) -> List[Dict[str, Any]]:
        chunks: List[Dict[str, Any]] = []
        for ref in refs:
            text = ref.text.strip()
            if not text:
                continue
            if len(text) <= _MAX_CHUNK_CHARS:
                chunks.append({"ref": ref.to_json(), "text": text, "label": ref.label})
                continue
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
            part = 1
            buffer = ""
            for paragraph in paragraphs:
                candidate = f"{buffer}\n\n{paragraph}".strip() if buffer else paragraph
                if len(candidate) > _MAX_CHUNK_CHARS and buffer:
                    chunks.append(
                        {
                            "ref": {**ref.to_json(), "part": part},
                            "text": buffer,
                            "label": f"{ref.label} (part {part})",
                        }
                    )
                    part += 1
                    buffer = paragraph
                else:
                    buffer = candidate
            if buffer:
                while len(buffer) > _MAX_CHUNK_CHARS:
                    chunks.append(
                        {
                            "ref": {**ref.to_json(), "part": part},
                            "text": buffer[:_MAX_CHUNK_CHARS],
                            "label": f"{ref.label} (part {part})",
                        }
                    )
                    part += 1
                    buffer = buffer[_MAX_CHUNK_CHARS:]
                if buffer:
                    chunks.append(
                        {
                            "ref": {**ref.to_json(), "part": part},
                            "text": buffer,
                            "label": (
                                f"{ref.label} (part {part})" if part > 1 else ref.label
                            ),
                        }
                    )
        if not chunks and refs:
            chunks = [
                {"ref": refs[0].to_json(), "text": refs[0].text, "label": refs[0].label}
            ]
        return chunks

    def _pass_extract_chunk(
        self,
        chunk: Dict[str, Any],
        class_names: Sequence[str],
        rolling_summary: str,
        extraction: SOPDocumentExtraction,
    ) -> List[Dict[str, Any]]:
        system = (
            "You are an offline SOP atomization engine for factory UI automation. "
            "Convert the chunk into atomic workflow steps as strict JSON only. "
            "Each step must cite source_refs from the chunk. "
            "Use action_kind in click|input|wait|drag|auth|validate|review and "
            "automation_kind in automatable|manual|conditional|unknown. "
            "Map UI targets to class_registry names when possible."
        )
        payload = {
            "chunk_label": chunk.get("label"),
            "source_ref": chunk.get("ref"),
            "rolling_summary": rolling_summary,
            "class_names": list(class_names),
            "document_title": extraction.title,
            "chunk_text": chunk.get("text"),
            "output_schema": {
                "steps": [
                    {
                        "id": "step_001",
                        "title": "string",
                        "intent": "string",
                        "action_kind": "click",
                        "automation_kind": "automatable",
                        "target": {"name": "login_button", "text": "LOGIN"},
                        "parameters": {},
                        "source_refs": [chunk.get("ref")],
                        "status": "draft",
                        "confidence": 0.9,
                    }
                ]
            },
        }
        raw = self._llm.chat_sop_generation(
            system=system,
            history=[
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
            ],
            brief=False,
            json_mode=True,
        )
        parsed = parse_json_blob(raw)
        if parsed is None:
            parsed = repair_json_with_llm(
                self._llm,
                raw,
                '{"steps": [{"id":"...", "title":"...", "action_kind":"...", "source_refs":[]}]}',
            )
        if parsed is None:
            return self._rule_fallback_steps(str(chunk.get("text") or ""), [])
        steps = parsed.get("steps", [])
        if not isinstance(steps, list):
            return []
        normalized: List[Dict[str, Any]] = []
        for idx, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                continue
            normalized.append(self._normalize_canonical_step(step, chunk, idx))
        return normalized

    def _pass_merge(self, steps: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        merged: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for step in steps:
            if not isinstance(step, dict):
                continue
            key = self._step_dedupe_key(step)
            if key in seen:
                continue
            seen.add(key)
            merged.append(step)
        for index, step in enumerate(merged, start=1):
            step["id"] = f"step_{index:03d}"
        return merged

    def _pass_audit(
        self, steps: Sequence[Dict[str, Any]], refs: Sequence[SOPSourceRef]
    ) -> CoverageReport:
        return self._audit_coverage(steps, refs)

    def _audit_coverage(
        self, steps: Sequence[Dict[str, Any]], refs: Sequence[SOPSourceRef]
    ) -> CoverageReport:
        ref_keys = {self._ref_key(ref.to_json()) for ref in refs}
        mapped: set[str] = set()
        low_confidence: List[str] = []
        for step in steps:
            if not isinstance(step, dict):
                continue
            confidence = step.get("confidence")
            if isinstance(confidence, (int, float)) and float(confidence) < 0.5:
                low_confidence.append(
                    str(step.get("id") or step.get("title") or "unknown")
                )
            for ref in step.get("source_refs") or []:
                if isinstance(ref, dict):
                    mapped.add(self._ref_key(ref))
        unmapped = [
            ref.to_json() for ref in refs if self._ref_key(ref.to_json()) not in mapped
        ]
        total = len(ref_keys) or 1
        mapped_count = total - len(unmapped)
        percent = (mapped_count / total) * 100.0
        return CoverageReport(
            total_refs=len(refs),
            mapped_refs=mapped_count,
            unmapped_refs=unmapped,
            low_confidence_steps=low_confidence,
            coverage_percent=percent,
        )

    def _normalize_canonical_step(
        self, step: Dict[str, Any], chunk: Dict[str, Any], index: int
    ) -> Dict[str, Any]:
        action_kind = str(step.get("action_kind") or "review").lower()
        if action_kind not in _CANONICAL_ACTION_KINDS:
            action_kind = "review"
        automation_kind = str(step.get("automation_kind") or "unknown").lower()
        if automation_kind not in _AUTOMATION_KINDS:
            automation_kind = "unknown"
        source_refs = step.get("source_refs") or []
        if not source_refs:
            source_refs = [chunk.get("ref")]
        target = step.get("target") if isinstance(step.get("target"), dict) else {}
        return {
            "id": str(step.get("id") or f"step_{index:03d}"),
            "title": str(step.get("title") or step.get("name") or f"Step {index}")[
                :120
            ],
            "intent": str(
                step.get("intent") or step.get("description") or step.get("title") or ""
            ),
            "action_kind": action_kind,
            "automation_kind": automation_kind,
            "target": target,
            "inputs": step.get("inputs") or [],
            "outputs": step.get("outputs") or [],
            "preconditions": step.get("preconditions") or [],
            "postconditions": step.get("postconditions") or [],
            "decision_points": step.get("decision_points") or [],
            "validations": step.get("validations") or [],
            "parameters": (
                step.get("parameters")
                if isinstance(step.get("parameters"), dict)
                else {}
            ),
            "source_refs": [ref for ref in source_refs if isinstance(ref, dict)],
            "status": "draft",
            "confidence": step.get("confidence"),
        }

    def _rule_fallback_steps(
        self, raw_text: str, refs: Sequence[SOPSourceRef]
    ) -> List[Dict[str, Any]]:
        use_refs = list(refs) if refs else self._build_fallback_refs(raw_text)
        candidates: List[Dict[str, Any]] = []
        for block_index, ref in enumerate(use_refs, start=1):
            lines = [
                line.strip(" -*\t") for line in ref.text.splitlines() if line.strip()
            ]
            if not lines:
                continue
            for line_index, line in enumerate(lines, start=1):
                lower = line.lower()
                action_kind = self._infer_action_kind(lower)
                candidates.append(
                    {
                        "id": f"step_{block_index:03d}_{line_index:02d}",
                        "title": line[:120],
                        "intent": line,
                        "action_kind": action_kind,
                        "automation_kind": self._infer_automation_kind(
                            lower, action_kind
                        ),
                        "target": self._infer_target(line, lower),
                        "inputs": [],
                        "outputs": [],
                        "preconditions": [],
                        "postconditions": [],
                        "decision_points": [],
                        "validations": [],
                        "parameters": self._infer_parameters(lower),
                        "source_refs": [ref.to_json()],
                        "status": "draft",
                    }
                )
        return candidates

    def _infer_action_kind(self, lower: str) -> str:
        if any(word in lower for word in ("click", "press", "select", "open")):
            return "click"
        if any(word in lower for word in ("type", "enter", "input")):
            return "input"
        if any(word in lower for word in ("wait", "delay", "pause")):
            return "wait"
        if any(word in lower for word in ("drag", "draw", "mark roi", "select area")):
            return "drag"
        if any(word in lower for word in ("login", "sign in", "authenticate")):
            return "auth"
        if any(word in lower for word in ("verify", "validate", "check", "inspect")):
            return "validate"
        return "review"

    def _infer_automation_kind(self, lower: str, action_kind: str) -> str:
        if action_kind in {"click", "input", "wait", "drag", "auth"}:
            return "automatable"
        if any(word in lower for word in ("inspect visually", "manually", "operator")):
            return "manual"
        if action_kind == "validate":
            return "conditional"
        return "unknown"

    def _infer_target(self, line: str, lower: str) -> Dict[str, Any]:
        quoted = re.findall(r"'([^']+)'|\"([^\"]+)\"", line)
        flattened = [part for group in quoted for part in group if part]
        if flattened:
            text = flattened[0].strip()
            slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "step"
            return {"text": text, "name": slug + "_button", "screen_label": text}
        if "login" in lower:
            return {"text": "LOGIN", "name": "login_button", "screen_label": "LOGIN"}
        if "save" in lower:
            return {"text": "SAVE", "name": "save_button", "screen_label": "SAVE"}
        if "apply" in lower:
            return {"text": "APPLY", "name": "apply_button", "screen_label": "APPLY"}
        return {}

    def _infer_parameters(self, lower: str) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        ms_match = re.search(
            r"(\d+)\s*(ms|millisecond|milliseconds|sec|second|seconds)", lower
        )
        if ms_match:
            value = int(ms_match.group(1))
            unit = ms_match.group(2)
            params["ms"] = value * 1000 if unit.startswith("sec") else value
        if any(word in lower for word in ("enter key", "press enter", "return")):
            params["key"] = "Return"
        if any(word in lower for word in ("password", "passcode")):
            params["sensitive_input"] = True
        return params

    def _rolling_summary(self, steps: Sequence[Dict[str, Any]]) -> str:
        tail = list(steps)[-_ROLLING_STEP_COUNT:]
        lines = []
        for step in tail:
            lines.append(
                f"- {step.get('id')}: {step.get('title')} ({step.get('action_kind')})"
            )
        return "\n".join(lines)

    def _step_dedupe_key(self, step: Dict[str, Any]) -> str:
        title = str(step.get("title") or "").strip().lower()
        intent = str(step.get("intent") or "").strip().lower()
        action = str(step.get("action_kind") or "").strip().lower()
        target = ""
        target_obj = step.get("target")
        if isinstance(target_obj, dict):
            target = str(target_obj.get("name") or target_obj.get("text") or "").lower()
        return f"{action}|{target}|{title}|{intent[:80]}"

    def _ref_key(self, ref: Dict[str, Any]) -> str:
        return f"{ref.get('kind')}:{ref.get('index')}:{ref.get('label')}"
