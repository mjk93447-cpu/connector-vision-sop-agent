"""
log_manager 단위 테스트.

LogManager의 이벤트 기록, 스크린샷 저장, 실행 요약, LLM 페이로드 빌드,
analyze_with_llm 스텁을 임시 디렉터리 기반으로 검증한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from src.log_manager import LogManager, LogEvent, RunSummary


# ---------------------------------------------------------------------------
# 이벤트 로깅
# ---------------------------------------------------------------------------


class TestLogEvents:
    def test_log_creates_event_in_memory(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        lm.log(step="login", message="clicked")
        assert len(lm.events) == 1
        assert lm.events[0].step == "login"
        assert lm.events[0].message == "clicked"

    def test_log_default_level_is_info(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        lm.log(step="x", message="msg")
        assert lm.events[0].level == "INFO"

    def test_log_custom_level(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        lm.log(step="x", message="msg", level="WARNING")
        assert lm.events[0].level == "WARNING"

    def test_log_error_shortcut(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        lm.log_error(step="login", message="not found")
        assert lm.events[0].level == "ERROR"

    def test_log_writes_jsonl_file(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        lm.log(step="step_a", message="hello")
        events_file = lm.run_dir / "events.jsonl"
        assert events_file.exists()
        line = events_file.read_text(encoding="utf-8").strip()
        data = json.loads(line)
        assert data["step"] == "step_a"
        assert data["message"] == "hello"

    def test_multiple_logs_appended_to_jsonl(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        lm.log(step="a", message="first")
        lm.log(step="b", message="second")
        lines = (lm.run_dir / "events.jsonl").read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2

    def test_log_extra_kwargs_stored_in_data(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        lm.log(step="x", message="test", coords=(100, 200), duration=0.5)
        assert lm.events[0].data["coords"] == (100, 200)  # in-memory: tuple 그대로 보존

    def test_run_dir_created_automatically(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="unique_run")
        assert lm.run_dir.exists()
        assert lm.run_dir.name == "unique_run"


# ---------------------------------------------------------------------------
# 스크린샷 저장
# ---------------------------------------------------------------------------


class TestSaveScreenshot:
    def test_numpy_array_saved_as_png(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        path = lm.save_screenshot(img, name="test_shot")
        assert path.exists()
        assert path.suffix == ".png"

    def test_pil_image_saved(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        pil_img = Image.new("RGB", (50, 50), color=(255, 0, 0))
        path = lm.save_screenshot(pil_img, name="pil_shot")
        assert path.exists()

    def test_auto_name_when_none(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        img = np.zeros((50, 50, 3), dtype=np.uint8)
        path = lm.save_screenshot(img)
        assert path.suffix == ".png"
        assert path.exists()

    def test_name_without_extension_gets_png(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        img = np.zeros((50, 50, 3), dtype=np.uint8)
        path = lm.save_screenshot(img, name="shot_no_ext")
        assert path.name == "shot_no_ext.png"

    def test_screenshot_recorded_in_list(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        img = np.zeros((50, 50, 3), dtype=np.uint8)
        path = lm.save_screenshot(img, name="tracked")
        assert path in lm.screenshots

    def test_screenshot_event_logged(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        img = np.zeros((50, 50, 3), dtype=np.uint8)
        lm.save_screenshot(img, name="ev_test")
        screenshot_events = [e for e in lm.events if e.step == "screenshot"]
        assert len(screenshot_events) == 1

    def test_grayscale_numpy_saved(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        gray = np.zeros((50, 50), dtype=np.uint8)
        path = lm.save_screenshot(gray, name="gray")
        assert path.exists()


# ---------------------------------------------------------------------------
# 실행 요약 (finalize)
# ---------------------------------------------------------------------------


class TestFinalize:
    def test_returns_run_summary(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        summary = lm.finalize(success=True)
        assert isinstance(summary, RunSummary)

    def test_success_flag_preserved(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        summary = lm.finalize(success=False)
        assert summary.success is False

    def test_error_field_stored(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        summary = lm.finalize(success=False, error="timeout")
        assert summary.error == "timeout"

    def test_summary_json_written(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        lm.finalize(success=True)
        summary_file = lm.run_dir / "summary.json"
        assert summary_file.exists()
        data = json.loads(summary_file.read_text(encoding="utf-8"))
        assert data["success"] is True

    def test_duration_positive(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        summary = lm.finalize(success=True)
        assert summary.duration_sec >= 0

    def test_run_id_in_summary(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="my_run")
        summary = lm.finalize(success=True)
        assert summary.run_id == "my_run"


# ---------------------------------------------------------------------------
# LLM 페이로드 빌드
# ---------------------------------------------------------------------------


class TestBuildLlmPayload:
    def test_payload_has_required_keys(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        payload = lm.build_llm_payload()
        assert "run_id" in payload
        assert "events_tail" in payload
        assert "screenshots" in payload
        assert "config_snapshot" in payload
        assert "generated_at" in payload

    def test_config_snapshot_included(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        payload = lm.build_llm_payload(config={"version": "test"})
        assert payload["config_snapshot"]["version"] == "test"

    def test_events_appear_in_payload(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        lm.log(step="login", message="ok")
        payload = lm.build_llm_payload()
        assert len(payload["events_tail"]) == 1

    def test_max_50_events_in_tail(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        for i in range(60):
            lm.log(step="step", message=f"event {i}")
        payload = lm.build_llm_payload()
        assert len(payload["events_tail"]) <= 50

    def test_empty_config_snapshot_when_none(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        payload = lm.build_llm_payload(config=None)
        assert payload["config_snapshot"] == {}

    def test_screenshot_paths_in_payload(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        img = np.zeros((50, 50, 3), dtype=np.uint8)
        lm.save_screenshot(img, name="cap")
        payload = lm.build_llm_payload()
        assert len(payload["screenshots"]) == 1

    def test_summary_included_if_finalized(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        lm.finalize(success=True)
        payload = lm.build_llm_payload()
        assert payload["summary"].get("success") is True


# ---------------------------------------------------------------------------
# analyze_with_llm (스텁 경로)
# ---------------------------------------------------------------------------


class TestAnalyzeWithLlm:
    def test_disabled_returns_stub(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        result = lm.analyze_with_llm(config={"llm": {"enabled": False}})
        assert result["config_patch"] == {}
        assert result["sop_recommendations"] == []
        assert "LLM disabled" in result["note"]

    def test_no_config_returns_stub(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        result = lm.analyze_with_llm(config=None)
        assert result["config_patch"] == {}
        assert "note" in result

    def test_no_llm_block_returns_stub(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        result = lm.analyze_with_llm(config={"version": "1.0"})
        assert result["config_patch"] == {}

    def test_result_always_has_contract_keys(self, tmp_path: Path) -> None:
        lm = LogManager(base_dir=tmp_path, run_id="r1")
        result = lm.analyze_with_llm(config=None)
        required = {"model", "payload", "config_patch", "sop_recommendations", "raw_text", "note"}
        assert required.issubset(result.keys())
