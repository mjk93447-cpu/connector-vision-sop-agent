# ROI Picker — Fullscreen Transparent Overlay + Direct Numeric Input

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `_RoiPickerDialog` popup with a fullscreen transparent overlay (`_RoiOverlayWindow`) for precise on-screen ROI selection, and add always-visible x/y/w/h spinboxes to `_StepEditDialog` for direct numeric input.

**Architecture:** New `_RoiOverlayWindow(QWidget)` + child `_ConfirmPanel(QWidget)` replace `_RoiPickerDialog`. Pure-arithmetic `_compute_roi()` keeps coordinate logic headless-testable via a `_to_global()` stub. `_StepEditDialog` gains always-visible spinboxes as the single source of truth for ROI.

**Tech Stack:** Python 3.11, PyQt6 (`pyqtSignal`, `QWidget`, `QPainter`, `QSpinBox`), pytest (headless — skip when PyQt6 present)

---

## File Map

| File | Action | Scope |
|------|--------|-------|
| `src/gui/panels/sop_editor_panel.py` | Modify | Delete `_RoiPickerDialog`; add `_RoiOverlayWindow`, `_ConfirmPanel`; update `_StepEditDialog` |
| `tests/unit/test_sop_editor_panel.py` | Rewrite | New `_make_stub()`, `TestHandlePressStateMachine` updated, `TestComputeRoiOverlay` replaces `TestComputeRoiCoordinates` |
| `src/gui/main_window.py:49` | Modify | Version bump `3.6.0` → `3.7.0` |
| `progress.md` | Modify | Add v3.7.0 checkpoint row |

---

## Task 1: Rewrite tests for `_RoiOverlayWindow` (TDD — write first)

**Files:**
- Modify: `tests/unit/test_sop_editor_panel.py`

Tests reference `_RoiOverlayWindow` which doesn't exist yet — they'll fail with `ImportError`. That's the expected TDD starting point.

- [ ] **Step 1: Rewrite `tests/unit/test_sop_editor_panel.py`**

Replace the entire file with:

```python
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
    from src.gui.panels.sop_editor_panel import _RoiOverlayWindow

    d = object.__new__(_RoiOverlayWindow)
    d._click_start = None
    d._hover_pos = None
    d._roi = None
    d._closed = False
    d._confirm_panel = None
    # Stub Qt-dependent methods
    d._update_overlay = lambda: None
    d._show_confirm_panel = lambda: None
    # Stub _to_global to return input unchanged (overlay at origin → local == global)
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
        assert d._roi is not None  # previous ROI still present until overwritten


# ---------------------------------------------------------------------------
# Coordinate conversion — 1:1 overlay (no scale, no centering offset)
# ---------------------------------------------------------------------------


class TestComputeRoiOverlay:
    def test_roi_direct_coordinates(self) -> None:
        """Overlay is 1:1 — coordinates map directly to screen pixels."""
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
```

- [ ] **Step 2: Run tests — confirm FAIL**

```bash
cd /c/connector-vision-sop-agent/.claude/worktrees/inspiring-swartz
python -m pytest tests/unit/test_sop_editor_panel.py -v 2>&1 | head -40
```

Expected: `ImportError: cannot import name '_RoiOverlayWindow'` (or entire module skip if PyQt6 present in local env — either is correct).

---

## Task 2: Add `_RoiOverlayWindow` coordinate core (make tests pass)

**Files:**
- Modify: `src/gui/panels/sop_editor_panel.py`

Add `_RoiOverlayWindow` class with just the coordinate logic. Full Qt UI comes in Task 3.

- [ ] **Step 3: Add `_RoiOverlayWindow` skeleton + coordinate methods**

In `sop_editor_panel.py`, replace the entire `_RoiPickerDialog` class (lines ~52–268) with the following. Keep everything else untouched.

