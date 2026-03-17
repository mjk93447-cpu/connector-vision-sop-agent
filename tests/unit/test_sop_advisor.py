"""
sop_advisor 단위 테스트.

apply_config_patch, write_proposed_config, summarize_failures, propose_actions
전체를 외부 의존 없이 검증한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


from src.config_audit import ConfigAuditLog
from src.sop_advisor import (
    SAFE_NUMERIC_RANGES,
    apply_config_direct,
    apply_config_patch,
    propose_actions,
    summarize_failures,
    write_proposed_config,
)


# ---------------------------------------------------------------------------
# apply_config_patch
# ---------------------------------------------------------------------------


class TestApplyConfigPatch:
    def test_simple_key_updated(self) -> None:
        cfg: dict[str, Any] = {"vision": {"confidence_threshold": 0.6}}
        new_cfg, warnings = apply_config_patch(cfg, {"confidence_threshold": 0.8})
        assert new_cfg["confidence_threshold"] == 0.8
        assert warnings == []

    def test_original_not_mutated(self) -> None:
        cfg: dict[str, Any] = {"vision": {"confidence_threshold": 0.6}}
        apply_config_patch(cfg, {"confidence_threshold": 0.9})
        assert cfg["vision"]["confidence_threshold"] == 0.6  # 원본 불변

    def test_out_of_range_skipped_with_warning(self) -> None:
        cfg: dict[str, Any] = {"confidence_threshold": 0.6}
        new_cfg, warnings = apply_config_patch(cfg, {"confidence_threshold": 9.99})
        assert new_cfg["confidence_threshold"] == 0.6  # 변경 안 됨
        assert len(warnings) == 1
        assert "outside safe range" in warnings[0]

    def test_lower_bound_inclusive(self) -> None:
        lo, _ = SAFE_NUMERIC_RANGES["confidence_threshold"]
        cfg: dict[str, Any] = {"confidence_threshold": 0.5}
        new_cfg, warnings = apply_config_patch(cfg, {"confidence_threshold": lo})
        assert new_cfg["confidence_threshold"] == lo
        assert warnings == []

    def test_upper_bound_inclusive(self) -> None:
        _, hi = SAFE_NUMERIC_RANGES["confidence_threshold"]
        cfg: dict[str, Any] = {"confidence_threshold": 0.5}
        new_cfg, warnings = apply_config_patch(cfg, {"confidence_threshold": hi})
        assert new_cfg["confidence_threshold"] == hi
        assert warnings == []

    def test_nested_dotted_key(self) -> None:
        cfg: dict[str, Any] = {"vision": {"confidence_threshold": 0.6}}
        new_cfg, warnings = apply_config_patch(
            cfg, {"vision.confidence_threshold": 0.7}
        )
        assert new_cfg["vision"]["confidence_threshold"] == 0.7
        assert warnings == []

    def test_creates_nested_dict_if_missing(self) -> None:
        cfg: dict[str, Any] = {}
        new_cfg, _ = apply_config_patch(cfg, {"vision.confidence_threshold": 0.7})
        assert new_cfg["vision"]["confidence_threshold"] == 0.7

    def test_non_numeric_key_applied_unconditionally(self) -> None:
        cfg: dict[str, Any] = {"backend": "old"}
        new_cfg, warnings = apply_config_patch(cfg, {"backend": "new"})
        assert new_cfg["backend"] == "new"
        assert warnings == []

    def test_multiple_patches_applied(self) -> None:
        cfg: dict[str, Any] = {"a": 1, "b": 2}
        new_cfg, warnings = apply_config_patch(cfg, {"a": 10, "b": 20})
        assert new_cfg["a"] == 10
        assert new_cfg["b"] == 20
        assert warnings == []

    def test_empty_patch_returns_copy(self) -> None:
        cfg = {"key": "value"}
        new_cfg, warnings = apply_config_patch(cfg, {})
        assert new_cfg == cfg
        assert warnings == []

    def test_pin_count_min_range(self) -> None:
        cfg: dict[str, Any] = {"pin_count_min": 20}
        new_cfg, warnings = apply_config_patch(cfg, {"pin_count_min": 40})
        assert new_cfg["pin_count_min"] == 40
        assert warnings == []

    def test_pin_count_exceeds_range(self) -> None:
        cfg: dict[str, Any] = {"pin_count_min": 20}
        _, warnings = apply_config_patch(cfg, {"pin_count_min": 9999})
        assert len(warnings) == 1


# ---------------------------------------------------------------------------
# write_proposed_config
# ---------------------------------------------------------------------------


class TestWriteProposedConfig:
    def test_writes_to_proposed_path(self, tmp_path: Path) -> None:
        base = tmp_path / "config.json"
        base.write_text("{}", encoding="utf-8")
        proposed = write_proposed_config(base, {"version": "2.0.0"})
        assert proposed.name == "config.proposed.json"
        assert proposed.exists()

    def test_content_matches_input(self, tmp_path: Path) -> None:
        base = tmp_path / "config.json"
        base.write_text("{}", encoding="utf-8")
        data = {"version": "2.0.0", "key": "value"}
        proposed = write_proposed_config(base, data)
        loaded = json.loads(proposed.read_text(encoding="utf-8"))
        assert loaded == data

    def test_base_config_not_overwritten(self, tmp_path: Path) -> None:
        original = {"version": "1.0.0"}
        base = tmp_path / "config.json"
        base.write_text(json.dumps(original), encoding="utf-8")
        write_proposed_config(base, {"version": "2.0.0"})
        still_original = json.loads(base.read_text(encoding="utf-8"))
        assert still_original["version"] == "1.0.0"

    def test_unicode_content_preserved(self, tmp_path: Path) -> None:
        base = tmp_path / "config.json"
        base.write_text("{}", encoding="utf-8")
        data = {"password": "라인비번", "note": "한국어"}
        proposed = write_proposed_config(base, data)
        loaded = json.loads(proposed.read_text(encoding="utf-8"))
        assert loaded["password"] == "라인비번"

    def test_overwrites_existing_proposed(self, tmp_path: Path) -> None:
        base = tmp_path / "config.json"
        base.write_text("{}", encoding="utf-8")
        write_proposed_config(base, {"version": "1.0"})
        write_proposed_config(base, {"version": "2.0"})
        proposed = tmp_path / "config.proposed.json"
        loaded = json.loads(proposed.read_text(encoding="utf-8"))
        assert loaded["version"] == "2.0"


# ---------------------------------------------------------------------------
# summarize_failures
# ---------------------------------------------------------------------------


class TestSummarizeFailures:
    def test_counts_errors_by_step(self, sample_events: list[dict]) -> None:
        result = summarize_failures(sample_events)
        assert result["error_counts_by_step"]["login"] == 1
        assert result["error_counts_by_step"]["mold_left_roi"] == 1

    def test_ignores_info_events(self) -> None:
        events = [{"level": "INFO", "step": "login", "message": "ok", "data": {}}]
        result = summarize_failures(events)
        assert result["error_counts_by_step"] == {}

    def test_empty_events(self) -> None:
        result = summarize_failures([])
        assert result["error_counts_by_step"] == {}
        assert result["error_counts_by_message"] == {}

    def test_counts_by_message(self) -> None:
        events = [
            {"level": "ERROR", "step": "login", "message": "not found", "data": {}},
            {"level": "ERROR", "step": "roi", "message": "not found", "data": {}},
        ]
        result = summarize_failures(events)
        assert result["error_counts_by_message"]["not found"] == 2

    def test_multiple_errors_same_step(self) -> None:
        events = [
            {"level": "ERROR", "step": "login", "message": "a", "data": {}},
            {"level": "ERROR", "step": "login", "message": "b", "data": {}},
            {"level": "ERROR", "step": "login", "message": "c", "data": {}},
        ]
        result = summarize_failures(events)
        assert result["error_counts_by_step"]["login"] == 3

    def test_case_insensitive_error_level(self) -> None:
        events = [{"level": "error", "step": "x", "message": "fail", "data": {}}]
        result = summarize_failures(events)
        assert result["error_counts_by_step"]["x"] == 1

    def test_missing_step_key_treated_as_unknown(self) -> None:
        events = [{"level": "ERROR", "message": "no step field", "data": {}}]
        result = summarize_failures(events)
        assert "unknown" in result["error_counts_by_step"]


# ---------------------------------------------------------------------------
# propose_actions
# ---------------------------------------------------------------------------


class TestProposeActions:
    def test_config_patch_becomes_action(self) -> None:
        output = {
            "config_patch": {"confidence_threshold": 0.8},
            "sop_recommendations": [],
        }
        actions = propose_actions(output)
        assert len(actions) == 1
        assert actions[0]["type"] == "config_patch"
        assert actions[0]["key"] == "confidence_threshold"
        assert actions[0]["value"] == 0.8

    def test_sop_recommendation_becomes_action(self) -> None:
        output = {"config_patch": {}, "sop_recommendations": ["재시도 횟수를 늘리세요"]}
        actions = propose_actions(output)
        assert len(actions) == 1
        assert actions[0]["type"] == "sop_recommendation"
        assert "재시도" in actions[0]["description"]

    def test_combined_actions(self, mock_llm_response: dict) -> None:
        actions = propose_actions(mock_llm_response)
        types = [a["type"] for a in actions]
        assert "config_patch" in types
        assert "sop_recommendation" in types

    def test_empty_output_returns_empty_list(self) -> None:
        actions = propose_actions({"config_patch": {}, "sop_recommendations": []})
        assert actions == []

    def test_none_values_handled(self) -> None:
        actions = propose_actions({"config_patch": None, "sop_recommendations": None})
        assert actions == []

    def test_action_has_description(self) -> None:
        output = {
            "config_patch": {"confidence_threshold": 0.9},
            "sop_recommendations": [],
        }
        actions = propose_actions(output)
        assert "description" in actions[0]
        assert len(actions[0]["description"]) > 0


# ---------------------------------------------------------------------------
# apply_config_direct
# ---------------------------------------------------------------------------


class TestApplyConfigDirect:
    def _make_audit(self, tmp_path: Path) -> ConfigAuditLog:
        return ConfigAuditLog(line_id="LINE-T", log_dir=tmp_path)

    def test_writes_config_json(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "config.json"
        cfg = {"pin_count_min": 20, "version": "2.0.0"}
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

        audit = self._make_audit(tmp_path)
        new_cfg, warnings, entry = apply_config_direct(
            config=cfg,
            patch={"pin_count_min": 40},
            config_path=cfg_path,
            audit_log=audit,
            username="Raj Kumar",
            reason="SOP spec 40 pins",
        )
        assert warnings == []
        assert new_cfg["pin_count_min"] == 40
        loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
        assert loaded["pin_count_min"] == 40

    def test_audit_entry_recorded(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "config.json"
        cfg = {"pin_count_min": 20}
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

        audit = self._make_audit(tmp_path)
        _, _, entry = apply_config_direct(
            config=cfg,
            patch={"pin_count_min": 40},
            config_path=cfg_path,
            audit_log=audit,
            username="Alice",
            reason="test reason",
            source="llm_chat",
        )
        assert entry is not None
        assert entry["username"] == "Alice"
        assert entry["changes"]["pin_count_min"]["old"] == 20
        assert entry["changes"]["pin_count_min"]["new"] == 40

    def test_immutable_key_blocked(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "config.json"
        cfg = {"password": "secret", "pin_count_min": 20}
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

        audit = self._make_audit(tmp_path)
        new_cfg, warnings, entry = apply_config_direct(
            config=cfg,
            patch={"password": "hacked"},
            config_path=cfg_path,
            audit_log=audit,
            username="x",
        )
        # password must not change
        loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
        assert loaded.get("password") == "secret"
        assert any("immutable" in w for w in warnings)

    def test_out_of_range_skipped(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "config.json"
        cfg = {"pin_count_min": 20}
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

        audit = self._make_audit(tmp_path)
        _, warnings, _ = apply_config_direct(
            config=cfg,
            patch={"pin_count_min": 9999},
            config_path=cfg_path,
            audit_log=audit,
            username="x",
        )
        assert any("safe range" in w for w in warnings)

    def test_empty_patch_returns_none_entry(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "config.json"
        cfg = {"version": "2.0.0"}
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

        audit = self._make_audit(tmp_path)
        _, _, entry = apply_config_direct(
            config=cfg,
            patch={},
            config_path=cfg_path,
            audit_log=audit,
            username="x",
        )
        assert entry is None

    def test_new_control_timing_keys(self, tmp_path: Path) -> None:
        """All new timing keys must be patchable."""
        cfg_path = tmp_path / "config.json"
        cfg: dict = {"control": {"step_delay": 0.5, "move_duration": 0.1}}
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

        audit = self._make_audit(tmp_path)
        new_cfg, warnings, entry = apply_config_direct(
            config=cfg,
            patch={"control.step_delay": 2.0, "control.move_duration": 0.5},
            config_path=cfg_path,
            audit_log=audit,
            username="Bob",
        )
        assert warnings == []
        assert new_cfg["control"]["step_delay"] == 2.0
        assert new_cfg["control"]["move_duration"] == 0.5


# ---------------------------------------------------------------------------
# SAFE_NUMERIC_RANGES completeness
# ---------------------------------------------------------------------------


class TestSafeNumericRanges:
    """All new v2.1 config keys must be present in SAFE_NUMERIC_RANGES."""

    required_keys = [
        "pin_count_min",
        "pin_count_max",
        "confidence_threshold",
        "move_duration",
        "click_pause",
        "drag_duration",
        "retry_delay",
        "step_delay",
        "retries",
        "pin_area_min_px",
    ]

    def test_all_required_keys_present(self) -> None:
        for key in self.required_keys:
            assert (
                key in SAFE_NUMERIC_RANGES
            ), f"Missing key in SAFE_NUMERIC_RANGES: {key}"

    def test_all_ranges_valid(self) -> None:
        for key, (lo, hi) in SAFE_NUMERIC_RANGES.items():
            assert lo < hi, f"Range for '{key}' is invalid: lo={lo} >= hi={hi}"
