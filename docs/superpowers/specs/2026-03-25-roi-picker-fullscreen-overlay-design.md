# ROI Picker — Fullscreen Transparent Overlay + Direct Numeric Input

**Date:** 2026-03-25
**Status:** Approved
**Scope:** `src/gui/panels/sop_editor_panel.py`, `tests/unit/test_sop_editor_panel.py`
**Version target:** v3.7.0

---

## Problem Statement

Two usability issues remain after v3.6.0:

1. No direct numeric input in `_StepEditDialog` — manual spinbox fallback is hidden unless screenshot capture fails.
2. ROI selection is confined to a popup dialog (max 900×500px) — precise screen-area selection is impossible.

---

## Goals

1. x/y/w/h spinboxes always visible in `_StepEditDialog` — ROI settable by typing alone, synced via `valueChanged`.
2. "🎯 Pick ROI (Fullscreen)" hides main GUI, covers primary screen with transparent overlay.
3. After second click, confirmation panel with editable spinboxes appears for fine-tuning.
4. OK restores main GUI with selected ROI in spinboxes.

---

## Architecture

### Deleted

- `_RoiPickerDialog` — replaced entirely by `_RoiOverlayWindow`.
- All references updated: `_StepEditDialog._on_pick_roi()`, `tests/unit/test_sop_editor_panel.py` (`_make_stub()` and all test classes that used `_RoiPickerDialog`).

---

### New: `_RoiOverlayWindow(QWidget)`

**Initialization — explicit primary screen geometry:**
```python
screen = QApplication.primaryScreen()
self.setGeometry(screen.geometry())
self.show(); self.raise_(); self.activateWindow()
```
Post-`show()` geometry check: if `self.geometry() != screen.geometry()`, close, show `QMessageBox.warning` on parent `_StepEditDialog`, and re-show main GUI.

**Window flags:**
```python
Qt.WindowType.FramelessWindowHint |
Qt.WindowType.WindowStaysOnTopHint |
Qt.WindowType.Tool
```
**Attributes:** `WA_TranslucentBackground = True`, `WA_NoSystemBackground = True`

**Signals:**
```python
roi_confirmed = pyqtSignal(int, int, int, int)
roi_cancelled = pyqtSignal()
```

**State:**
- `_click_start: Optional[QPoint]` — widget-local, set on first click
- `_hover_pos: Optional[QPoint]` — widget-local, updated on mouse move
- `_roi: Optional[Tuple[int,int,int,int]]` — global screen coordinates, set by `_compute_roi()`

---

### Coordinate Design — Pure-Arithmetic `_compute_roi` (testable headless)

**Key principle:** `_handle_press(local_pos)` converts to global before calling `_compute_roi`. This keeps `_compute_roi` as pure arithmetic (no Qt calls) — identical to the existing headless test pattern.

```python
def _handle_press(self, local_pos: Any) -> None:
    """State machine — called from mousePressEvent with widget-local pos."""
    if self._click_start is None:
        self._click_start = local_pos
    else:
        # Convert both points to global coords, then compute
        g_start = self._to_global(self._click_start)
        g_end   = self._to_global(local_pos)
        self._compute_roi(g_start, g_end)
        self._click_start = None

def _to_global(self, local_pos: Any) -> Any:
    """Convert widget-local QPoint to global screen QPoint. Overridable for testing."""
    return self.mapToGlobal(local_pos)

def _compute_roi(self, g_start: Any, g_end: Any) -> None:
    """Pure arithmetic — no Qt calls. Accepts any object with .x()/.y()."""
    x = min(g_start.x(), g_end.x())
    y = min(g_start.y(), g_end.y())
    w = abs(g_end.x() - g_start.x())
    h = abs(g_end.y() - g_start.y())
    self._roi = (x, y, w, h)
```

In headless tests, `_to_global` is stubbed to return the input unchanged (overlay at origin → local == global). This makes `_compute_roi` fully testable without `mapToGlobal`.

---

### `paintEvent` with Windows DWM fallback

**Primary path** (DWM compositing available):
1. Fill entire widget with `rgba(0, 0, 0, 150)`.
2. If selection rect exists: `CompositionMode_Clear` to erase it (spotlight — real screen shows through).
3. Red dashed border during preview; solid after confirmation.

**Fallback path** (DWM compositing unavailable):
- Detect: after `CompositionMode_Clear`, sample pixel color at rect center. If opaque black → compositing is off.
- Fallback: draw 4 dark strips (top/bottom/left/right) surrounding the selection area, leaving the interior undrawn. No per-pixel alpha needed.

---

### ESC / Cancel — `_cancel()` handles all states

```python
def _cancel(self) -> None:
    self._click_start = None
    self._roi = None
    self.roi_cancelled.emit()
    self.close()
```

**`keyPressEvent` override:**
```python
def keyPressEvent(self, event: Any) -> None:
    if event.key() == Qt.Key.Key_Escape:
        self._cancel()
    else:
        super().keyPressEvent(event)
```

**`closeEvent` override:**
```python
def closeEvent(self, event: Any) -> None:
    # Prevent double-emission when _cancel() → close() → closeEvent
    if not self._closed:
        self._closed = True
        self.roi_cancelled.emit()
    super().closeEvent(event)
```
`self._closed = False` initialized in `__init__`. `_cancel()` sets `self._closed = True` before calling `self.close()`.

---

### `_ConfirmPanel` (child `QWidget` of `_RoiOverlayWindow`)

**Position:** bottom-center of overlay widget. If `_roi[1] + _roi[3]/2 > self.parent().height() // 2` (selection vertical center is in the lower half of the overlay window — `self.parent()` is `_RoiOverlayWindow` whose height equals the screen height), position panel in the upper portion instead.

