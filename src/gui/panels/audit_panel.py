"""
Tab 6 — Audit History Panel.

Displays config change audit log entries from logs/config_audit_{line_id}.jsonl.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

try:
    from PyQt6.QtWidgets import (
        QGroupBox,
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

        header = QLabel("📊 Audit Log — Config Change History")
        header.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(header)

        # Splitter: table (top) + detail (bottom)
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Table
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Timestamp", "Line ID", "User", "Action", "Changed Keys"]
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
        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.clicked.connect(self.refresh)
        btn_row.addWidget(btn_refresh)
        btn_row.addStretch()
        self._lbl_count = QLabel("0 records")
        self._lbl_count.setStyleSheet("color: #607d8b;")
        btn_row.addWidget(self._lbl_count)
        layout.addLayout(btn_row)

        # M4: SOP Pattern Summary (CycleDetector)
        pattern_grp = QGroupBox("📈 SOP Pattern Summary (last 20 runs)")
        pattern_layout = QVBoxLayout(pattern_grp)

        btn_pattern_row = QHBoxLayout()
        btn_load_patterns = QPushButton("🔄 Load Patterns")
        btn_load_patterns.clicked.connect(self._refresh_pattern_summary)
        btn_pattern_row.addWidget(btn_load_patterns)
        btn_pattern_row.addStretch()
        pattern_layout.addLayout(btn_pattern_row)

        self._txt_patterns = QTextEdit()
        self._txt_patterns.setReadOnly(True)
        self._txt_patterns.setMaximumHeight(160)
        self._txt_patterns.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 11px; background: #f9f9f9;"
        )
        self._txt_patterns.setPlaceholderText(
            "No SOP run history yet. Run SOP from the ▶ Run SOP tab to record patterns."
        )
        pattern_layout.addWidget(self._txt_patterns)
        layout.addWidget(pattern_grp)

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

        self._lbl_count.setText(f"{len(self._entries)} records")
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
            self._detail.setPlainText(f"Error: {msg}")

    def _refresh_pattern_summary(self) -> None:
        """M4: Load CycleDetector summary and display in the pattern text box."""
        if not _QT_AVAILABLE:
            return
        try:
            from src.cycle_detector import CycleDetector  # noqa: PLC0415

            cd = CycleDetector()
            summary = cd.build_improvement_summary(n_recent=20)
            count = summary.get("sample_count", 0)
            if count == 0:
                self._txt_patterns.setPlainText(
                    "No SOP run history recorded yet.\n"
                    "Run SOP from the ▶ Run SOP tab to start recording patterns."
                )
                return

            lines = [f"Recorded runs: {count}", ""]

            # Per-step stats
            step_stats = summary.get("step_stats", {})
            if step_stats:
                lines.append("Per-step success rates:")
                for step_id, stats in sorted(step_stats.items()):
                    rate = stats.get("success_rate", 0)
                    avg_ms = stats.get("avg_ms", 0)
                    method = stats.get("dominant_method", "?")
                    bar = "✓" if rate >= 0.9 else ("⚠" if rate >= 0.5 else "✗")
                    lines.append(
                        f"  {bar} {step_id:<22} "
                        f"{rate*100:.0f}% ok | {avg_ms} ms | {method}"
                    )

            # Cycle patterns
            patterns = summary.get("patterns", [])
            if patterns:
                lines.append("")
                lines.append(f"Repeating patterns detected: {len(patterns)}")
                for p in patterns[:3]:  # show top 3
                    steps_str = "→".join(p.get("steps", []))
                    cnt = p.get("sample_count", 0)
                    avg = p.get("avg_ms", 0)
                    lines.append(f"  [{cnt}x] {steps_str} ({avg} ms avg)")

            self._txt_patterns.setPlainText("\n".join(lines))
        except Exception as exc:  # noqa: BLE001
            self._txt_patterns.setPlainText(f"Error loading patterns: {exc}")
