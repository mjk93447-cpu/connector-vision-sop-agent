"""
Unit tests for _RoiPickerDialog coordinate logic (v3.5.1).

Tests use object.__new__ to bypass Qt initialization — pure Python coordinate
math is tested without a display server.
"""

from __future__ import annotations

import importlib.util
from typing import Any

import pytest

# object.__new__(_RoiPickerDialog) is only safe when PyQt6 is absent
# (QDialog becomes plain `object`).  Skip entire module when PyQt6 is installed.
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


class _FakePixmap:
    """Minimal QPixmap stub."""

    def __init__(self, w: int, h: int) -> None:
        self._w, self._h = w, h

    def width(self) -> int:
        return self._w

    def height(self) -> int:
        return self._h


class _FakeLabel:
    """Minimal QLabel stub."""

    def __init__(self, w: int, h: int) -> None:
        self._w, self._h = w, h

    def width(self) -> int:
        return self._w

    def height(self) -> int:
        return self._h


def _make_stub(
    scale_x: float = 2.0,
    scale_y: float = 2.0,
    pix_w: int = 960,
    pix_h: int = 540,
    label_w: int = 1020,  # label wider than pixmap → ox = 30
    label_h: int = 580,  # label taller than pixmap → oy = 20
) -> Any:
    """Build a _RoiPickerDialog stub without Qt — pure coordinate logic only."""
    from src.gui.panels.sop_editor_panel import _RoiPickerDialog

    d = object.__new__(_RoiPickerDialog)
    d._click_start = None
    d._hover_pos = None
    d._roi = None
    d._scale_x = scale_x
    d._scale_y = scale_y
    d._display_pixmap = _FakePixmap(pix_w, pix_h)
    d._img_label = _FakeLabel(label_w, label_h)
    # Stub out Qt-dependent methods
    d._update_overlay = lambda: None
    d._coord_label = type("L", (), {"setText": lambda s, t: None})()
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
        """After second click, _click_start resets to None (ready for next selection)."""
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
        # _click_start is None now; third click starts over
        d._handle_press(_FakePos(100, 100))
        assert d._click_start is not None
        assert d._roi is not None  # previous ROI still there until overwritten


# ---------------------------------------------------------------------------
# Coordinate conversion with centering offset
# ---------------------------------------------------------------------------


class TestComputeRoiCoordinates:
    def test_roi_with_centering_offset(self) -> None:
        """Centering offset (ox=30, oy=20) is subtracted before scaling.

        pix_w=960, pix_h=540, label_w=1020 → ox=(1020-960)//2=30
                                label_h=580 → oy=(580-540)//2=20
        scale=2.0
        click1=(130,120): rx=130-30=100, ry=120-20=100
        click2=(230,220): rw=100, rh=100
        expected roi=(200,200,200,200)
        """
        d = _make_stub(
            scale_x=2.0, scale_y=2.0, pix_w=960, pix_h=540, label_w=1020, label_h=580
        )
        d._handle_press(_FakePos(130, 120))
        d._handle_press(_FakePos(230, 220))
        assert d._roi == (200, 200, 200, 200)

    def test_first_click_at_offset_origin_maps_to_screen_zero(self) -> None:
        """Click exactly at (ox, oy) should map to screen coordinate (0, 0)."""
        d = _make_stub(
            scale_x=2.0, scale_y=2.0, pix_w=960, pix_h=540, label_w=1020, label_h=580
        )
        # ox=30, oy=20
        d._handle_press(_FakePos(30, 20))  # exactly at offset origin
        d._handle_press(_FakePos(130, 120))  # 100px right/down
        rx, ry, rw, rh = d._roi
        assert rx == 0 and ry == 0, f"Expected (0,0) but got ({rx},{ry})"
        assert rw == 200 and rh == 200

    def test_no_offset_when_pixmap_fills_label(self) -> None:
        """When pixmap and label are same size, ox=oy=0 and coordinates are direct."""
        d = _make_stub(
            scale_x=2.0, scale_y=2.0, pix_w=900, pix_h=500, label_w=900, label_h=500
        )
        d._handle_press(_FakePos(50, 50))
        d._handle_press(_FakePos(150, 150))
        # rx=50, ry=50, rw=100, rh=100 → *2 = (100, 100, 200, 200)
        assert d._roi == (100, 100, 200, 200)

    def test_selection_clamped_to_pixmap_bounds(self) -> None:
        """Selection cannot extend beyond pixmap edges."""
        d = _make_stub(
            scale_x=2.0, scale_y=2.0, pix_w=100, pix_h=100, label_w=100, label_h=100
        )
        # Click way outside pixmap bounds
        d._handle_press(_FakePos(0, 0))
        d._handle_press(_FakePos(9999, 9999))
        _, _, rw, rh = d._roi
        assert rw <= 100 * 2  # max is pix_w * scale_x
        assert rh <= 100 * 2