**Spinbox ranges:** x/w → 0–3840, y/h → 0–2160.

**Layout:** `ROI Confirm:  x=[spin] y=[spin] w=[spin] h=[spin]  [OK]  [Cancel]`

**Behavior:**
- Initialized with values from `_RoiOverlayWindow._roi`.
- `valueChanged` on any spinbox → update `_RoiOverlayWindow._roi` → `parent().update()` (repaints overlay with new rect).
- OK → `parent().roi_confirmed.emit(x, y, w, h)` → `parent().close()`.
- Cancel → `parent()._cancel()`.

---

### Modified: `_StepEditDialog`

**ROI section — always visible:**
```
[🎯 Pick ROI (Fullscreen)]  [✕ Clear ROI]
ROI:  x=[spinbox]  y=[spinbox]  w=[spinbox]  h=[spinbox]
```

**Spinbox ranges:** x/w → 0–3840, y/h → 0–2160.

**Initialization order (existing ROI preserved):**
```python
# 1. Set spinbox VALUES first (before connecting signals)
if self._roi is not None:
    x, y, w, h = self._roi
    self._spin_x.setValue(x); self._spin_y.setValue(y)
    self._spin_w.setValue(w); self._spin_h.setValue(h)

# 2. Connect valueChanged AFTER values are set
for spin in (self._spin_x, self._spin_y, self._spin_w, self._spin_h):
    spin.valueChanged.connect(self._sync_roi_from_spinboxes)
```
This prevents `valueChanged` from firing during initialization and overwriting an existing ROI with (0,0,0,0).

**Single source of truth:**
```python
def _sync_roi_from_spinboxes(self) -> None:
    x, y, w, h = (self._spin_x.value(), self._spin_y.value(),
                  self._spin_w.value(), self._spin_h.value())
    self._roi = (x, y, w, h) if (w > 0 or h > 0) else None
```

`get_step()` reads **only** `self._roi` — never reads spinboxes directly.

**`_on_clear_roi()`:** sets all four spinboxes to 0. `_sync_roi_from_spinboxes` fires via `valueChanged` → `self._roi = None`. No direct assignment to `self._roi` in this method.

**`_on_pick_roi()`:**
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

**`_on_roi_confirmed(x, y, w, h)`:**
```python
def _on_roi_confirmed(self, x: int, y: int, w: int, h: int) -> None:
    self.window().show(); self.window().raise_()
    # Temporarily block signals to prevent double-sync
    for spin in (self._spin_x, self._spin_y, self._spin_w, self._spin_h):
        spin.blockSignals(True)
    self._spin_x.setValue(x); self._spin_y.setValue(y)
    self._spin_w.setValue(w); self._spin_h.setValue(h)
    for spin in (self._spin_x, self._spin_y, self._spin_w, self._spin_h):
        spin.blockSignals(False)
    self._roi = (x, y, w, h)
```

**`_on_roi_cancelled()`:**
```python
def _on_roi_cancelled(self) -> None:
    self.window().show(); self.window().raise_()
    # no ROI change
```

---

## Data Flow

```
User clicks "🎯 Pick ROI (Fullscreen)"
  → _StepEditDialog._on_pick_roi()
      → self.window().hide()
      → _RoiOverlayWindow created → setGeometry(primaryScreen) → show()
          → user click #1 → _click_start set (widget-local)
          → user moves mouse → paintEvent draws dashed preview
          → user click #2 → _handle_press() → _to_global() → _compute_roi() → _roi set
              → _ConfirmPanel shown (bottom-center or top-center if selection in lower half)
                  → user optionally edits spinboxes → _roi updated → overlay repaints
                  → user clicks OK → roi_confirmed(x,y,w,h) emitted → overlay closed
  → _StepEditDialog._on_roi_confirmed(x,y,w,h)
      → self.window().show() + raise_()
      → spinboxes set (blockSignals) → self._roi = (x,y,w,h)

ESC / Cancel (any state) → _cancel() → roi_cancelled emitted → overlay closed
  → _StepEditDialog._on_roi_cancelled() → self.window().show() + raise_()
```

---

## Testing

**Skip guard:** unchanged — `pytest.skip` when `find_spec("PyQt6") is not None`.

**`_make_stub()` updated for `_RoiOverlayWindow`:**
```python
def _make_stub() -> Any:
    from src.gui.panels.sop_editor_panel import _RoiOverlayWindow
    d = object.__new__(_RoiOverlayWindow)
    d._click_start = None
    d._hover_pos   = None
    d._roi         = None
    d._closed      = False
    d._update_overlay = lambda: None
    # Stub _to_global to return the input unchanged (no mapToGlobal needed)
    d._to_global = lambda pos: pos
    return d
```

**Tests retained (updated class name):**
- `TestHandlePressStateMachine` — click-move-click state machine (unchanged logic).

**`TestComputeRoiCoordinates` → `TestComputeRoiOverlay`:**
- `test_roi_no_scale_no_offset`: (130,120)→(230,220) → `(130,120,100,100)` (1:1, no offset).
- `test_reversed_click_order`: bottom-right first then top-left → same positive roi.
- Previous centering-offset tests removed (no longer applicable — overlay is 1:1 with screen).

---

## Version & Docs

- `src/gui/main_window.py:49`: `"3.6.0"` → `"3.7.0"`
- `progress.md`: add v3.7.0 checkpoint row
- Commit: `[feat] ROI picker 전체화면 투명 오버레이 + 직접 숫자 입력 (v3.7.0)`

---

## Out of Scope

- Multi-monitor (non-primary screen) support.
- ROI history / presets.
- ROI preview in the SOP step list table.