```python
# ---------------------------------------------------------------------------
# ROI Overlay Window (fullscreen transparent — replaces _RoiPickerDialog)
# ---------------------------------------------------------------------------


class _RoiOverlayWindow(QWidget):  # type: ignore[misc]
    """
    Fullscreen transparent overlay for ROI selection.

    Shows the real screen under a semi-transparent dark layer. User clicks
    twice (click-move-click) to define a rectangle; a _ConfirmPanel then
    lets them fine-tune the coordinates before confirming.
    """

    if _QT_AVAILABLE:
        from PyQt6.QtCore import pyqtSignal  # noqa: PLC0415

        roi_confirmed = pyqtSignal(int, int, int, int)
        roi_cancelled = pyqtSignal()

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._click_start: Optional[Any] = None
        self._hover_pos: Optional[Any] = None
        self._roi: Optional[Tuple[int, int, int, int]] = None
        self._closed: bool = False
        self._confirm_panel: Optional[Any] = None

        if not _QT_AVAILABLE:
            return

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        screen = QApplication.primaryScreen()
        self.setGeometry(screen.geometry())

    # ------------------------------------------------------------------
    # Coordinate state machine (pure Python — testable headless)
    # ------------------------------------------------------------------

    def _handle_press(self, local_pos: Any) -> None:
        """Click-move-click state machine. Called from mousePressEvent."""
        if self._click_start is None:
            self._click_start = local_pos          # first click: set start
        else:
            g_start = self._to_global(self._click_start)
            g_end = self._to_global(local_pos)
            self._compute_roi(g_start, g_end)
            self._click_start = None               # reset for next selection
            self._show_confirm_panel()

    def _to_global(self, local_pos: Any) -> Any:
        """Convert widget-local QPoint to global screen QPoint.
        Overridden in headless tests by setting d._to_global = lambda p: p."""
        if _QT_AVAILABLE:
            return self.mapToGlobal(local_pos)
        return local_pos

    def _compute_roi(self, g_start: Any, g_end: Any) -> None:
        """Pure arithmetic — no Qt calls. g_start/g_end have .x() and .y()."""
        x = min(g_start.x(), g_end.x())
        y = min(g_start.y(), g_end.y())
        w = abs(g_end.x() - g_start.x())
        h = abs(g_end.y() - g_start.y())
        self._roi = (x, y, w, h)

    # ------------------------------------------------------------------
    # Cancel / close
    # ------------------------------------------------------------------

    def _cancel(self) -> None:
        """Cancel from any state — restores GUI via roi_cancelled signal."""
        self._closed = True
        self._click_start = None
        self._roi = None
        if _QT_AVAILABLE:
            self.roi_cancelled.emit()
            self.close()

    # ------------------------------------------------------------------
    # Qt UI — paint, events, confirm panel (requires display)
    # ------------------------------------------------------------------

    def _show_confirm_panel(self) -> None:
        if not _QT_AVAILABLE or self._roi is None:
            return
        if self._confirm_panel is not None:
            self._confirm_panel.deleteLater()
        self._confirm_panel = _ConfirmPanel(self._roi, parent=self)
        panel_w = self._confirm_panel.sizeHint().width()
        panel_h = self._confirm_panel.sizeHint().height()
        cx = max(0, (self.width() - panel_w) // 2)

        # Place at bottom; shift to top if selection occupies the lower half
        x, y, w, h = self._roi
        screen = QApplication.primaryScreen()
        oy = screen.geometry().y()
        roi_center_local_y = (y - oy) + h // 2
        if roi_center_local_y > self.height() // 2:
            cy = 20
        else:
            cy = max(0, self.height() - panel_h - 20)

        self._confirm_panel.setGeometry(cx, cy, panel_w, panel_h)
        self._confirm_panel.show()
        self.update()

    def _get_selection_rect_local(self) -> Optional[Any]:
        """Return selection rect in widget-local coordinates, or None."""
        if not _QT_AVAILABLE:
            return None
        screen = QApplication.primaryScreen()
        ox = screen.geometry().x()
        oy = screen.geometry().y()

        if self._roi is not None:
            rx, ry, rw, rh = self._roi
            return QRect(rx - ox, ry - oy, rw, rh)
        if self._click_start is not None and self._hover_pos is not None:
            return QRect(self._click_start, self._hover_pos).normalized()
        return None

    def paintEvent(self, event: Any) -> None:
        if not _QT_AVAILABLE:
            return
        from PyQt6.QtGui import QColor, QFont  # noqa: PLC0415

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Semi-transparent dark overlay over entire screen
        painter.fillRect(self.rect(), QColor(0, 0, 0, 150))

        sel = self._get_selection_rect_local()
        if sel is not None and sel.width() > 0 and sel.height() > 0:
            # Spotlight: clear selection area so real screen shows through
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_Clear
            )
            painter.fillRect(sel, Qt.GlobalColor.transparent)
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceOver
            )

            # Red border: dashed during preview, solid after confirm
            pen = QPen(QColor("red"), 2)
            if self._click_start is not None:
                pen.setStyle(Qt.PenStyle.DashLine)
            else:
                pen.setStyle(Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawRect(sel)

        # Hint text when nothing is selected yet
        if self._click_start is None and self._roi is None:
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceOver
            )
            painter.setPen(QColor(255, 255, 255, 220))
            painter.setFont(QFont("Arial", 14))
            hint = "Click to set start point — move mouse — click again to confirm  (ESC to cancel)"
            painter.drawText(
                self.rect().adjusted(0, 20, 0, 0),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                hint,
            )

        painter.end()

    def mousePressEvent(self, event: Any) -> None:
        if not _QT_AVAILABLE or self._confirm_panel is not None:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._handle_press(event.pos())
            self.update()

    def mouseMoveEvent(self, event: Any) -> None:
        if not _QT_AVAILABLE:
            return
        self._hover_pos = event.pos()
        if self._click_start is not None and self._confirm_panel is None:
            self.update()

    def keyPressEvent(self, event: Any) -> None:
        if not _QT_AVAILABLE:
            return
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event: Any) -> None:
        if not self._closed:
            self._closed = True
            if _QT_AVAILABLE:
                self.roi_cancelled.emit()
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# ROI Confirm Panel (child of _RoiOverlayWindow)
# ---------------------------------------------------------------------------


class _ConfirmPanel(QWidget):  # type: ignore[misc]
    """Small overlay panel for fine-tuning ROI after selection."""

    def __init__(self, roi: Tuple[int, int, int, int], parent: Any = None) -> None:
        super().__init__(parent)
        if _QT_AVAILABLE:
            self._setup_ui(roi)

    def _setup_ui(self, roi: Tuple[int, int, int, int]) -> None:
        self.setStyleSheet(
            "background: rgba(255,255,255,230);"
            "border: 1px solid #aaa; border-radius: 6px; padding: 2px;"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(6)

        layout.addWidget(QLabel("ROI Confirm:"))

        x, y, w, h = roi
        self._spin_x = QSpinBox()
        self._spin_x.setRange(0, 3840)
        self._spin_x.setValue(x)
        self._spin_y = QSpinBox()
        self._spin_y.setRange(0, 2160)
        self._spin_y.setValue(y)
        self._spin_w = QSpinBox()
        self._spin_w.setRange(0, 3840)
        self._spin_w.setValue(w)
        self._spin_h = QSpinBox()
        self._spin_h.setRange(0, 2160)
        self._spin_h.setValue(h)

        for lbl, spin in [
            ("x:", self._spin_x),
            ("y:", self._spin_y),
            ("w:", self._spin_w),
            ("h:", self._spin_h),
        ]:
            layout.addWidget(QLabel(lbl))
            layout.addWidget(spin)

        for spin in (self._spin_x, self._spin_y, self._spin_w, self._spin_h):
            spin.valueChanged.connect(self._on_spinbox_changed)

        btn_ok = QPushButton("OK")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._on_ok)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self._on_cancel)
        layout.addWidget(btn_ok)
        layout.addWidget(btn_cancel)

        self.adjustSize()

    def _on_spinbox_changed(self) -> None:
        overlay = self.parent()
        if overlay is not None and _QT_AVAILABLE:
            overlay._roi = (
                self._spin_x.value(),
                self._spin_y.value(),
                self._spin_w.value(),
                self._spin_h.value(),
            )
            overlay.update()

    def _on_ok(self) -> None:
        overlay = self.parent()
        if overlay is not None and _QT_AVAILABLE:
            x = self._spin_x.value()
            y = self._spin_y.value()
            w = self._spin_w.value()
            h = self._spin_h.value()
            overlay._closed = True
            overlay.roi_confirmed.emit(x, y, w, h)
            overlay.close()

    def _on_cancel(self) -> None:
        overlay = self.parent()
        if overlay is not None:
            overlay._cancel()
```

