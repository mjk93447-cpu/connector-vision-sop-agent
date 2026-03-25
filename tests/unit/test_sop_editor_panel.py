"""
Unit tests for _RoiOverlayWindow coordinate logic (v3.7.0).

Tests use object.__new__ to bypass Qt initialization — pure Python coordinate
math is tested without a display server.
"""

from __future__ import annotations

import importlib.util
from typing import Any

import pytest

# object.__new__(_RoiOverlayWindow) is only safe when PyQt6 is absent
# (QWidget becomes plain `object`).  Skip entire module when PyQt6 is installed.
if importlib.util.find_spec("PyQt6") is not None:
    pytest.skip(
        "test_sop_editor_panel: headless tests require PyQt6 to be absent"
        " — object.__new__ incompatible with C++ extension classes",
        allow_module_level=True,
    )


class _FakePos:
    """Minimal QPoint stub for headless coordinate testing."""

    def __init__(self, x: int, y: int) -> None:
        self._x, self._y = x, y

    def x(self) -> int:
        return self._x

    def y(self) -> int:
        return self._y


def _make_stub() -> Any:
    """Build a _RoiOverlayWindow stub without Qt — pure coordinate logic only."""
    from src.gui.panels.sop_editor_panel import _RoiOverlayWindow  # noqa: PLC0415

    d = object.__new__(_RoiOverlayWindow)
    d._click_start = None
    d._hover_pos = None
    d._roi = None
    d._closed = False
    d._confirm_panel = None
    # Stub Qt-dependent methods
    d._show_confirm_panel = lambda: None
    # Stub _to_global: overlay at origin → local coords == global coords
    d._to_global = lambda pos: pos
    return d


# ---------------------------------------------------------------------------
# Click-move-click state machine
# ---------------------------------------------------------------------------


class TestHandlePressStateMachine:
    def test_first_click_sets_click_start(self) -> None:
        """First _handle_press call must set _click_start."""
        d = _make_stub()
        d._handle_press(_FakePos(100, 100))
        assert d._click_start is not None

    def test_first_click_does_not_set_roi(self) -> None:
        """First click must NOT compute ROI."""
        d = _make_stub()
        d._handle_press(_FakePos(100, 100))
        assert d._roi is None

    def test_second_click_clears_click_start(self) -> None:
        """After second click, _click_start resets to None."""
        d = _make_stub()
        d._handle_press(_FakePos(100, 100))
        d._handle_press(_FakePos(200, 200))
        assert d._click_start is None

    def test_second_click_sets_roi(self) -> None:
        """Second click must produce a non-None ROI."""
        d = _make_stub()
        d._handle_press(_FakePos(130, 120))
        d._handle_press(_FakePos(230, 220))
        assert d._roi is not None

    def test_third_click_starts_new_selection(self) -> None:
        """Third click after a completed selection must start a new selection."""
        d = _make_stub()
        d._handle_press(_FakePos(10, 10))
        d._handle_press(_FakePos(50, 50))
        d._handle_press(_FakePos(100, 100))
        assert d._click_start is not None
        assert d._roi is not None  # previous ROI present until overwritten


# ---------------------------------------------------------------------------
# Coordinate conversion — 1:1 overlay (no scale, no centering offset)
# ---------------------------------------------------------------------------


class TestComputeRoiOverlay:
    def test_roi_direct_coordinates(self) -> None:
        """Overlay is 1:1 with screen — coordinates map directly."""
        d = _make_stub()
        d._handle_press(_FakePos(130, 120))
        d._handle_press(_FakePos(230, 220))
        assert d._roi == (130, 120, 100, 100)

    def test_reversed_click_order(self) -> None:
        """Clicking bottom-right first then top-left must yield same positive roi."""
        d = _make_stub()
        d._handle_press(_FakePos(230, 220))
        d._handle_press(_FakePos(130, 120))
        assert d._roi == (130, 120, 100, 100)

    def test_roi_at_origin(self) -> None:
        """Click at (0,0) must map to screen coordinate (0,0)."""
        d = _make_stub()
        d._handle_press(_FakePos(0, 0))
        d._handle_press(_FakePos(100, 80))
        assert d._roi == (0, 0, 100, 80)

    def test_roi_width_height_are_positive(self) -> None:
        """Width and height must always be non-negative."""
        d = _make_stub()
        d._handle_press(_FakePos(500, 400))
        d._handle_press(_FakePos(100, 100))
        _, _, w, h = d._roi
        assert w >= 0 and h >= 0


# ---------------------------------------------------------------------------
# Cancel state machine
# ---------------------------------------------------------------------------


class TestCancelBehavior:
    def test_cancel_clears_click_start(self) -> None:
        """_cancel() must reset _click_start to None."""
        d = _make_stub()
        # Stub close() so it doesn't crash headless
        d.close = lambda: None
        # Stub roi_cancelled signal
        cancelled = []
        d.roi_cancelled = type("S", (), {"emit": lambda s: cancelled.append(True)})()
        d._handle_press(_FakePos(100, 100))
        d._cancel()
        assert d._click_start is None

    def test_cancel_sets_closed_flag(self) -> None:
        """_cancel() must set _closed=True before emitting signal."""
        d = _make_stub()
        d.close = lambda: None
        closed_when_emitted: list = []

        d.roi_cancelled = type(
            "S", (), {"emit": lambda s: closed_when_emitted.append(d._closed)}
        )()
        d._cancel()
        assert d._closed is True
        assert closed_when_emitted == [True], "_closed must be True before emit"

    def test_cancel_clears_roi(self) -> None:
        """_cancel() must clear _roi."""
        d = _make_stub()
        d.close = lambda: None
        d.roi_cancelled = type("S", (), {"emit": lambda s: None})()
        d._handle_press(_FakePos(10, 10))
        d._handle_press(_FakePos(50, 50))
        assert d._roi is not None
        d._cancel()
        assert d._roi is None
