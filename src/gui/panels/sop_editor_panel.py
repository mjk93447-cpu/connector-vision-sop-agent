"""
Tab 4 — SOP Step Editor Panel.

Allows engineers to add, delete, reorder, and toggle SOP steps
without editing code. Changes are saved to assets/sop_steps.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
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


# ---------------------------------------------------------------------------
# Step edit dialog
# ---------------------------------------------------------------------------


class _StepEditDialog(QDialog):  # type: ignore[misc]
    def __init__(
        self, step: Optional[Dict[str, Any]] = None, parent: Any = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit SOP Step" if step else "Add New SOP Step")
        self.setMinimumWidth(380)
        self._step = step or {}
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
        form.addRow("Target:", self._target_edit)

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

        # Table
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["ID", "Name", "Type", "Description", "Enabled"]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
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

        self._btn_save = QPushButton("💾 Save")
        self._btn_save.setStyleSheet(
            "background-color: #2196f3; color: white; font-weight: bold; padding: 6px 16px;"
        )
        self._btn_save.clicked.connect(self._on_save)

        for btn in [btn_add, btn_edit, btn_del, btn_up, btn_down]:
            btn_row.addWidget(btn)
        btn_row.addStretch()
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
            self._table.setItem(row, 3, QTableWidgetItem(step.get("description", "")))
            enabled = "✓" if step.get("enabled", True) else "✗"
            self._table.setItem(row, 4, QTableWidgetItem(enabled))

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

    def _on_save(self) -> None:
        if not _QT_AVAILABLE:
            return
        try:
            data = {"version": "1.0", "steps": self._steps}
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
