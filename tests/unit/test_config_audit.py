"""Tests for src/config_audit.py — audit log manager."""

from __future__ import annotations

import json
from pathlib import Path


from src.config_audit import ConfigAuditLog, build_audit_entry


class TestBuildAuditEntry:
    def test_required_fields_present(self):
        entry = build_audit_entry(
            line_id="LINE-A3",
            username="Raj Kumar",
            action="config_apply",
            changes={"control.step_delay": {"old": 0.5, "new": 1.5}},
        )
        assert entry["line_id"] == "LINE-A3"
        assert entry["username"] == "Raj Kumar"
        assert entry["action"] == "config_apply"
        assert "ts" in entry
        assert entry["changes"]["control.step_delay"]["new"] == 1.5

    def test_defaults_populated(self):
        entry = build_audit_entry(
            line_id="X",
            username="u",
            action="a",
            changes={},
        )
        assert entry["reason"] == ""
        assert entry["llm_recommendation"] == ""
        assert entry["source"] == "llm_chat"

    def test_ts_is_utc_iso(self):
        entry = build_audit_entry(line_id="X", username="u", action="a", changes={})
        ts = entry["ts"]
        assert ts.endswith("Z")
        assert "T" in ts


class TestConfigAuditLog:
    def test_record_creates_file(self, tmp_path: Path):
        log = ConfigAuditLog(line_id="LINE-T1", log_dir=tmp_path)
        entry = log.record(
            username="Alice",
            action="config_apply",
            changes={"pin_count_min": {"old": None, "new": 40}},
            reason="SOP update",
        )
        assert entry["username"] == "Alice"
        log_file = tmp_path / "config_audit_LINE-T1.jsonl"
        assert log_file.exists()
        data = json.loads(log_file.read_text(encoding="utf-8").strip())
        assert data["username"] == "Alice"
        assert data["changes"]["pin_count_min"]["new"] == 40

    def test_multiple_records_append(self, tmp_path: Path):
        log = ConfigAuditLog(line_id="L", log_dir=tmp_path)
        log.record(username="u1", changes={"a": {"old": 1, "new": 2}})
        log.record(username="u2", changes={"b": {"old": 3, "new": 4}})
        history = log.get_history()
        assert len(history) == 2
        assert history[0]["username"] == "u1"
        assert history[1]["username"] == "u2"

    def test_get_history_empty_when_no_file(self, tmp_path: Path):
        log = ConfigAuditLog(line_id="NOFILE", log_dir=tmp_path)
        assert log.get_history() == []

    def test_get_history_limit(self, tmp_path: Path):
        log = ConfigAuditLog(line_id="L", log_dir=tmp_path)
        for i in range(10):
            log.record(username=f"user{i}", changes={})
        recent = log.get_history(limit=3)
        assert len(recent) == 3
        assert recent[-1]["username"] == "user9"

    def test_format_history_table_no_entries(self, tmp_path: Path):
        log = ConfigAuditLog(line_id="E", log_dir=tmp_path)
        table = log.format_history_table()
        assert "no config changes" in table

    def test_format_history_table_with_entries(self, tmp_path: Path):
        log = ConfigAuditLog(line_id="T", log_dir=tmp_path)
        log.record(
            username="Raj Kumar",
            action="config_apply",
            changes={"control.step_delay": {"old": 0.5, "new": 1.5}},
        )
        table = log.format_history_table()
        assert "Raj Kumar" in table
        assert "control.step_delay" in table

    def test_line_id_in_log_path(self, tmp_path: Path):
        log = ConfigAuditLog(line_id="LINE-B7", log_dir=tmp_path)
        log.record(username="x", changes={})
        assert (tmp_path / "config_audit_LINE-B7.jsonl").exists()

    def test_creates_log_dir_if_missing(self, tmp_path: Path):
        nested = tmp_path / "deep" / "logs"
        log = ConfigAuditLog(line_id="L", log_dir=nested)
        log.record(username="x", changes={})
        assert nested.exists()

    def test_corrupted_line_skipped(self, tmp_path: Path):
        log = ConfigAuditLog(line_id="L", log_dir=tmp_path)
        log_file = tmp_path / "config_audit_L.jsonl"
        log_file.write_text(
            '{"username": "good"}\nNOT_JSON\n{"username": "also_good"}\n',
            encoding="utf-8",
        )
        history = log.get_history()
        assert len(history) == 2
        assert history[0]["username"] == "good"
