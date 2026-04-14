from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from src.class_registry import ClassRegistry
from src.sop_document_ingest import SOPDocumentExtraction, SOPDocumentIngestor

_CANONICAL_VERSION = "1.0"
_PACKAGE_VERSION = "1.0"
_AUTOMATION_KINDS = {"automatable", "manual", "conditional", "unknown"}
_COMPILE_STEP_TYPES = {
    "click",
    "click_sequence",
    "input_text",
    "type_text",
    "press_key",
    "wait_ms",
    "drag",
    "auth_sequence",
}
_OPTIONAL_EXTENSION_TYPES = {"validate_pins", "mold_setup"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "step"


def _target_to_runtime_name(target: Dict[str, Any]) -> Optional[str]:
    if not isinstance(target, dict):
        return None
    name = str(target.get("name") or "").strip()
    if name:
        return name
    text = str(target.get("text") or target.get("screen_label") or "").strip()
    if not text:
        return None
    suffix = "_button" if " " not in text else ""
    return _slugify(text) + suffix


def _source_refs_for(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    refs = item.get("source_refs") or []
    if isinstance(refs, list):
        return [ref for ref in refs if isinstance(ref, dict)]
    return []


@dataclass
class RuntimeCompileResult:
    canonical: Dict[str, Any]
    runtime_json: Dict[str, Any]
    warnings: List[str]
    supported_steps: List[str]
    unsupported_steps: List[str]
    runtime_profile: Dict[str, Any]


class SOPGenerationService:
    def __init__(self, llm: Any | None = None, ocr: Any | None = None) -> None:
        self._llm = llm
        self._ocr = ocr
        self._ingestor = SOPDocumentIngestor(llm=llm, ocr=ocr)

    def generate_from_document(self, file_path: str | Path) -> Dict[str, Any]:
        extraction = self._ingestor.extract_document(file_path)
        steps = self._extract_step_candidates(extraction)
        questions = self._build_questions(steps, extraction)
        canonical = self._build_canonical(extraction, steps, questions, {})
        compile_result = self.compile_to_runtime_json(canonical, self.build_runtime_profile())
        canonical["compile_result"] = self._compile_payload(compile_result)
        return canonical

    def generation_readiness(self) -> str:
        if self._llm is None:
            raise RuntimeError(
                "SOP Generate requires a configured Ollama Gemma runtime with TurboQuant enabled."
            )
        cfg = getattr(self._llm, "cfg", None)
        backend = str(getattr(cfg, "backend", ""))
        model_path = str(getattr(cfg, "model_path", "") or "")
        turboquant_enabled = bool(getattr(cfg, "turboquant_enabled", False))
        if backend != "ollama":
            raise RuntimeError(
                "SOP Generate requires the Ollama backend for document-to-SOP generation."
            )
        if "gemma" not in model_path.lower():
            raise RuntimeError(
                "SOP Generate requires the Gemma deployment target configured in llm.model_path."
            )
        if not turboquant_enabled:
            raise RuntimeError(
                "SOP Generate is unavailable because TurboQuant is not enabled in the LLM config."
            )
        health_check = getattr(self._llm, "check_health", None)
        if callable(health_check):
            result = health_check()
            return result or "Ollama generation runtime is ready."
        return "Ollama generation runtime is ready."

    def answer_generation_questions(
        self,
        canonical: Dict[str, Any],
        answers: Dict[str, Any],
    ) -> Dict[str, Any]:
        updated = json.loads(json.dumps(canonical))
        stored_answers = updated.setdefault("answers", {})
        stored_answers.update(answers)
        question_map = {q["id"]: q for q in updated.get("questions_asked", []) if isinstance(q, dict)}
        workflow_steps = updated.get("workflow", {}).get("steps", [])
        for qid, answer in answers.items():
            question = question_map.get(qid)
            if not question:
                continue
            for path in question.get("affects_fields", []):
                self._apply_answer_to_path(updated, workflow_steps, path, answer)
        compile_result = self.compile_to_runtime_json(updated, self.build_runtime_profile())
        updated["compile_result"] = self._compile_payload(compile_result)
        return updated

    def finalize_canonical_sop(self, canonical: Dict[str, Any]) -> Dict[str, Any]:
        finalized = json.loads(json.dumps(canonical))
        missing = []
        for question in finalized.get("questions_asked", []):
            if not isinstance(question, dict):
                continue
            if question.get("required") and question.get("id") not in finalized.get("answers", {}):
                missing.append(question.get("id"))
        if missing:
            raise ValueError(
                "Required SOP generation questions are unanswered: "
                + ", ".join(str(item) for item in missing)
            )
        finalized.setdefault("metadata", {})["status"] = "finalized"
        finalized.setdefault("metadata", {})["finalized_at"] = _utc_now()
        compile_result = self.compile_to_runtime_json(finalized, self.build_runtime_profile())
        finalized["compile_result"] = self._compile_payload(compile_result)
        return finalized

    def compile_to_runtime_json(
        self,
        canonical: Dict[str, Any],
        runtime_profile: Dict[str, Any],
    ) -> RuntimeCompileResult:
        registry = ClassRegistry.load()
        runtime_steps: List[Dict[str, Any]] = []
        warnings: List[str] = []
        supported_steps: List[str] = []
        unsupported_steps: List[str] = []

        for step in canonical.get("workflow", {}).get("steps", []):
            if not isinstance(step, dict):
                continue
            compiled = self._compile_step(step, registry, runtime_profile)
            if compiled is None:
                unsupported_steps.append(str(step.get("id") or step.get("title") or "unknown"))
                continue
            runtime_steps.append(compiled)
            supported_steps.append(compiled["id"])
            target_name = compiled.get("target")
            if target_name and registry.get_type(target_name) is None:
                warnings.append(f"Runtime target '{target_name}' is not present in class_registry.json")

        if not runtime_steps:
            warnings.append("No automatable runtime steps were produced from the canonical SOP.")

        return RuntimeCompileResult(
            canonical=canonical,
            runtime_json={"version": "generated-1.0", "steps": runtime_steps},
            warnings=warnings,
            supported_steps=supported_steps,
            unsupported_steps=unsupported_steps,
            runtime_profile=runtime_profile,
        )

    def save_sop_package(
        self,
        canonical: Dict[str, Any],
        compile_result: Optional[RuntimeCompileResult],
        destination: str | Path,
    ) -> Path:
        dest = Path(destination)
        dest.parent.mkdir(parents=True, exist_ok=True)
        manifest = {
            "package_version": _PACKAGE_VERSION,
            "created_at": _utc_now(),
            "app_version": "6.0.0",
            "has_compiled_runtime": compile_result is not None,
            "runtime_profile": compile_result.runtime_profile if compile_result else {},
            "warnings": compile_result.warnings if compile_result else [],
        }
        with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            zf.writestr("canonical.sop.json", json.dumps(canonical, ensure_ascii=False, indent=2))
            if compile_result is not None:
                zf.writestr(
                    "compiled.sop_steps.json",
                    json.dumps(compile_result.runtime_json, ensure_ascii=False, indent=2),
                )
        return dest

    def import_sop_package(self, package_path: str | Path) -> Dict[str, Any]:
        path = Path(package_path)
        if not path.exists():
            raise FileNotFoundError(f"SOP package not found: {path}")
        with zipfile.ZipFile(path, "r") as zf:
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            canonical = json.loads(zf.read("canonical.sop.json").decode("utf-8"))
            compiled = None
            if "compiled.sop_steps.json" in zf.namelist():
                compiled = json.loads(zf.read("compiled.sop_steps.json").decode("utf-8"))
        return {"manifest": manifest, "canonical": canonical, "compiled_runtime": compiled}

    def build_runtime_profile(self) -> Dict[str, Any]:
        return {
            "registry_classes": ClassRegistry.load().class_names(),
            "optional_extensions": ["connector_pin"],
        }

    def _compile_payload(self, compile_result: RuntimeCompileResult) -> Dict[str, Any]:
        return {
            "supported_steps": list(compile_result.supported_steps),
            "unsupported_steps": list(compile_result.unsupported_steps),
            "warnings": list(compile_result.warnings),
            "runtime_profile": dict(compile_result.runtime_profile),
            "output_path": "",
        }

    def _extract_step_candidates(self, extraction: SOPDocumentExtraction) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        blocks = extraction.refs or self._ingestor._build_text_refs(extraction.raw_text)  # noqa: SLF001
        for block_index, ref in enumerate(blocks, start=1):
            lines = [line.strip(" -*\t") for line in ref.text.splitlines() if line.strip()]
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
                        "automation_kind": self._infer_automation_kind(lower, action_kind),
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

    def _build_questions(
        self,
        steps: Sequence[Dict[str, Any]],
        extraction: SOPDocumentExtraction,
    ) -> List[Dict[str, Any]]:
        questions: List[Dict[str, Any]] = [
            {
                "id": "workflow_goal",
                "category": "sop_goal_type",
                "prompt": "What kind of SOP is this document describing?",
                "answer_type": "single_choice",
                "options": ["ui_automation", "manual_work_instruction", "hybrid"],
                "required": True,
                "affects_fields": ["automation_profile.sop_goal_type"],
                "source_refs": [ref.to_json() for ref in extraction.refs[:1]],
            }
        ]
        for step in steps:
            step_id = step["id"]
            refs = _source_refs_for(step)
            if step.get("automation_kind") == "unknown":
                questions.append(
                    {
                        "id": f"{step_id}_automation_kind",
                        "category": "ui_vs_manual",
                        "prompt": f"How should '{step['title']}' be classified?",
                        "answer_type": "single_choice",
                        "options": ["automatable", "manual", "conditional"],
                        "required": True,
                        "affects_fields": [f"workflow.steps.{step_id}.automation_kind"],
                        "source_refs": refs,
                    }
                )
            if not step.get("target") and step.get("automation_kind") in {"automatable", "conditional"}:
                questions.append(
                    {
                        "id": f"{step_id}_target_name",
                        "category": "execution_environment",
                        "prompt": f"What runtime target name should be used for '{step['title']}'?",
                        "answer_type": "text",
                        "options": [],
                        "required": True,
                        "affects_fields": [f"workflow.steps.{step_id}.target.name"],
                        "source_refs": refs,
                    }
                )
            if step.get("action_kind") == "wait" and "ms" not in step.get("parameters", {}):
                questions.append(
                    {
                        "id": f"{step_id}_wait_ms",
                        "category": "repeat_counts_timeouts",
                        "prompt": f"What wait duration should '{step['title']}' use?",
                        "answer_type": "single_choice",
                        "options": ["250", "500", "1000", "2000"],
                        "required": True,
                        "affects_fields": [f"workflow.steps.{step_id}.parameters.ms"],
                        "source_refs": refs,
                    }
                )
        deduped: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for question in questions:
            qid = str(question.get("id") or "")
            if not qid or qid in seen:
                continue
            seen.add(qid)
            deduped.append(question)
        return deduped

    def _build_canonical(
        self,
        extraction: SOPDocumentExtraction,
        steps: Sequence[Dict[str, Any]],
        questions: Sequence[Dict[str, Any]],
        answers: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "metadata": {
                "version": _CANONICAL_VERSION,
                "title": extraction.title,
                "status": "draft",
                "created_at": _utc_now(),
            },
            "source_document": extraction.to_json(),
            "workflow": {"steps": list(steps)},
            "questions_asked": list(questions),
            "answers": dict(answers),
            "automation_profile": {"sop_goal_type": "hybrid", "extensions": {}},
            "portability": {"mode": "portable_default"},
            "compile_result": {
                "supported_steps": [],
                "unsupported_steps": [],
                "warnings": [],
                "runtime_profile": self.build_runtime_profile(),
                "output_path": "",
            },
        }

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
            return {"text": text, "name": _slugify(text) + "_button", "screen_label": text}
        if "login" in lower:
            return {"text": "LOGIN", "name": "login_button", "screen_label": "LOGIN"}
        if "save" in lower:
            return {"text": "SAVE", "name": "save_button", "screen_label": "SAVE"}
        if "apply" in lower:
            return {"text": "APPLY", "name": "apply_button", "screen_label": "APPLY"}
        return {}

    def _infer_parameters(self, lower: str) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        ms_match = re.search(r"(\d+)\s*(ms|millisecond|milliseconds|sec|second|seconds)", lower)
        if ms_match:
            value = int(ms_match.group(1))
            unit = ms_match.group(2)
            params["ms"] = value * 1000 if unit.startswith("sec") else value
        if any(word in lower for word in ("enter key", "press enter", "return")):
            params["key"] = "Return"
        if any(word in lower for word in ("password", "passcode")):
            params["sensitive_input"] = True
        return params

    def _compile_step(
        self,
        step: Dict[str, Any],
        registry: ClassRegistry,
        runtime_profile: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        automation_kind = step.get("automation_kind", "unknown")
        if automation_kind not in _AUTOMATION_KINDS or automation_kind not in {"automatable", "conditional"}:
            return None
        step_id = str(step.get("id") or _slugify(str(step.get("title") or "step")))
        title = str(step.get("title") or step_id)
        description = str(step.get("intent") or title)
        action_kind = str(step.get("action_kind") or "")
        target = step.get("target") or {}
        parameters = step.get("parameters") or {}
        runtime_target = _target_to_runtime_name(target)
        compiled: Dict[str, Any] = {
            "id": step_id,
            "name": title,
            "description": description,
            "enabled": True,
        }

        if action_kind == "click":
            runtime_type = "click"
            compiled["target"] = runtime_target or step_id
            if target.get("text"):
                compiled["button_text"] = str(target["text"])
        elif action_kind == "input":
            if runtime_target:
                runtime_type = "input_text"
                compiled["target"] = runtime_target
                compiled["text"] = str(parameters.get("text") or parameters.get("value") or "0")
                compiled["clear_first"] = bool(parameters.get("clear_first", True))
            else:
                runtime_type = "type_text"
                compiled["text"] = str(parameters.get("text") or parameters.get("value") or "")
                compiled["clear_first"] = bool(parameters.get("clear_first", False))
        elif action_kind == "wait":
            runtime_type = "wait_ms"
            compiled["ms"] = int(parameters.get("ms") or 500)
        elif action_kind == "drag":
            runtime_type = "drag"
            compiled["start"] = list(parameters.get("start") or [100, 200])
            compiled["end"] = list(parameters.get("end") or [800, 350])
        elif action_kind == "auth":
            runtime_type = "auth_sequence"
            compiled["login_button"] = runtime_target or "login_button"
            compiled["password_field"] = str(parameters.get("password_field") or "password_field")
            compiled["ok_button"] = str(parameters.get("ok_button") or "ok_button")
        elif action_kind == "validate":
            if "connector_pin" not in runtime_profile.get("optional_extensions", []):
                return None
            runtime_type = "validate_pins"
        else:
            return None

        if runtime_type not in _COMPILE_STEP_TYPES | _OPTIONAL_EXTENSION_TYPES:
            return None

        compiled["type"] = runtime_type
        target_type = None
        if runtime_target:
            target_type = registry.get_type(runtime_target)
            if target_type:
                compiled["target_type"] = target_type
        if target_type == "NON_TEXT":
            compiled["yolo_class"] = runtime_target
        return compiled

    def _apply_answer_to_path(
        self,
        canonical: Dict[str, Any],
        workflow_steps: Sequence[Dict[str, Any]],
        path: str,
        answer: Any,
    ) -> None:
        if path.startswith("workflow.steps."):
            _, _, step_id, *rest = path.split(".")
            for step in workflow_steps:
                if str(step.get("id")) == step_id:
                    self._set_nested(step, rest, answer)
                    return
            return
        self._set_nested(canonical, path.split("."), answer)

    def _set_nested(self, root: Dict[str, Any], path: Sequence[str], value: Any) -> None:
        cur: Any = root
        for part in path[:-1]:
            if part not in cur or not isinstance(cur[part], dict):
                cur[part] = {}
            cur = cur[part]
        if path:
            cur[path[-1]] = value
