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
    from PyQt6.QtCore import QRect, Qt
    from PyQt6.QtGui import QPainter, QPen, QPixmap
    from PyQt6.QtWidgets import (
        QAbstractItemView,
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
# ROI Picker Dialog
# ---------------------------------------------------------------------------


class _RoiPickerDialog(QDialog):  # type: ignore[misc]
    """Screenshot-based ROI selector. Shows current screen, user drags to select area."""

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pick ROI")
        self.setMinimumSize(600, 480)
        self._roi: Optional[Tuple[int, int, int, int]] = None
        self._scale_x: float = 1.0
        self._scale_y: float = 1.0
        self._orig_pixmap: Optional[Any] = None
        self._display_pixmap: Optional[Any] = None
        self._drag_start: Optional[Any] = None
        self._drag_end: Optional[Any] = None
        self._manual_mode = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        if not _QT_AVAILABLE:
            return
        layout = QVBoxLayout(self)

        header = QLabel("Drag to select ROI area. Press OK to confirm.")
        layout.addWidget(header)

        btn_capture = QPushButton("📷 Capture")
        btn_capture.clicked.connect(self._on_capture)
        layout.addWidget(btn_capture)

        # Image label for displaying screenshot
        self._img_label = QLabel("(No screenshot yet — click Capture)")
        self._img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_label.setMinimumHeight(300)
        self._img_label.setStyleSheet("background: #222; color: #aaa;")
        self._img_label.setMouseTracking(True)
        self._img_label.mousePressEvent = self._on_mouse_press  # type: ignore[method-assign]
        self._img_label.mouseMoveEvent = self._on_mouse_move  # type: ignore[method-assign]
        self._img_label.mouseReleaseEvent = self._on_mouse_release  # type: ignore[method-assign]
        layout.addWidget(self._img_label)

        self._coord_label = QLabel("x=0 y=0 w=0 h=0")
        layout.addWidget(self._coord_label)

        # Manual input (fallback mode)
        self._manual_widget = QWidget()
        manual_layout = QHBoxLayout(self._manual_widget)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.addWidget(QLabel("x:"))
        self._spin_x = QSpinBox()
        self._spin_x.setRange(0, 1920)
        manual_layout.addWidget(self._spin_x)
        manual_layout.addWidget(QLabel("y:"))
        self._spin_y = QSpinBox()
        self._spin_y.setRange(0, 1080)
        manual_layout.addWidget(self._spin_y)
        manual_layout.addWidget(QLabel("w:"))
        self._spin_w = QSpinBox()
        self._spin_w.setRange(0, 1920)
        manual_layout.addWidget(self._spin_w)
        manual_layout.addWidget(QLabel("h:"))
        self._spin_h = QSpinBox()
        self._spin_h.setRange(0, 1080)
        manual_layout.addWidget(self._spin_h)
        self._manual_widget.setVisible(False)
        layout.addWidget(self._manual_widget)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_capture(self) -> None:
        if not _QT_AVAILABLE:
            return
        try:
            import pyautogui  # type: ignore[import-untyped]

            screenshot = pyautogui.screenshot()
            orig_w, orig_h = screenshot.size

            # Convert PIL image to QPixmap
            from PyQt6.QtGui import QImage

            img_bytes = screenshot.tobytes("raw", "RGB")
            qimg = QImage(
                img_bytes, orig_w, orig_h, orig_w * 3, QImage.Format.Format_RGB888
            )
            self._orig_pixmap = QPixmap.fromImage(qimg)

            # Scale to max 900x500
            max_w, max_h = 900, 500
            scaled = self._orig_pixmap.scaled(
                max_w,
                max_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            display_w = scaled.width()
            display_h = scaled.height()
            self._scale_x = orig_w / display_w
            self._scale_y = orig_h / display_h
            self._display_pixmap = scaled
            self._img_label.setPixmap(scaled)
            self._drag_start = None
            self._drag_end = None
            self._roi = None
            self._coord_label.setText("x=0 y=0 w=0 h=0")
        except Exception:  # noqa: BLE001
            # Fallback: show manual spinboxes
            self._manual_mode = True
            self._manual_widget.setVisible(True)
            self._img_label.setText(
                "(Screenshot unavailable — enter coordinates manually)"
            )

    def _on_mouse_press(self, event: Any) -> None:
        if not _QT_AVAILABLE or self._display_pixmap is None:
            return
        self._drag_start = event.pos()
        self._drag_end = event.pos()

    def _on_mouse_move(self, event: Any) -> None:
        if not _QT_AVAILABLE or self._drag_start is None:
            return
        self._drag_end = event.pos()
        self._update_overlay()

    def _on_mouse_release(self, event: Any) -> None:
        if not _QT_AVAILABLE or self._drag_start is None:
            return
        self._drag_end = event.pos()
        self._update_overlay()
        self._compute_roi()

    def _update_overlay(self) -> None:
        if not _QT_AVAILABLE or self._display_pixmap is None:
            return
        if self._drag_start is None or self._drag_end is None:
            return
        pixmap_copy = self._display_pixmap.copy()
        painter = QPainter(pixmap_copy)
        pen = QPen(Qt.GlobalColor.red)
        pen.setWidth(2)
        painter.setPen(pen)
        rect = QRect(self._drag_start, self._drag_end).normalized()
        painter.drawRect(rect)
        painter.end()
        self._img_label.setPixmap(pixmap_copy)

    def _compute_roi(self) -> None:
        if not _QT_AVAILABLE or self._drag_start is None or self._drag_end is None:
            return
        rect = QRect(self._drag_start, self._drag_end).normalized()
        dx = int(rect.x() * self._scale_x)
        dy = int(rect.y() * self._scale_y)
        dw = int(rect.width() * self._scale_x)
        dh = int(rect.height() * self._scale_y)
        self._roi = (dx, dy, dw, dh)
        self._coord_label.setText(f"x={dx} y={dy} w={dw} h={dh}")

    def _on_accept(self) -> None:
        if self._manual_mode:
            x = self._spin_x.value()
            y = self._spin_y.value()
            w = self._spin_w.value()
            h = self._spin_h.value()
            self._roi = (x, y, w, h)
        self.accept()

    @property
    def roi(self) -> Optional[Tuple[int, int, int, int]]:
        return self._roi


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
        self._registry_hint.setStyleSheet("color: gray; font-size: 11px;")

        tt_row = QHBoxLayout()
        tt_row.addWidget(self._target_type_combo)
        tt_row.addWidget(self._registry_hint)
        tt_row.addStretch()
        tt_container = QWidget()
        tt_container.setLayout(tt_row)
        form.addRow("Target Type:", tt_container)

        # ROI field
        self._roi_label = QLabel("full screen")
        self._roi_label.setStyleSheet("font-style: italic; color: gray;")
        btn_roi = QPushButton("🎯 Pick ROI")
        btn_roi.clicked.connect(self._on_pick_roi)
        roi_row = QHBoxLayout()
        roi_row.addWidget(btn_roi)
        roi_row.addWidget(self._roi_label)
        roi_row.addStretch()
        roi_container = QWidget()
        roi_container.setLayout(roi_row)
        form.addRow("ROI:", roi_container)

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

        # Initialize ROI label
        if self._roi is not None:
            x, y, w, h = self._roi
            self._roi_label.setText(f"x={x} y={y} w={w} h={h}")
            self._roi_label.setStyleSheet("color: black;")

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
            self._button_text_edit.setStyleSheet("color: gray; background: #eee;")
            self._yolo_class_edit.setEnabled(True)
            self._yolo_class_edit.setStyleSheet("")
        else:
            # TEXT or auto — enable button_text, disable yolo_class
            self._button_text_edit.setEnabled(True)
            self._button_text_edit.setStyleSheet("")
            self._yolo_class_edit.setEnabled(False)
            self._yolo_class_edit.setStyleSheet("color: gray; background: #eee;")

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
