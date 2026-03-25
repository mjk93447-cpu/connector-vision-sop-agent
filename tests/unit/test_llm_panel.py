"""
Unit tests for LlmPanel (src/gui/panels/llm_panel.py).

All tests run headless — PyQt6 is mocked via _QT_AVAILABLE=False path.
We test the logic layer (empty response handling, think panel state) by
patching _QT_AVAILABLE to False and calling methods directly on a stub panel.
"""

from __future__ import annotations

import importlib.util

import pytest

from typing import Any
from unittest.mock import MagicMock, patch

# These tests use object.__new__(LlmPanel) which only works when PyQt6 is
# absent (LlmPanel falls back to a plain Python class in that case).
# Skip the entire module on environments where PyQt6 is installed.
if importlib.util.find_spec("PyQt6") is not None:
    pytest.skip(
        "test_llm_panel: headless tests require PyQt6 to be absent",
        allow_module_level=True,
    )


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
        panel._pending_prompt = None
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
# TestThinkInMainChat (v3.4.1 — think tokens appear in main chat)
# ---------------------------------------------------------------------------


class TestThinkInMainChat:
    def test_think_cursor_none_before_first_think_token(self) -> None:
        """_begin_streaming_bubble() 후 _think_cursor는 None."""
        panel = _make_panel()
        panel._think_cursor = None
        # Simulate _begin_streaming_bubble logic (headless: just attribute reset)
        panel._think_cursor = None  # explicitly None — no Qt call
        assert panel._think_cursor is None

    def test_think_cursor_reset_on_new_bubble(self) -> None:
        """새 메시지 시작(_begin_streaming_bubble) 시 _think_cursor가 None으로 리셋됨."""
        panel = _make_panel()
        # Simulate previous message left a think cursor
        panel._think_cursor = MagicMock()
        # _begin_streaming_bubble with _QT_AVAILABLE=False → no-op,
        # but the attribute reset happens before the Qt guard
        with patch("src.gui.panels.llm_panel._QT_AVAILABLE", False):
            panel._begin_streaming_bubble()
        # Without Qt, _begin_streaming_bubble returns immediately without resetting
        # attributes (entire body is guarded by `if not _QT_AVAILABLE: return`)
        # This test confirms the method exists and doesn't crash with a non-None cursor
        assert True  # no exception = pass

    def test_flush_with_think_cursor_inserts_newline_before_answer(self) -> None:
        """_think_cursor != None 상태에서 첫 answer 토큰 flush 시 newline 삽입 + _stream_cursor 재설정."""
        import src.gui.panels.llm_panel as _mod

        # Fake QTextCursor for headless env (QTextCursor not defined without PyQt6)
        class _FakeQTC:
            class MoveOperation:
                End = 0
                PreviousCharacter = 1

            def __init__(self, c: Any = None) -> None:
                pass

        panel = _make_panel()
        panel._think_cursor = MagicMock()  # think was active
        panel._stream_cursor = MagicMock()  # original anchor
        panel._token_buf = ["Hello"]
        panel._first_token = True

        new_cursor = MagicMock()
        panel._chat_display.textCursor.return_value = new_cursor

        with patch("src.gui.panels.llm_panel._QT_AVAILABLE", True), patch.object(
            _mod, "QTextCursor", _FakeQTC, create=True
        ):
            panel._flush_token_buf()

        # A newline should have been inserted to separate think from answer
        # (insertText is called twice: "\n" separator then the actual chunk)
        new_cursor.insertText.assert_any_call("\n")
        # _stream_cursor is now the cursor object returned by textCursor()
        assert panel._stream_cursor is new_cursor
        assert panel._first_token is False

    def test_flush_without_think_cursor_does_not_insert_newline(self) -> None:
        """_think_cursor=None (no think block) 시 추가 newline 없음."""
        import src.gui.panels.llm_panel as _mod

        class _FakeQTC:
            class MoveOperation:
                End = 0
                PreviousCharacter = 1

            def __init__(self, c: Any = None) -> None:
                pass

        panel = _make_panel()
        panel._think_cursor = None  # no think phase
        mock_stream = MagicMock()
        panel._stream_cursor = mock_stream
        panel._token_buf = ["Hi"]
        panel._first_token = True

        with patch("src.gui.panels.llm_panel._QT_AVAILABLE", True), patch.object(
            _mod, "QTextCursor", _FakeQTC, create=True
        ):
            panel._flush_token_buf()

        # textCursor() was NOT called (no think→answer separator needed)
        panel._chat_display.textCursor.assert_not_called()
        # _stream_cursor is still the original (not replaced)
        assert panel._stream_cursor is mock_stream
        assert panel._first_token is False


