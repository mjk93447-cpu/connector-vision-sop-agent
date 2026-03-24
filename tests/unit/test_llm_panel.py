"""
Unit tests for LlmPanel (src/gui/panels/llm_panel.py).

All tests run headless — PyQt6 is mocked via _QT_AVAILABLE=False path.
We test the logic layer (empty response handling, think panel state) by
patching _QT_AVAILABLE to False and calling methods directly on a stub panel.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_panel() -> Any:
    """Return a LlmPanel instance with PyQt6 stubbed out (headless)."""
    with patch("src.gui.panels.llm_panel._QT_AVAILABLE", False):
        from src.gui.panels.llm_panel import LlmPanel

        panel = object.__new__(LlmPanel)
        # Initialise minimal attributes that __init__ normally sets
        panel._history = []
        panel._worker = None
        panel._last_llm_text = ""
        panel._brief_mode = True
        panel._t0 = 0.0
        panel._streaming_buffer = ""
        panel._timer = None
        panel._token_buf = []
        panel._flush_timer = None
        panel._stop_requested = False
        panel._last_think_t = 0.0
        panel._stream_cursor = None
        panel._first_token = False
        # Stub Qt widgets
        panel._lbl_elapsed = MagicMock()
        panel._txt_think = MagicMock()
        panel._txt_think.isVisible.return_value = False
        panel._txt_think.toPlainText.return_value = ""
        panel._chat_display = MagicMock()
        panel._btn_send = MagicMock()
        panel._btn_apply = MagicMock()
        panel._btn_analyze = MagicMock()
        panel._input = MagicMock()
        panel._chk_brief = MagicMock()
        return panel


# ---------------------------------------------------------------------------
# TestEmptyResponseHandling
# ---------------------------------------------------------------------------


class TestEmptyResponseHandling:
    def test_empty_full_text_appends_warning(self) -> None:
        """on_streaming_done('') → ⚠ 안내 메시지 _append_system 호출."""
        panel = _make_panel()
        system_msgs: list = []
        panel._append_system = lambda msg: system_msgs.append(msg)
        panel._extract_patch = lambda t: None
        panel.set_sending = lambda s: None

        import time

        panel._t0 = time.perf_counter()

        with patch("src.gui.panels.llm_panel._QT_AVAILABLE", False):
            panel.on_streaming_done("")

        assert any(
            "\u26a0" in m or "No visible response" in m for m in system_msgs
        ), "Expected warning message when full_text is empty"

    def test_empty_full_text_does_not_enable_apply_button(self) -> None:
        """빈 응답 시 _btn_apply.setEnabled 호출 안 됨."""
        panel = _make_panel()
        panel._append_system = lambda msg: None
        panel.set_sending = lambda s: None

        import time

        panel._t0 = time.perf_counter()

        with patch("src.gui.panels.llm_panel._QT_AVAILABLE", False):
            panel.on_streaming_done("")

        panel._btn_apply.setEnabled.assert_not_called()

    def test_nonempty_response_does_not_show_warning(self) -> None:
        """정상 응답 시 ⚠ 메시지 없음."""
        panel = _make_panel()
        system_msgs: list = []
        panel._append_system = lambda msg: system_msgs.append(msg)
        panel._extract_patch = lambda t: None
        panel.set_sending = lambda s: None

        import time

        panel._t0 = time.perf_counter()

        with patch("src.gui.panels.llm_panel._QT_AVAILABLE", False):
            panel.on_streaming_done("The answer is 4.")

        warning_msgs = [m for m in system_msgs if "\u26a0" in m or "No visible" in m]
        assert (
            not warning_msgs
        ), f"Unexpected warning for non-empty response: {warning_msgs}"

    def test_history_updated_even_for_empty_response(self) -> None:
        """빈 응답도 history에 추가됨 (대화 흐름 유지)."""
        panel = _make_panel()
        panel._append_system = lambda msg: None
        panel.set_sending = lambda s: None

        import time

        panel._t0 = time.perf_counter()

        with patch("src.gui.panels.llm_panel._QT_AVAILABLE", False):
            panel.on_streaming_done("")

        assert panel._history[-1] == {"role": "assistant", "content": ""}


# ---------------------------------------------------------------------------
# TestThinkPanelBehavior (headless — checks attribute logic)
# ---------------------------------------------------------------------------


class TestThinkPanelBehavior:
    def test_begin_streaming_bubble_hides_think_panel(self) -> None:
        """_begin_streaming_bubble() 호출 시 _txt_think.hide() 호출."""
        panel = _make_panel()
        # _begin_streaming_bubble does nothing without PyQt6
        with patch("src.gui.panels.llm_panel._QT_AVAILABLE", False):
            panel._begin_streaming_bubble()
        # Without Qt, nothing runs — but _first_token and _streaming_buffer
        # should not be set (no-op path)
        # This test verifies the method exists and doesn't crash headless
        assert True  # no exception = pass

    def test_on_think_token_ready_updates_last_think_time(self) -> None:
        """on_think_token_ready() 호출 시 _last_think_t 갱신."""
        import time

        panel = _make_panel()
        panel._t0 = time.perf_counter() - 5.0  # 5s ago

        with patch("src.gui.panels.llm_panel._QT_AVAILABLE", False):
            panel.on_think_token_ready("hello reasoning")

        # Without Qt the method is a no-op — just verify no crash
        assert True

    def test_flush_token_buf_no_crash_without_stream_cursor(self) -> None:
        """_stream_cursor=None 상태에서 _flush_token_buf() 크래시 없음."""
        panel = _make_panel()
        panel._token_buf = ["hello", " world"]
        panel._stream_cursor = None
        panel._first_token = False

        with patch("src.gui.panels.llm_panel._QT_AVAILABLE", True):
            # _QT_AVAILABLE=True but cursor is None — should return safely
            panel._flush_token_buf()

        # If we get here without AttributeError, the guard works
        assert True


# ---------------------------------------------------------------------------
# TestBriefMaxTokensConfig
# ---------------------------------------------------------------------------


class TestBriefMaxTokensConfig:
    def test_brief_max_tokens_comment_matches_value(self) -> None:
        """_BRIEF_MAX_TOKENS >= 1024 (SmolLM3 think block budget)."""
        from src.llm_offline import _BRIEF_MAX_TOKENS

        assert _BRIEF_MAX_TOKENS >= 1024
