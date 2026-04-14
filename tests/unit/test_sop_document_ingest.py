from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.sop_document_ingest import SOPDocumentIngestor, SOPSourceRef


class _FakeRegistry:
    def class_names(self) -> list[str]:
        return [
            "login_button",
            "recipe_button",
            "mold_left_label",
            "mold_right_label",
            "connector_pin",
        ]


class _FakeLLM:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def chat(self, **kwargs):  # noqa: ANN003
        return json.dumps(self._payload, ensure_ascii=False)


def test_ingest_txt_with_llm(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("src.sop_document_ingest.ClassRegistry.load", lambda: _FakeRegistry())
    llm_payload = {
        "version": "4.4.0",
        "title": "Sample SOP",
        "source_path": "sample.txt",
        "source_type": "txt",
        "raw_text": "Login then open recipe",
        "metadata": {"atomization_mode": "llm"},
        "steps": [
            {
                "id": "step_001",
                "name": "Login",
                "type": "click",
                "target": "login_button",
                "description": "Click login",
                "enabled": True,
                "class_name": "login_button",
                "confidence": 0.9,
            }
        ],
    }
    ingestor = SOPDocumentIngestor(llm=_FakeLLM(llm_payload))
    txt = tmp_path / "sample.txt"
    txt.write_text("Login then open recipe", encoding="utf-8")

    artifact = ingestor.ingest(txt)

    assert artifact.title == "Sample SOP"
    assert artifact.steps[0]["target"] == "login_button"
    assert artifact.steps[0]["class_name"] == "login_button"


def test_ingest_txt_rule_fallback(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("src.sop_document_ingest.ClassRegistry.load", lambda: _FakeRegistry())
    ingestor = SOPDocumentIngestor()
    txt = tmp_path / "sample.txt"
    txt.write_text("Login button\nWait for recipe load\nPress enter", encoding="utf-8")

    artifact = ingestor.ingest(txt)

    assert len(artifact.steps) >= 2
    assert artifact.steps[0]["type"] in {"click", "wait_ms", "press_key"}


def test_export_json_round_trip(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("src.sop_document_ingest.ClassRegistry.load", lambda: _FakeRegistry())
    ingestor = SOPDocumentIngestor()
    artifact = ingestor._normalize_artifact(  # noqa: SLF001
        {
            "version": "4.4.0",
            "title": "Export SOP",
            "steps": [
                {
                    "id": "step_001",
                    "name": "Login",
                    "type": "click",
                    "description": "Click login",
                    "enabled": True,
                }
            ],
            "metadata": {"atomization_mode": "rules"},
        },
        tmp_path / "sample.txt",
        "Login",
        "txt",
    )

    dest = ingestor.export_json(artifact, tmp_path / "export.json")
    data = json.loads(dest.read_text(encoding="utf-8"))

    assert data["steps"][0]["name"] == "Login"
    assert data["metadata"]["atomization_mode"] == "rules"


def test_extract_document_txt_builds_section_refs(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("src.sop_document_ingest.ClassRegistry.load", lambda: _FakeRegistry())
    ingestor = SOPDocumentIngestor()
    txt = tmp_path / "sample.txt"
    txt.write_text("Header\n\nStep one\nStep two", encoding="utf-8")

    extraction = ingestor.extract_document(txt)

    assert extraction.source_type == "txt"
    assert extraction.refs
    assert extraction.refs[0].kind == "section"


def test_extract_document_pptx_uses_slide_refs(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("src.sop_document_ingest.ClassRegistry.load", lambda: _FakeRegistry())
    ingestor = SOPDocumentIngestor()
    pptx = tmp_path / "sample.pptx"
    pptx.write_bytes(b"fake")
    monkeypatch.setattr(
        ingestor,
        "_extract_pptx_refs",
        lambda _path: [SOPSourceRef(kind="slide", index=1, label="Slide 1", text="Click LOGIN")],
    )

    extraction = ingestor.extract_document(pptx)

    assert extraction.source_type == "pptx"
    assert extraction.refs[0].kind == "slide"
