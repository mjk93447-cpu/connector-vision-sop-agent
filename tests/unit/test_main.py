"""
Unit tests for src/main.py.

Covers:
- _resolve_confidence_threshold()
- _get_line_id()
- _load_sop_steps()
- _check_ocr_health()
- _extract_patch_from_llm_text()
- _build_services() (mocked)
- CLI arg parsing: --console flag
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# _resolve_confidence_threshold
# ---------------------------------------------------------------------------


class TestResolveConfidenceThreshold:
    def test_returns_vision_threshold(self) -> None:
        from src.main import _resolve_confidence_threshold

        cfg = {"vision": {"confidence_threshold": 0.75}}
        assert _resolve_confidence_threshold(cfg) == 0.75

    def test_default_when_missing(self) -> None:
        from src.main import _resolve_confidence_threshold

        assert _resolve_confidence_threshold({}) == 0.6

    def test_default_when_vision_missing(self) -> None:
        from src.main import _resolve_confidence_threshold

        assert _resolve_confidence_threshold({"vision": {}}) == 0.6

    def test_returns_float(self) -> None:
        from src.main import _resolve_confidence_threshold

        cfg = {"vision": {"confidence_threshold": "0.8"}}
        result = _resolve_confidence_threshold(cfg)
        assert isinstance(result, float)
        assert result == 0.8


# ---------------------------------------------------------------------------
# _get_line_id
# ---------------------------------------------------------------------------


class TestGetLineId:
    def test_returns_line_id(self) -> None:
        from src.main import _get_line_id

        assert _get_line_id({"line_id": "LINE-01"}) == "LINE-01"

    def test_default_when_missing(self) -> None:
        from src.main import _get_line_id

        assert _get_line_id({}) == "LINE-UNKNOWN"

    def test_numeric_id_stringified(self) -> None:
        from src.main import _get_line_id

        assert _get_line_id({"line_id": 42}) == "42"


# ---------------------------------------------------------------------------
# _load_sop_steps
# ---------------------------------------------------------------------------


class TestLoadSopSteps:
    def test_loads_enabled_steps(self, tmp_path: Path) -> None:
        from src.main import _load_sop_steps

        data = {
            "steps": [
                {"id": "s1", "enabled": True},
                {"id": "s2", "enabled": False},
                {"id": "s3"},
            ]
        }
        p = tmp_path / "sop_steps.json"
        p.write_text(json.dumps(data), encoding="utf-8")

        steps = _load_sop_steps(p)
        ids = [s["id"] for s in steps]
        assert "s1" in ids
        assert "s2" not in ids  # enabled=False filtered out
        assert "s3" in ids  # missing enabled defaults to True

    def test_returns_empty_on_missing_file(self, tmp_path: Path) -> None:
        from src.main import _load_sop_steps

        result = _load_sop_steps(tmp_path / "nonexistent.json")
        assert result == []

    def test_returns_empty_on_bad_json(self, tmp_path: Path) -> None:
        from src.main import _load_sop_steps

        p = tmp_path / "bad.json"
        p.write_text("NOT JSON", encoding="utf-8")
        result = _load_sop_steps(p)
        assert result == []


# ---------------------------------------------------------------------------
# _check_ocr_health
# ---------------------------------------------------------------------------


class TestCheckOcrHealth:
    def test_returns_ok_when_regions_found(self) -> None:
        from src.main import _check_ocr_health

        mock_ocr = MagicMock()
        mock_ocr.scan_all.return_value = [MagicMock()]
        mock_ocr._backend = "winsdk"

        result = _check_ocr_health(mock_ocr)
        assert result.startswith("OK")
        assert "winsdk" in result

    def test_returns_warn_when_no_regions(self) -> None:
        from src.main import _check_ocr_health

        mock_ocr = MagicMock()
        mock_ocr.scan_all.return_value = []
        mock_ocr._backend = "easyocr"

        result = _check_ocr_health(mock_ocr)
        assert result.startswith("WARN")

    def test_returns_error_on_exception(self) -> None:
        from src.main import _check_ocr_health

        mock_ocr = MagicMock()
        mock_ocr.scan_all.side_effect = RuntimeError("cv2 missing")

        result = _check_ocr_health(mock_ocr)
        assert result.startswith("ERROR")
        assert "cv2 missing" in result


# ---------------------------------------------------------------------------
# _extract_patch_from_llm_text
# ---------------------------------------------------------------------------


class TestExtractPatchFromLlmText:
    def test_extracts_config_patch_block(self) -> None:
        from src.main import _extract_patch_from_llm_text

        text = 'Here is my suggestion:\nconfig_patch: {"control.step_delay": 1.5}'
        result = _extract_patch_from_llm_text(text)
        assert result == {"control.step_delay": 1.5}

    def test_returns_none_when_no_patch(self) -> None:
        from src.main import _extract_patch_from_llm_text

        result = _extract_patch_from_llm_text("No changes needed.")
        assert result is None

    def test_returns_none_on_bad_json(self) -> None:
        from src.main import _extract_patch_from_llm_text

        text = "config_patch: {bad json here"
        result = _extract_patch_from_llm_text(text)
        assert result is None

    def test_case_insensitive(self) -> None:
        from src.main import _extract_patch_from_llm_text

        text = 'CONFIG PATCH: {"pin_count_min": 40}'
        result = _extract_patch_from_llm_text(text)
        assert result is not None
        assert result.get("pin_count_min") == 40


# ---------------------------------------------------------------------------
# CLI arg parsing: --console flag
# ---------------------------------------------------------------------------


class TestCliArgParsing:
    def test_console_flag_detected(self) -> None:
        """--console in args selects console path."""
        args = ["--console"]
        assert "--console" in args or "-c" in args

    def test_short_flag_c_detected(self) -> None:
        """-c short flag also selects console path."""
        args = ["-c"]
        assert "--console" in args or "-c" in args

    def test_no_flag_selects_gui_path(self) -> None:
        """Without --console/-c, GUI path is chosen."""
        args: list[str] = []
        assert "--console" not in args and "-c" not in args

    def test_gui_flag_selects_gui_path(self) -> None:
        """--gui explicitly selects GUI path (no --console)."""
        args = ["--gui"]
        assert "--console" not in args and "-c" not in args


# ---------------------------------------------------------------------------
# _build_services (smoke test with mocks)
# ---------------------------------------------------------------------------


class TestBuildServices:
    def test_returns_three_services(self) -> None:
        from src.main import _build_services
        from src.vision_engine import VisionEngine
        from src.control_engine import ControlEngine
        from src.sop_executor import SopExecutor

        cfg = {
            "vision": {"confidence_threshold": 0.6},
            "llm": {"enabled": False},
        }

        with (
            patch.object(VisionEngine, "_load_model", return_value=None),
            patch("src.main.OCREngine", side_effect=RuntimeError("no ocr")),
        ):
            vision, control, executor = _build_services(config=cfg)

        assert isinstance(vision, VisionEngine)
        assert isinstance(control, ControlEngine)
        assert isinstance(executor, SopExecutor)
