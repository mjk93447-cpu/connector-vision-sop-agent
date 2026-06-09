from __future__ import annotations

import json
from pathlib import Path

from src.sop_document_ingest import SOPDocumentExtraction, SOPSourceRef
from src.sop_llm_atomizer import SOPLLMAtomizer, parse_json_blob


class _FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def chat_sop_generation(self, **kwargs):  # noqa: ANN003
        del kwargs
        if self.calls >= len(self._responses):
            return self._responses[-1]
        payload = self._responses[self.calls]
        self.calls += 1
        return payload


def test_parse_json_blob_strips_markdown_fence() -> None:
    parsed = parse_json_blob('```json\n{"steps": []}\n```')
    assert parsed == {"steps": []}


def test_atomize_rule_fallback_without_llm() -> None:
    extraction = SOPDocumentExtraction(
        source_path="sample.txt",
        source_type="txt",
        title="Sample",
        raw_text="Click LOGIN\nWait 500 ms",
        refs=[
            SOPSourceRef(
                kind="section",
                index=1,
                label="Section 1",
                text="Click LOGIN\nWait 500 ms",
            )
        ],
    )
    result = SOPLLMAtomizer(llm=None).atomize(extraction)
    assert result.atomization_mode == "rules"
    assert len(result.steps) >= 2
    assert result.coverage_report.total_refs == 1


def test_atomize_llm_merge_and_audit(tmp_path: Path) -> None:
    del tmp_path
    llm_payload = json.dumps(
        {
            "steps": [
                {
                    "id": "step_001",
                    "title": "Click LOGIN",
                    "intent": "Click LOGIN",
                    "action_kind": "click",
                    "automation_kind": "automatable",
                    "target": {"name": "login_button", "text": "LOGIN"},
                    "source_refs": [
                        {"kind": "section", "index": 1, "label": "Section 1"}
                    ],
                    "confidence": 0.95,
                }
            ]
        },
        ensure_ascii=False,
    )
    extraction = SOPDocumentExtraction(
        source_path="sample.txt",
        source_type="txt",
        title="Sample",
        raw_text="Click LOGIN",
        refs=[
            SOPSourceRef(kind="section", index=1, label="Section 1", text="Click LOGIN")
        ],
    )
    result = SOPLLMAtomizer(llm=_FakeLLM([llm_payload])).atomize(extraction)
    assert result.atomization_mode == "llm"
    assert result.steps[0]["action_kind"] == "click"
    assert result.coverage_report.mapped_refs == 1


def test_atomize_splits_large_ref_into_chunks() -> None:
    large_text = "A" * 15000
    extraction = SOPDocumentExtraction(
        source_path="big.txt",
        source_type="txt",
        title="Big",
        raw_text=large_text,
        refs=[
            SOPSourceRef(kind="section", index=1, label="Section 1", text=large_text)
        ],
    )
    atomizer = SOPLLMAtomizer(llm=None)
    chunks = atomizer._pass_outline(extraction.refs, [])  # noqa: SLF001
    assert len(chunks) >= 2