Also add these imports to the `try` block at the top of the file (if not already present):

```python
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    ...existing...
    QApplication,   # add if missing
)
```

- [ ] **Step 4: Run tests — confirm PASS**

```bash
python -m pytest tests/unit/test_sop_editor_panel.py -v 2>&1 | tail -20
```

Expected: 9 tests pass (or entire module skipped with `s` if PyQt6 is present locally — both are OK).

---

## Task 3: Update `_StepEditDialog` — always-visible spinboxes

**Files:**
- Modify: `src/gui/panels/sop_editor_panel.py` — `_StepEditDialog` class

- [ ] **Step 5: Update `_StepEditDialog._setup_ui()` — ROI section**

Replace the current ROI row (lines ~338–349):

```python
# ROI field
self._roi_label = QLabel("full screen")
self._roi_label.setStyleSheet("font-style: italic; color: #555555;")
btn_roi = QPushButton("🎯 Pick ROI")
btn_roi.clicked.connect(self._on_pick_roi)
roi_row = QHBoxLayout()
roi_row.addWidget(btn_roi)
roi_row.addWidget(self._roi_label)
roi_row.addStretch()
roi_container = QWidget()
roi_container.setLayout(roi_row)
form.addRow("ROI:", roi_container)
```

With:

```python
# ROI — always-visible spinboxes + fullscreen picker button
btn_roi = QPushButton("🎯 Pick ROI (Fullscreen)")
btn_roi.clicked.connect(self._on_pick_roi)
btn_clear_roi = QPushButton("✕ Clear ROI")
btn_clear_roi.clicked.connect(self._on_clear_roi)

roi_btn_row = QHBoxLayout()
roi_btn_row.addWidget(btn_roi)
roi_btn_row.addWidget(btn_clear_roi)
roi_btn_row.addStretch()
roi_btn_container = QWidget()
roi_btn_container.setLayout(roi_btn_row)
form.addRow("", roi_btn_container)

self._spin_x = QSpinBox()
self._spin_x.setRange(0, 3840)
self._spin_x.setPrefix("x: ")
self._spin_y = QSpinBox()
self._spin_y.setRange(0, 2160)
self._spin_y.setPrefix("y: ")
self._spin_w = QSpinBox()
self._spin_w.setRange(0, 3840)
self._spin_w.setPrefix("w: ")
self._spin_h = QSpinBox()
self._spin_h.setRange(0, 2160)
self._spin_h.setPrefix("h: ")

roi_spin_row = QHBoxLayout()
for spin in (self._spin_x, self._spin_y, self._spin_w, self._spin_h):
    roi_spin_row.addWidget(spin)
roi_spin_row.addStretch()
roi_spin_container = QWidget()
roi_spin_container.setLayout(roi_spin_row)
form.addRow("ROI:", roi_spin_container)
```

