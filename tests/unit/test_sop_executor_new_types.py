"""
Unit tests for v3.9 new SOP step types:
  - wait_ms   : pause N milliseconds (always succeeds)
  - type_text : standalone type_text without preceding click
  - press_key : standalone key press (Return, Tab, ctrl+a, etc.)

These tests use mocked vision/control so no display or YOLO model is needed.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.sop_executor import SopExecutor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_executor(tmp_path: Path) -> SopExecutor:
    """SopExecutor with mocked vision/control, no sop_steps.json."""
    vision = MagicMock()
    control = MagicMock()
    # type_text / press_key return successful ControlResult-like mocks by default
    ok_type = MagicMock(success=True, duration=0.01, error=None)
    ok_key = MagicMock(success=True, duration=0.005, error=None)
    control.type_text.return_value = ok_type
    control.press_key.return_value = ok_key
    return SopExecutor(
        vision=vision,
        control=control,
        sop_steps_path=tmp_path / "nonexistent_sop_steps.json",
    )


# ---------------------------------------------------------------------------
# wait_ms step type
# ---------------------------------------------------------------------------


class TestWaitMsStep:
    """wait_ms steps must pause and always succeed."""

    def test_wait_ms_success(self, tmp_path: Path) -> None:
        ex = _make_executor(tmp_path)
        with patch("time.sleep") as mock_sleep:
            ok, msg = ex.run_step(
                {"id": "w1", "name": "Wait", "type": "wait_ms", "ms": 500}
            )
        assert ok is True
        assert "500" in msg
        mock_sleep.assert_called_once_with(0.5)

    def test_wait_ms_zero(self, tmp_path: Path) -> None:
        ex = _make_executor(tmp_path)
        with patch("time.sleep") as mock_sleep:
            ok, msg = ex.run_step(
                {"id": "w0", "name": "Wait0", "type": "wait_ms", "ms": 0}
            )
        assert ok is True
        mock_sleep.assert_called_once_with(0.0)

    def test_wait_ms_default_500_when_ms_missing(self, tmp_path: Path) -> None:
        ex = _make_executor(tmp_path)
        with patch("time.sleep") as mock_sleep:
            ok, _ = ex.run_step({"id": "wd", "name": "WaitD", "type": "wait_ms"})
        assert ok is True
        mock_sleep.assert_called_once_with(0.5)

    def test_wait_ms_large_value(self, tmp_path: Path) -> None:
        ex = _make_executor(tmp_path)
        with patch("time.sleep") as mock_sleep:
            ok, msg = ex.run_step(
                {"id": "wl", "name": "WaitL", "type": "wait_ms", "ms": 2000}
            )
        assert ok is True
        assert "2000" in msg
        mock_sleep.assert_called_once_with(2.0)


# ---------------------------------------------------------------------------
# type_text step type (standalone — no preceding click)
# ---------------------------------------------------------------------------


class TestTypeTextStep:
    """type_text step delegates to control.type_text()."""

    def test_type_text_success(self, tmp_path: Path) -> None:
        ex = _make_executor(tmp_path)
        ok, msg = ex.run_step(
            {"id": "t1", "name": "Type PW", "type": "type_text", "text": "1111"}
        )
        assert ok is True
        assert "1111" in msg
        ex.control.type_text.assert_called_once_with("1111", clear_first=False)

    def test_type_text_with_clear_first(self, tmp_path: Path) -> None:
        ex = _make_executor(tmp_path)
        ex.run_step(
            {
                "id": "t2",
                "name": "Type PW Clear",
                "type": "type_text",
                "text": "hello",
                "clear_first": True,
            }
        )
        ex.control.type_text.assert_called_once_with("hello", clear_first=True)

    def test_type_text_failure(self, tmp_path: Path) -> None:
        ex = _make_executor(tmp_path)
        fail_result = MagicMock(success=False, duration=0.0, error="keyboard blocked")
        ex.control.type_text.return_value = fail_result
        ok, msg = ex.run_step(
            {"id": "tf", "name": "Type Fail", "type": "type_text", "text": "abc"}
        )
        assert ok is False
        assert "keyboard blocked" in msg

    def test_type_text_empty_string(self, tmp_path: Path) -> None:
        ex = _make_executor(tmp_path)
        ok, _ = ex.run_step(
            {"id": "te", "name": "Type Empty", "type": "type_text", "text": ""}
        )
        assert ok is True
        ex.control.type_text.assert_called_once_with("", clear_first=False)

    def test_type_text_default_empty_when_text_missing(self, tmp_path: Path) -> None:
        ex = _make_executor(tmp_path)
        ok, _ = ex.run_step({"id": "tm", "name": "Type Miss", "type": "type_text"})
        assert ok is True
        ex.control.type_text.assert_called_once_with("", clear_first=False)


# ---------------------------------------------------------------------------
# press_key step type (standalone)
# ---------------------------------------------------------------------------


class TestPressKeyStep:
    """press_key step delegates to control.press_key()."""

    def test_press_key_return(self, tmp_path: Path) -> None:
        ex = _make_executor(tmp_path)
        ok, msg = ex.run_step(
            {"id": "k1", "name": "Press Enter", "type": "press_key", "key": "Return"}
        )
        assert ok is True
        assert "Return" in msg
        ex.control.press_key.assert_called_once_with("Return")

    def test_press_key_tab(self, tmp_path: Path) -> None:
        ex = _make_executor(tmp_path)
        ok, _ = ex.run_step(
            {"id": "k2", "name": "Press Tab", "type": "press_key", "key": "Tab"}
        )
        assert ok is True
        ex.control.press_key.assert_called_once_with("Tab")

    def test_press_key_default_return_when_key_missing(self, tmp_path: Path) -> None:
        ex = _make_executor(tmp_path)
        ok, _ = ex.run_step({"id": "km", "name": "Press Default", "type": "press_key"})
        assert ok is True
        ex.control.press_key.assert_called_once_with("Return")

    def test_press_key_failure(self, tmp_path: Path) -> None:
        ex = _make_executor(tmp_path)
        fail_result = MagicMock(success=False, duration=0.0, error="not available")
        ex.control.press_key.return_value = fail_result
        ok, msg = ex.run_step(
            {"id": "kf", "name": "Press Fail", "type": "press_key", "key": "Escape"}
        )
        assert ok is False
        assert "not available" in msg

    def test_press_key_hotkey_combo(self, tmp_path: Path) -> None:
        ex = _make_executor(tmp_path)
        ok, msg = ex.run_step(
            {"id": "kh", "name": "Select All", "type": "press_key", "key": "ctrl+a"}
        )
        assert ok is True
        assert "ctrl+a" in msg
        ex.control.press_key.assert_called_once_with("ctrl+a")


# ---------------------------------------------------------------------------
# Unknown step type (regression guard)
# ---------------------------------------------------------------------------


class TestUnknownStepType:
    def test_unknown_type_returns_failure(self, tmp_path: Path) -> None:
        ex = _make_executor(tmp_path)
        ok, msg = ex.run_step({"id": "u1", "name": "Unknown", "type": "teleport"})
        assert ok is False
        assert "teleport" in msg or "Unknown" in msg
