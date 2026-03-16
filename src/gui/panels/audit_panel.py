"""
Tab 6 — Audit History Panel.

Displays config change audit log entries from logs/config_audit_{line_id}.jsonl.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

try:
    from PyQt6.QtWidgets import (
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QPushButton,
        QSplitter,
        QTableWidget,
        QTableWidgetItem,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
    from PyQt6.QtCore import Qt

    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False
    QWidget = object  # type: ignore[assignment,misc]


class AuditPanel(QWidget):  # type: ignore[misc]
    """Audit History tab."""

    def __init__(
        self,
        audit_log: Optional[Any] = None,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._audit_log = audit_log
        self._entries: List[Dict[str, Any]] = []
        self._setup_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_audit_log(self, audit_log: Any) -> None:
        self._audit_log = audit_log

    def refresh(self) -> None:
        """Reload entries from the audit log file."""
        if self._audit_log is None:
            return
        try:
            self._entries = self._audit_log.get_history(limit=100)
            self._refresh_table()
        except Exception as exc:  # noqa: BLE001
            self._show_error(str(exc))

    # ------------------------------------------------------------------
    # Private — UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        if not _QT_AVAILABLE:
            return

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header = QLabel("📊 Audit 이력 — Config 변경 기록")
        header.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(header)

        # Splitter: table (top) + detail (bottom)
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Table
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["시간", "라인ID", "사용자", "액션", "변경 키"]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        splitter.addWidget(self._table)

        # Detail pane
        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 11px; background: #f5f5f5;"
        )
        splitter.addWidget(self._detail)
        splitter.setSizes([300, 150])
        layout.addWidget(splitter)

        # Buttons
        btn_row = QHBoxLayout()
        btn_refresh = QPushButton("🔄 새로 고침")
        btn_refresh.clicked.connect(self.refresh)
        btn_row.addWidget(btn_refresh)
        btn_row.addStretch()
        self._lbl_count = QLabel("0개 기록")
        self._lbl_count.setStyleSheet("color: #607d8b;")
        btn_row.addWidget(self._lbl_count)
        layout.addLayout(btn_row)

    def _refresh_table(self) -> None:
        if not _QT_AVAILABLE:
            return
        self._table.setRowCount(len(self._entries))
        for row, entry in enumerate(self._entries):
            ts = entry.get("ts", "")[:19]
            line_id = entry.get("line_id", "?")
            user = entry.get("username", "?")
            action = entry.get("action", "?")
            changes = entry.get("changes", {})
            keys = ", ".join(changes.keys()) if changes else ""

            self._table.setItem(row, 0, QTableWidgetItem(ts))
            self._table.setItem(row, 1, QTableWidgetItem(line_id))
            self._table.setItem(row, 2, QTableWidgetItem(user))
            self._table.setItem(row, 3, QTableWidgetItem(action))
            self._table.setItem(row, 4, QTableWidgetItem(keys))

        self._lbl_count.setText(f"{len(self._entries)}개 기록")
        self._detail.clear()

    def _on_selection_changed(self) -> None:
        if not _QT_AVAILABLE:
            return
        rows = self._table.selectedItems()
        if not rows:
            return
        row = self._table.currentRow()
        if 0 <= row < len(self._entries):
            entry = self._entries[row]
            self._detail.setPlainText(json.dumps(entry, ensure_ascii=False, indent=2))

    def _show_error(self, msg: str) -> None:
        if _QT_AVAILABLE:
            self._detail.setPlainText(f"오류: {msg}")