- [ ] **Step 6: Update `_setup_ui()` — ROI initialization + signal connection (after form layout)**

After the existing ROI label initialization block (lines ~374–382), replace:

```python
# Initialize ROI label
if self._roi is not None:
    x, y, w, h = self._roi
    self._roi_label.setText(f"x={x} y={y} w={w} h={h}")
    self._roi_label.setStyleSheet("color: black;")
```

With:

```python
# Initialize spinboxes with existing ROI BEFORE connecting signals
# (prevents valueChanged from firing and overwriting _roi during init)
if self._roi is not None:
    x, y, w, h = self._roi
    self._spin_x.setValue(x)
    self._spin_y.setValue(y)
    self._spin_w.setValue(w)
    self._spin_h.setValue(h)

# Connect valueChanged AFTER setting initial values
for spin in (self._spin_x, self._spin_y, self._spin_w, self._spin_h):
    spin.valueChanged.connect(self._sync_roi_from_spinboxes)
```

- [ ] **Step 7: Add new methods to `_StepEditDialog`**

Add these methods to `_StepEditDialog` (after `_update_field_states`, before `_on_accept`):

```python
def _sync_roi_from_spinboxes(self) -> None:
    """Single source of truth: spinboxes → self._roi."""
    x = self._spin_x.value()
    y = self._spin_y.value()
    w = self._spin_w.value()
    h = self._spin_h.value()
    self._roi = (x, y, w, h) if (w > 0 or h > 0) else None

def _on_clear_roi(self) -> None:
    """Reset all spinboxes to 0 — triggers _sync_roi_from_spinboxes via valueChanged."""
    for spin in (self._spin_x, self._spin_y, self._spin_w, self._spin_h):
        spin.setValue(0)

def _on_roi_confirmed(self, x: int, y: int, w: int, h: int) -> None:
    """Called when overlay emits roi_confirmed signal."""
    self.window().show()
    self.window().raise_()
    # Block signals while setting values to prevent double-sync
    for spin in (self._spin_x, self._spin_y, self._spin_w, self._spin_h):
        spin.blockSignals(True)
    self._spin_x.setValue(x)
    self._spin_y.setValue(y)
    self._spin_w.setValue(w)
    self._spin_h.setValue(h)
    for spin in (self._spin_x, self._spin_y, self._spin_w, self._spin_h):
        spin.blockSignals(False)
    self._roi = (x, y, w, h)

def _on_roi_cancelled(self) -> None:
    """Called when overlay emits roi_cancelled signal."""
    self.window().show()
    self.window().raise_()
    # No ROI change
```

- [ ] **Step 8: Replace `_on_pick_roi()` in `_StepEditDialog`**

Replace the existing `_on_pick_roi()` method:

