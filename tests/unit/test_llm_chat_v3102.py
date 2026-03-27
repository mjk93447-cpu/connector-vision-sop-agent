"""
v3.10.2 LLM Chat 개선 사항 단위 테스트.

검증 범위:
  1. 이미지 최적화 — _on_roi_selected() JPEG 압축 + 800px 리사이즈
  2. ROI 오버레이 — _RoiScreenshotOverlay 시그니처 및 클래스 존재 확인
  3. ChatGPT-like UI — token_count 추적, has_warm_llm 플래그, ETA 텍스트
  4. Stop/Cancel — _on_stop_requested() 및 _remove_partial_bubble() 소스 검증
  5. Workers/LLM timeout — 600s 설정 확인
"""

from __future__ import annotations

import importlib
import inspect
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_llm_panel():
    return importlib.import_module("src.gui.panels.llm_panel")


def _load_workers():
    return importlib.import_module("src.gui.workers")


def _load_llm_offline():
    return importlib.import_module("src.llm_offline")


# ---------------------------------------------------------------------------
# 1. ROI Overlay — class exists with required signals and methods
# ---------------------------------------------------------------------------


class TestRoiScreenshotOverlay:
    def test_class_exists(self) -> None:
        mod = _load_llm_panel()
        assert hasattr(
            mod, "_RoiScreenshotOverlay"
        ), "_RoiScreenshotOverlay class not found in llm_panel"

    def test_has_roi_selected_signal(self) -> None:
        mod = _load_llm_panel()
        cls = mod._RoiScreenshotOverlay
        assert hasattr(cls, "roi_selected"), "roi_selected signal missing"

    def test_has_cancelled_signal(self) -> None:
        mod = _load_llm_panel()
        cls = mod._RoiScreenshotOverlay
        assert hasattr(cls, "cancelled"), "cancelled signal missing"

    def test_has_paint_event(self) -> None:
        mod = _load_llm_panel()
        cls = mod._RoiScreenshotOverlay
        assert hasattr(cls, "paintEvent"), "paintEvent missing"

    def test_has_mouse_press_event(self) -> None:
        mod = _load_llm_panel()
        cls = mod._RoiScreenshotOverlay
        assert hasattr(cls, "mousePressEvent")

    def test_has_mouse_release_event(self) -> None:
        mod = _load_llm_panel()
        cls = mod._RoiScreenshotOverlay
        assert hasattr(cls, "mouseReleaseEvent")


# ---------------------------------------------------------------------------
# 2. LlmPanel — new fields and ROI methods exist
# ---------------------------------------------------------------------------


class TestLlmPanelNewFields:
    def test_token_count_field_in_init_source(self) -> None:
        mod = _load_llm_panel()
        src = inspect.getsource(mod.LlmPanel.__init__)
        assert "_token_count" in src, "_token_count field missing from __init__"

    def test_has_warm_llm_field_in_init_source(self) -> None:
        mod = _load_llm_panel()
        src = inspect.getsource(mod.LlmPanel.__init__)
        assert "_has_warm_llm" in src, "_has_warm_llm field missing from __init__"

    def test_bubble_start_pos_field_in_init_source(self) -> None:
        mod = _load_llm_panel()
        src = inspect.getsource(mod.LlmPanel.__init__)
        assert "_bubble_start_pos" in src, "_bubble_start_pos field missing"

    def test_roi_overlay_field_in_init_source(self) -> None:
        mod = _load_llm_panel()
        src = inspect.getsource(mod.LlmPanel.__init__)
        assert "_roi_overlay" in src

    def test_show_roi_overlay_method_exists(self) -> None:
        mod = _load_llm_panel()
        assert hasattr(mod.LlmPanel, "_show_roi_overlay")

    def test_on_roi_selected_method_exists(self) -> None:
        mod = _load_llm_panel()
        assert hasattr(mod.LlmPanel, "_on_roi_selected")

    def test_on_roi_cancelled_method_exists(self) -> None:
        mod = _load_llm_panel()
        assert hasattr(mod.LlmPanel, "_on_roi_cancelled")

    def test_on_stop_requested_method_exists(self) -> None:
        mod = _load_llm_panel()
        assert hasattr(mod.LlmPanel, "_on_stop_requested")

    def test_remove_partial_bubble_method_exists(self) -> None:
        mod = _load_llm_panel()
        assert hasattr(mod.LlmPanel, "_remove_partial_bubble")


# ---------------------------------------------------------------------------
# 3. Stop button — _on_send delegates to _on_stop_requested when Stop mode
# ---------------------------------------------------------------------------


class TestStopButtonLogic:
    def test_on_send_checks_stop_button_text(self) -> None:
        """_on_send() must check for '⏹ Stop' and delegate to _on_stop_requested."""
        mod = _load_llm_panel()
        src = inspect.getsource(mod.LlmPanel._on_send)
        assert "⏹ Stop" in src, "_on_send must check for '⏹ Stop' button text"
        assert "_on_stop_requested" in src

    def test_on_stop_requested_calls_stop_on_worker(self) -> None:
        mod = _load_llm_panel()
        src = inspect.getsource(mod.LlmPanel._on_stop_requested)
        assert (
            "stop_fn" in src or "stop()" in src or ".stop" in src
        ), "_on_stop_requested must call worker.stop()"

    def test_remove_partial_bubble_uses_bubble_start_pos(self) -> None:
        mod = _load_llm_panel()
        src = inspect.getsource(mod.LlmPanel._remove_partial_bubble)
        assert "_bubble_start_pos" in src

    def test_begin_streaming_bubble_saves_start_pos(self) -> None:
        mod = _load_llm_panel()
        src = inspect.getsource(mod.LlmPanel._begin_streaming_bubble)
        assert "_bubble_start_pos" in src


