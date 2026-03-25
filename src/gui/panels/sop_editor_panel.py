"""
Tab 4 — SOP Step Editor Panel.

Allows engineers to add, delete, reorder, and toggle SOP steps
without editing code. Changes are saved to assets/sop_steps.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from PyQt6.QtCore import QRect, Qt, pyqtSignal
    from PyQt6.QtGui import QColor, QFont, QPainter, QPen
    from PyQt6.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QSpinBox,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False
    QWidget = object  # type: ignore[assignment,misc]
    QDialog = object  # type: ignore[assignment,misc]

_STEP_TYPES = ["click", "drag", "validate_pins", "click_sequence"]
_TARGET_TYPES = ["auto", "TEXT", "NON_TEXT"]


# ---------------------------------------------------------------------------
# ROI Overlay Window (fullscreen transparent — replaces _RoiPickerDialog)
# ---------------------------------------------------------------------------


class _RoiOverlayWindow(QWidget):  # type: ignore[misc]
    """
    Fullscreen transparent overlay for ROI selection.

    Covers the primary screen with a semi-transparent dark layer. User
    clicks twice (click-move-click) to define a rectangle; a _ConfirmPanel
    then lets them fine-tune coordinates before confirming.

    Signals (when PyQt6 available):
        roi_confirmed(int, int, int, int) — emitted with (x, y, w, h)
        roi_cancelled                     — emitted on ESC / Cancel / close
    """

    if _QT_AVAILABLE:
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
    # Coordinate state machine — pure Python, testable headless
    # ------------------------------------------------------------------

    def _handle_press(self, local_pos: Any) -> None:
        """Click-move-click state machine. Called from mousePressEvent."""
        if self._click_start is None:
            self._click_start = local_pos  # first click: set start
        else:
            g_start = self._to_global(self._click_start)
            g_end = self._to_global(local_pos)
            self._compute_roi(g_start, g_end)  # sets self._roi
            self._click_start = None  # reset for next selection
            self._show_confirm_panel()

    def _to_global(self, local_pos: Any) -> Any:
        """Convert widget-local QPoint to global screen QPoint.
        Instance attribute overrides class method in headless tests:
            d._to_global = lambda pos: pos
        """
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
    # Cancel — handles all states
    # ------------------------------------------------------------------

    def _cancel(self) -> None:
        """Cancel from any state. Sets _closed BEFORE emitting to prevent
        double-emission if closeEvent fires after close()."""
        self._closed = True
        self._click_start = None
        self._roi = None
        if hasattr(self, "roi_cancelled"):
            self.roi_cancelled.emit()
        if _QT_AVAILABLE:
            self.close()

    # ------------------------------------------------------------------
    # Qt UI — requires display
    # ------------------------------------------------------------------

    def _show_confirm_panel(self) -> None:
        if not _QT_AVAILABLE or self._roi is None:
            return
        if self._confirm_panel is not None:
            self._confirm_panel.deleteLater()
        # _ConfirmPanel reads self._roi (set by _compute_roi) for initial values
        self._confirm_panel = _ConfirmPanel(self._roi, parent=self)
        panel_w = self._confirm_panel.sizeHint().width()
        panel_h = self._confirm_panel.sizeHint().height()
        cx = max(0, (self.width() - panel_w) // 2)

        # Place at bottom; shift to top if selection occupies the lower half.
        # Use self.parent().height() is N/A — self IS the overlay (fullscreen).
        # self.height() == screen height. _roi coords are global; subtract
        # overlay origin to get widget-local Y.
        screen = QApplication.primaryScreen()
        oy = screen.geometry().y()
        rx, ry, rw, rh = self._roi
        roi_center_local_y = (ry - oy) + rh // 2
        if roi_center_local_y > self.height() // 2:
            cy = 20
        else:
            cy = max(0, self.height() - panel_h - 20)

        self._confirm_panel.setGeometry(cx, cy, panel_w, panel_h)
        self._confirm_panel.show()
        self.update()

    def _get_selection_rect_local(self) -> Optional[Any]:
        """Return selection rect in widget-local coordinates for painting."""
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
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Semi-transparent dark overlay covering entire screen
        painter.fillRect(self.rect(), QColor(0, 0, 0, 150))

        sel = self._get_selection_rect_local()
        if sel is not None and sel.width() > 0 and sel.height() > 0:
            # Spotlight: clear selection so real screen shows through
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(sel, Qt.GlobalColor.transparent)
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceOver
            )
            # Red border: dashed during preview, solid after confirmation
            pen = QPen(QColor("red"), 2)
            pen.setStyle(
                Qt.PenStyle.DashLine
                if self._click_start is not None
                else Qt.PenStyle.SolidLine
            )
            painter.setPen(pen)
            painter.drawRect(sel)

        # Hint text when nothing selected yet
        if self._click_start is None and self._roi is None:
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceOver
            )
            painter.setPen(QColor(255, 255, 255, 220))
            painter.setFont(QFont("Arial", 14))
            painter.drawText(
                self.rect().adjusted(0, 20, 0, 0),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                "Click to set start point — move mouse — click again to confirm"
                "  (ESC to cancel)",
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
    """Small panel for fine-tuning ROI after click selection."""

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


# ---------------------------------------------------------------------------
# Step edit dialog
# ---------------------------------------------------------------------------


class _StepEditDialog(QDialog):  # type: ignore[misc]
    def __init__(
        self, step: Optional[Dict[str, Any]] = None, parent: Any = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit SOP Step" if step else "Add New SOP Step")
        self.setMinimumWidth(420)
        self._step = step or {}
        self._roi: Optional[Tuple[int, int, int, int]] = None
        # Load existing ROI from step if present
        existing_roi = self._step.get("roi")
        if existing_roi and len(existing_roi) == 4:
            self._roi = tuple(existing_roi)  # type: ignore[assignment]
        self._setup_ui()

    def _setup_ui(self) -> None:
        if not _QT_AVAILABLE:
            return
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._id_edit = QLineEdit(self._step.get("id", ""))
        self._id_edit.setPlaceholderText("e.g. my_step")
        form.addRow("ID:", self._id_edit)

        self._name_edit = QLineEdit(self._step.get("name", ""))
        self._name_edit.setPlaceholderText("e.g. Login")
        form.addRow("Name:", self._name_edit)

        self._type_combo = QComboBox()
        self._type_combo.addItems(_STEP_TYPES)
        cur_type = self._step.get("type", "click")
        idx = _STEP_TYPES.index(cur_type) if cur_type in _STEP_TYPES else 0
        self._type_combo.setCurrentIndex(idx)
        form.addRow("Type:", self._type_combo)

        self._desc_edit = QLineEdit(self._step.get("description", ""))
        form.addRow("Description:", self._desc_edit)

        self._target_edit = QLineEdit(self._step.get("target", ""))
        self._target_edit.setPlaceholderText("Target name for click type")
        self._target_edit.textChanged.connect(self._on_target_changed)
        form.addRow("Target:", self._target_edit)

        # Target Type combo
        self._target_type_combo = QComboBox()
        self._target_type_combo.addItems(_TARGET_TYPES)
        cur_tt = self._step.get("target_type", "auto")
        tt_idx = _TARGET_TYPES.index(cur_tt) if cur_tt in _TARGET_TYPES else 0
        self._target_type_combo.setCurrentIndex(tt_idx)
        self._target_type_combo.currentTextChanged.connect(self._on_target_type_changed)

        self._registry_hint = QLabel("")
        self._registry_hint.setStyleSheet("color: #555555; font-size: 11px;")

        tt_row = QHBoxLayout()
        tt_row.addWidget(self._target_type_combo)
        tt_row.addWidget(self._registry_hint)
        tt_row.addStretch()
        tt_container = QWidget()
        tt_container.setLayout(tt_row)
        form.addRow("Target Type:", tt_container)

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

        # Create spinboxes (set values BEFORE connecting valueChanged signals)
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

        # Populate spinboxes from existing ROI BEFORE connecting signals
        if self._roi is not None:
            x, y, w, h = self._roi
            self._spin_x.setValue(x)
            self._spin_y.setValue(y)
            self._spin_w.setValue(w)
            self._spin_h.setValue(h)

        # Connect valueChanged AFTER values are initialized
        for spin in (self._spin_x, self._spin_y, self._spin_w, self._spin_h):
            spin.valueChanged.connect(self._sync_roi_from_spinboxes)

        roi_spin_row = QHBoxLayout()
        for spin in (self._spin_x, self._spin_y, self._spin_w, self._spin_h):
            roi_spin_row.addWidget(spin)
        roi_spin_row.addStretch()
        roi_spin_container = QWidget()
        roi_spin_container.setLayout(roi_spin_row)
        form.addRow("ROI:", roi_spin_container)

        # button_text field (existing concept, now with enable/disable)
        self._button_text_edit = QLineEdit(self._step.get("button_text", ""))
        self._button_text_edit.setPlaceholderText("Text to find via OCR")
        form.addRow("Button Text:", self._button_text_edit)

        # yolo_class field (new)
        self._yolo_class_edit = QLineEdit(self._step.get("yolo_class", ""))
        self._yolo_class_edit.setPlaceholderText("YOLO detection class name")
        form.addRow("YOLO Class:", self._yolo_class_edit)

        self._enabled_chk = QCheckBox()
        self._enabled_chk.setChecked(self._step.get("enabled", True))
        form.addRow("Enabled:", self._enabled_chk)

        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        # Initialize field states
        self._update_field_states(self._target_type_combo.currentText())
        self._update_registry_hint(self._target_edit.text().strip())

    def _on_target_changed(self, text: str) -> None:
        cur_tt = self._target_type_combo.currentText()
        if cur_tt == "auto":
            self._update_registry_hint(text.strip())

    def _update_registry_hint(self, target: str) -> None:
        if not _QT_AVAILABLE:
            return
        if not target:
            self._registry_hint.setText("")
            return
        try:
            from src.class_registry import ClassRegistry

            registry = ClassRegistry.load()
            tt = registry.get_type(target)
            if tt is not None:
                self._registry_hint.setText(f"(registry: {tt})")
            else:
                self._registry_hint.setText("(not in registry)")
        except Exception:  # noqa: BLE001
            self._registry_hint.setText("")

    def _on_target_type_changed(self, text: str) -> None:
        self._update_field_states(text)
        if text == "auto":
            self._update_registry_hint(self._target_edit.text().strip())
        else:
            self._registry_hint.setText("")

    def _update_field_states(self, target_type: str) -> None:
        if not _QT_AVAILABLE:
            return
        if target_type == "NON_TEXT":
            self._button_text_edit.setEnabled(False)
            self._button_text_edit.setStyleSheet("color: #333333; background: #dddddd;")
            self._yolo_class_edit.setEnabled(True)
            self._yolo_class_edit.setStyleSheet("")
        else:
            # TEXT or auto — enable button_text, disable yolo_class
            self._button_text_edit.setEnabled(True)
            self._button_text_edit.setStyleSheet("")
            self._yolo_class_edit.setEnabled(False)
            self._yolo_class_edit.setStyleSheet("color: #333333; background: #dddddd;")

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
        # Block signals while setting to prevent double-sync
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

    def _on_pick_roi(self) -> None:
        if not _QT_AVAILABLE:
            return
        self.window().hide()
        overlay = _RoiOverlayWindow(parent=None)
        overlay.roi_confirmed.connect(self._on_roi_confirmed)
        overlay.roi_cancelled.connect(self._on_roi_cancelled)
        overlay.show()

    def _on_accept(self) -> None:
        if not _QT_AVAILABLE:
            return
        if not self._id_edit.text().strip():
            QMessageBox.warning(self, "Input Error", "ID is required.")
            return
        if not self._name_edit.text().strip():
            QMessageBox.warning(self, "Input Error", "Name is required.")
            return
        self.accept()

    def get_step(self) -> Dict[str, Any]:
        step: Dict[str, Any] = dict(self._step)
        if _QT_AVAILABLE:
            step["id"] = self._id_edit.text().strip()
            step["name"] = self._name_edit.text().strip()
            step["type"] = self._type_combo.currentText()
            step["description"] = self._desc_edit.text().strip()
            step["enabled"] = self._enabled_chk.isChecked()
            t = self._target_edit.text().strip()
            if t:
                step["target"] = t
            # target_type: omit if "auto"
            tt = self._target_type_combo.currentText()
            if tt != "auto":
                step["target_type"] = tt
            elif "target_type" in step:
                del step["target_type"]
            # ROI: omit if None
            if self._roi is not None:
                step["roi"] = list(self._roi)
            elif "roi" in step:
                del step["roi"]
            # yolo_class: include if NON_TEXT and non-empty
            yolo_cls = self._yolo_class_edit.text().strip()
            if yolo_cls and tt == "NON_TEXT":
                step["yolo_class"] = yolo_cls
            elif "yolo_class" in step and tt != "NON_TEXT":
                del step["yolo_class"]
            elif yolo_cls:
                step["yolo_class"] = yolo_cls
            elif not yolo_cls and "yolo_class" in step:
                del step["yolo_class"]
            # button_text: from field
            bt = self._button_text_edit.text().strip()
            if bt:
                step["button_text"] = bt
            elif "button_text" in step:
                del step["button_text"]
        return step


# ---------------------------------------------------------------------------
# SOP Editor Panel
# ---------------------------------------------------------------------------


class SopEditorPanel(QWidget):  # type: ignore[misc]
    """SOP Step Editor tab."""

    def __init__(
        self,
        sop_path: Optional[Path] = None,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._sop_path = sop_path or Path("assets/sop_steps.json")
        self._steps: List[Dict[str, Any]] = []
        self._dirty = False
        self._setup_ui()
        self._load_steps()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_steps(self) -> List[Dict[str, Any]]:
        return list(self._steps)

    def validate_config(self) -> List[str]:
        """Check all steps. Return list of warning strings (empty = ok)."""
        warnings: List[str] = []
        try:
            from src.class_registry import ClassRegistry

            registry = ClassRegistry.load()
        except Exception:  # noqa: BLE001
            registry = None  # type: ignore[assignment]

        for step in self._steps:
            target = step.get("target")
            if not target:
                continue
            if registry is not None:
                # Warning: target not in registry
                if registry.get_type(target) is None:
                    warnings.append(
                        f"Step '{step['id']}': target '{target}' not in class_registry"
                    )
                # Warning: NON_TEXT step has button_text set
                eff_type = step.get("target_type") or registry.get_type(target)
                if eff_type == "NON_TEXT" and step.get("button_text"):
                    warnings.append(
                        f"Step '{step['id']}': NON_TEXT target has button_text set"
                        " (OCR will be skipped)"
                    )
        return warnings

    # ------------------------------------------------------------------
    # Private — UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        if not _QT_AVAILABLE:
            return

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header = QLabel("📋 SOP Step Editor")
        header.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(header)

        # Table — 7 columns: ID | Name | Type | Target Type | ROI | Description | Enabled
        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["ID", "Name", "Type", "Target Type", "ROI", "Description", "Enabled"]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.Stretch
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.doubleClicked.connect(self._on_edit)
        layout.addWidget(self._table)

        # Buttons
        btn_row = QHBoxLayout()

        btn_add = QPushButton("➕ Add")
        btn_add.clicked.connect(self._on_add)

        btn_edit = QPushButton("✏ Edit")
        btn_edit.clicked.connect(self._on_edit)

        btn_del = QPushButton("🗑 Delete")
        btn_del.clicked.connect(self._on_delete)

        btn_up = QPushButton("⬆ Move Up")
        btn_up.clicked.connect(self._on_move_up)

        btn_down = QPushButton("⬇ Move Down")
        btn_down.clicked.connect(self._on_move_down)

        self._btn_validate = QPushButton("🔍 Validate Config")
        self._btn_validate.clicked.connect(self._on_validate)

        self._btn_save = QPushButton("💾 Save")
        self._btn_save.setStyleSheet(
            "background-color: #2196f3; color: white; font-weight: bold; padding: 6px 16px;"
        )
        self._btn_save.clicked.connect(self._on_save)

        for btn in [btn_add, btn_edit, btn_del, btn_up, btn_down]:
            btn_row.addWidget(btn)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_validate)
        btn_row.addWidget(self._btn_save)
        layout.addLayout(btn_row)

    def _refresh_table(self) -> None:
        if not _QT_AVAILABLE:
            return
        self._table.setRowCount(len(self._steps))
        for row, step in enumerate(self._steps):
            self._table.setItem(row, 0, QTableWidgetItem(step.get("id", "")))
            self._table.setItem(row, 1, QTableWidgetItem(step.get("name", "")))
            self._table.setItem(row, 2, QTableWidgetItem(step.get("type", "")))

            # Target Type column
            tt = step.get("target_type")
            if tt == "TEXT":
                tt_display = "🔤 TEXT"
            elif tt == "NON_TEXT":
                tt_display = "👁 NON_TEXT"
            else:
                tt_display = "—"
            self._table.setItem(row, 3, QTableWidgetItem(tt_display))

            # ROI column
            roi = step.get("roi")
            if roi and len(roi) == 4:
                roi_display = str(roi)
            else:
                roi_display = "full"
            self._table.setItem(row, 4, QTableWidgetItem(roi_display))

            self._table.setItem(row, 5, QTableWidgetItem(step.get("description", "")))
            enabled = "✓" if step.get("enabled", True) else "✗"
            self._table.setItem(row, 6, QTableWidgetItem(enabled))

    def _load_steps(self) -> None:
        if not self._sop_path.exists():
            return
        try:
            data = json.loads(self._sop_path.read_text(encoding="utf-8"))
            self._steps = data.get("steps", [])
            self._refresh_table()
        except Exception as exc:  # noqa: BLE001
            if _QT_AVAILABLE:
                QMessageBox.warning(
                    self, "Load Error", f"Failed to load sop_steps.json:\n{exc}"
                )

    def _on_add(self) -> None:
        if not _QT_AVAILABLE:
            return
        dlg = _StepEditDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._steps.append(dlg.get_step())
            self._dirty = True
            self._refresh_table()

    def _on_edit(self) -> None:
        if not _QT_AVAILABLE:
            return
        row = self._table.currentRow()
        if row < 0:
            return
        dlg = _StepEditDialog(step=self._steps[row], parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._steps[row] = dlg.get_step()
            self._dirty = True
            self._refresh_table()

    def _on_delete(self) -> None:
        if not _QT_AVAILABLE:
            return
        row = self._table.currentRow()
        if row < 0:
            return
        name = self._steps[row].get("name", "?")
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete step '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._steps.pop(row)
            self._dirty = True
            self._refresh_table()

    def _on_move_up(self) -> None:
        row = self._table.currentRow()
        if row > 0:
            self._steps[row], self._steps[row - 1] = (
                self._steps[row - 1],
                self._steps[row],
            )
            self._dirty = True
            self._refresh_table()
            self._table.selectRow(row - 1)

    def _on_move_down(self) -> None:
        row = self._table.currentRow()
        if 0 <= row < len(self._steps) - 1:
            self._steps[row], self._steps[row + 1] = (
                self._steps[row + 1],
                self._steps[row],
            )
            self._dirty = True
            self._refresh_table()
            self._table.selectRow(row + 1)

    def _on_validate(self) -> None:
        if not _QT_AVAILABLE:
            return
        warnings = self.validate_config()
        if not warnings:
            QMessageBox.information(self, "Validate Config", "✅ All steps look good!")
        else:
            msg = "\n".join(f"⚠ {w}" for w in warnings)
            QMessageBox.warning(self, "Validate Config", msg)

    def _on_save(self) -> None:
        if not _QT_AVAILABLE:
            return
        try:
            data = {"version": "1.2", "steps": self._steps}
            self._sop_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            self._dirty = False
            QMessageBox.information(self, "Saved", "sop_steps.json has been saved.")
            # Notify MainWindow to reload steps
            parent = self.parent()
            while parent:
                if hasattr(parent, "reload_sop_steps"):
                    parent.reload_sop_steps()  # type: ignore[union-attr]
                    break
                parent = parent.parent() if hasattr(parent, "parent") else None
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Save Error", f"Save failed:\n{exc}")