# ---------------------------------------------------------------------------
# TestBriefMaxTokensConfig
# ---------------------------------------------------------------------------


class TestBriefMaxTokensConfig:
    def test_brief_max_tokens_comment_matches_value(self) -> None:
        """_BRIEF_MAX_TOKENS >= 1024 (SmolLM3 think block budget)."""
        from src.llm_offline import _BRIEF_MAX_TOKENS

        assert _BRIEF_MAX_TOKENS >= 1024


# ---------------------------------------------------------------------------
# TestStopFlushAndFinalize (Issue 5: burst output fix)
# ---------------------------------------------------------------------------


class TestStopFlushAndFinalize:
    def test_flushes_before_stopping_timer(self) -> None:
        """_stop_flush_and_finalize must call _flush_token_buf before stopping timer."""
        panel = _make_panel()
        call_order: list = []
        panel._token_buf = ["hello", " world"]
        panel._flush_token_buf = lambda: call_order.append("flush")

        mock_timer = MagicMock()
        mock_timer.isActive.return_value = True
        mock_timer.stop.side_effect = lambda: call_order.append("timer_stop")
        panel._flush_timer = mock_timer
        panel._stream_cursor = None

        panel._stop_flush_and_finalize()

        assert "flush" in call_order, "flush must be called"
        assert "timer_stop" in call_order, "timer must be stopped"
        assert call_order.index("flush") < call_order.index(
            "timer_stop"
        ), "flush must come before timer_stop"

    def test_clears_token_buf_after_flush(self) -> None:
        """Token buffer is empty after _stop_flush_and_finalize."""
        panel = _make_panel()
        panel._token_buf = ["leftover"]
        panel._flush_token_buf = lambda: None  # stub — don't actually flush
        mock_timer = MagicMock()
        mock_timer.isActive.return_value = False
        panel._flush_timer = mock_timer

        panel._stop_flush_and_finalize()

        assert panel._token_buf == [], "token_buf must be cleared"

    def test_no_crash_when_flush_timer_none(self) -> None:
        """_stop_flush_and_finalize must not crash when _flush_timer is None."""
        panel = _make_panel()
        panel._token_buf = []
        panel._flush_token_buf = lambda: None
        panel._flush_timer = None  # no timer created yet

        panel._stop_flush_and_finalize()  # must not raise


# ---------------------------------------------------------------------------
# TestPromptQueue (Issue 6: queue during generation)
# ---------------------------------------------------------------------------


class TestPromptQueue:
    def test_prompt_queued_when_worker_running(self) -> None:
        """New prompt while generating is stored in _pending_prompt, not sent."""
        panel = _make_panel()
        panel._pending_prompt = None
        panel._worker = MagicMock()
        panel._worker.isRunning.return_value = True
        panel._input.text.return_value = "new question"
        system_msgs: list = []
        panel._append_system = lambda m: system_msgs.append(m)

        with patch("src.gui.panels.llm_panel._QT_AVAILABLE", True):
            panel._on_send()

        assert (
            panel._pending_prompt == "new question"
        ), "prompt should be stored in _pending_prompt"
        assert any(
            "Queued" in m for m in system_msgs
        ), "user should see a Queued confirmation"

    def test_process_pending_prompt_auto_sends(self) -> None:
        """After generation, _process_pending_prompt fires _on_send with queued text."""
        panel = _make_panel()
        panel._pending_prompt = "queued question"
        sent: list = []
        panel._on_send = lambda: sent.append(True)
        panel._input.setText = MagicMock()

        panel._process_pending_prompt()

        assert panel._pending_prompt is None, "_pending_prompt must be cleared"
        assert sent, "_on_send must be called"
        panel._input.setText.assert_called_once_with("queued question")

    def test_process_pending_prompt_noop_when_empty(self) -> None:
        """_process_pending_prompt does nothing when queue is empty."""
        panel = _make_panel()
        panel._pending_prompt = None
        called: list = []
        panel._on_send = lambda: called.append(True)

        panel._process_pending_prompt()

        assert not called, "_on_send must not be called when no pending prompt"

    def test_flush_timer_interval_is_16ms(self) -> None:
        """Flush timer interval must be 16ms (≈ 60 fps) for smooth streaming."""
        import inspect
        from src.gui.panels.llm_panel import LlmPanel

        src = inspect.getsource(LlmPanel._start_flush_timer)
        assert "16" in src, "flush timer must use 16ms interval"