```python
def _on_pick_roi(self) -> None:
    if not _QT_AVAILABLE:
        return
    dlg = _RoiPickerDialog(parent=self)
    if dlg.exec() == QDialog.DialogCode.Accepted:
        roi = dlg.roi
        if roi is not None:
            self._roi = roi
            x, y, w, h = roi
            self._roi_label.setText(f"x={x} y={y} w={w} h={h}")
            self._roi_label.setStyleSheet("color: black;")
```

With:

```python
def _on_pick_roi(self) -> None:
    if not _QT_AVAILABLE:
        return
    self.window().hide()
    overlay = _RoiOverlayWindow(parent=None)
    overlay.roi_confirmed.connect(self._on_roi_confirmed)
    overlay.roi_cancelled.connect(self._on_roi_cancelled)
    overlay.show()
```

- [ ] **Step 9: Update `get_step()` — remove `_roi_label` reference, read `self._roi` only**

In `get_step()`, the ROI section currently reads from `self._roi` which is already the correct field. Verify no reference to `self._roi_label` remains in `get_step()`. The ROI block should be:

```python
# ROI: omit if None
if self._roi is not None:
    step["roi"] = list(self._roi)
elif "roi" in step:
    del step["roi"]
```

No changes needed here if `_roi_label` was only used for display (confirm this is the case).

---

## Task 4: Run full test suite + linting

- [ ] **Step 10: Run full test suite**

```bash
cd /c/connector-vision-sop-agent/.claude/worktrees/inspiring-swartz
bash run_tests.sh 2>&1 | tail -30
```

Expected: all existing tests pass + new `TestComputeRoiOverlay` tests pass (or skipped on PyQt6 env). No regressions.

If any test fails: read the error, diagnose, fix, and rerun before proceeding.

- [ ] **Step 11: Run linters**

```bash
python -m black src/gui/panels/sop_editor_panel.py tests/unit/test_sop_editor_panel.py
python -m ruff check src/gui/panels/sop_editor_panel.py tests/unit/test_sop_editor_panel.py --fix
```

Expected: no errors.

---

## Task 5: Version bump + docs

**Files:**
- Modify: `src/gui/main_window.py:49`
- Modify: `progress.md`

- [ ] **Step 12: Bump version to 3.7.0**

In `src/gui/main_window.py` line 49:

```python
_APP_VERSION = "3.7.0"   # was "3.6.0"
```

- [ ] **Step 13: Update progress.md**

Update `_최종 갱신` line at top:

```markdown
_최종 갱신: 2026-03-25 (v3.7.0 — ROI picker 전체화면 오버레이 + 직접 숫자 입력)_
```

Add row to completion checkpoint table (after v3.6.0 row):

```markdown
| **v3.7.0** | **ROI picker 전체화면 투명 오버레이 + 직접 숫자 입력 (_RoiOverlayWindow)** | **pass** | **92%+** |
```

---

## Task 6: Commit + GitHub artifact build

- [ ] **Step 14: Commit all changes**

```bash
git add src/gui/panels/sop_editor_panel.py \
        tests/unit/test_sop_editor_panel.py \
        src/gui/main_window.py \
        progress.md \
        docs/superpowers/specs/2026-03-25-roi-picker-fullscreen-overlay-design.md \
        docs/superpowers/plans/2026-03-25-roi-picker-fullscreen-overlay.md
git commit -m "[feat] ROI picker 전체화면 투명 오버레이 + 직접 숫자 입력 (v3.7.0)"
```

- [ ] **Step 15: Push to main**

```bash
git push origin claude/inspiring-swartz:main
```

- [ ] **Step 16: Trigger artifact build**

```bash
gh workflow run "Build Connector Vision Agent (All-in-One)" --ref main
```

- [ ] **Step 17: Monitor build**

```bash
# Get the run ID (wait ~30s for it to appear)
gh run list --workflow="Build Connector Vision Agent (All-in-One)" --limit 3

# Watch live
gh run watch <RUN_ID>
```

If build fails:

```bash
gh run view <RUN_ID> --log-failed 2>&1 | head -80
```

Diagnose the failure, fix the code, commit + push, then trigger a new build (do NOT retry the same failed run).

---

## Notes

1. `_RoiPickerDialog` is deleted entirely — no other callers exist outside `_StepEditDialog._on_pick_roi()`.
2. `pyautogui` import in `_RoiPickerDialog._on_capture()` is also removed with the class.
3. The PyQt6 skip guard in tests is unchanged (`pytest.skip` when `find_spec("PyQt6") is not None`).
4. Do NOT modify `assets/config.json` or `assets/models/`.
5. YOLO rule: `yolo26x.pt` only — no YOLOv8/v9/v10/v11.