# ---------------------------------------------------------------------------
# 4. Token count tracking
# ---------------------------------------------------------------------------


class TestTokenCountTracking:
    def test_on_token_ready_increments_count(self) -> None:
        mod = _load_llm_panel()
        src = inspect.getsource(mod.LlmPanel.on_token_ready)
        assert "_token_count" in src

    def test_tick_timer_shows_token_count(self) -> None:
        mod = _load_llm_panel()
        src = inspect.getsource(mod.LlmPanel._tick_timer)
        assert "_token_count" in src, "_tick_timer must show token count"
        assert "token_info" in src or "tokens" in src

    def test_set_sending_resets_token_count(self) -> None:
        mod = _load_llm_panel()
        src = inspect.getsource(mod.LlmPanel.set_sending)
        assert "_token_count = 0" in src

    def test_streaming_done_sets_warm_flag(self) -> None:
        mod = _load_llm_panel()
        src = inspect.getsource(mod.LlmPanel.on_streaming_done)
        assert "_has_warm_llm" in src

    def test_set_sending_shows_eta_based_on_warm_flag(self) -> None:
        mod = _load_llm_panel()
        src = inspect.getsource(mod.LlmPanel.set_sending)
        assert "_has_warm_llm" in src, "set_sending must branch on _has_warm_llm"


# ---------------------------------------------------------------------------
# 5. ROI image capture — JPEG compression and resize source verification
# ---------------------------------------------------------------------------


class TestRoiImageCapture:
    def test_on_roi_selected_uses_pillow(self) -> None:
        mod = _load_llm_panel()
        src = inspect.getsource(mod.LlmPanel._on_roi_selected)
        assert (
            "PIL" in src or "Image" in src
        ), "_on_roi_selected must use Pillow for JPEG compression"

    def test_on_roi_selected_resizes_to_max_800(self) -> None:
        mod = _load_llm_panel()
        src = inspect.getsource(mod.LlmPanel._on_roi_selected)
        assert "800" in src, "max_dim=800 must be in _on_roi_selected"

    def test_on_roi_selected_uses_jpeg(self) -> None:
        mod = _load_llm_panel()
        src = inspect.getsource(mod.LlmPanel._on_roi_selected)
        assert "JPEG" in src

    def test_on_roi_selected_uses_quality_80(self) -> None:
        mod = _load_llm_panel()
        src = inspect.getsource(mod.LlmPanel._on_roi_selected)
        assert "quality=80" in src

    def test_on_roi_selected_mock_capture(self) -> None:
        """Integration: _on_roi_selected with mocked mss + PIL stores base64 JPEG."""
        import base64
        import sys
        import types

        mod = _load_llm_panel()

        # Build a minimal stub
        class _Stub:
            _on_roi_selected = mod.LlmPanel._on_roi_selected
            _pending_image_b64: object = None

            def _append_system(self, msg: str) -> None:
                self._last_sys_msg = msg

            def window(self):
                return None

        stub = _Stub()

        # Create a small fake RGB image (40×30 red)
        from PIL import Image  # noqa: PLC0415

        fake_pil = Image.new("RGB", (40, 30), color=(255, 0, 0))
        fake_raw = MagicMock()
        fake_raw.size = (40, 30)
        fake_raw.rgb = fake_pil.tobytes()

        mock_sct_ctx = MagicMock()
        mock_sct_ctx.__enter__ = lambda s: s
        mock_sct_ctx.__exit__ = MagicMock(return_value=False)
        mock_sct_ctx.grab.return_value = fake_raw

        # Inject mock mss module so the import inside _on_roi_selected works
        mock_mss_mod = types.ModuleType("mss")
        mock_mss_mod.mss = MagicMock(return_value=mock_sct_ctx)  # type: ignore[attr-defined]

        with patch.dict(sys.modules, {"mss": mock_mss_mod}):
            stub._on_roi_selected(0, 0, 40, 30)

        assert stub._pending_image_b64 is not None, "base64 not set after roi_selected"
        decoded = base64.b64decode(stub._pending_image_b64)
        assert decoded[:2] == b"\xff\xd8", "output must be JPEG"


# ---------------------------------------------------------------------------
# 6. Timeout values
# ---------------------------------------------------------------------------


class TestTimeoutValues:
    def test_stream_worker_timeout_is_600(self) -> None:
        mod = _load_workers()
        assert (
            mod.LLMStreamWorker._STREAM_TIMEOUT_SECS == 600
        ), "_STREAM_TIMEOUT_SECS must be 600 for v3.10.2"

    def test_llm_offline_read_timeout_is_600(self) -> None:
        mod = _load_llm_offline()
        src = inspect.getsource(mod.OfflineLLM._stream_ollama)
        assert "600" in src, "_stream_ollama read timeout must be 600s"
        # And the old 180 value should NOT appear as the read timeout
        assert "timeout=(10, 180)" not in src, "old 180s timeout still present"
