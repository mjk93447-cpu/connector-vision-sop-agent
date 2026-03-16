"""
Tab 1 — Run SOP Panel.

Shows the list of SOP steps, a log output area, and Run/Stop buttons.
Connects to SopWorker for background execution.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from PyQt6.QtCore import Qt, pyqtSlot
    from PyQt6.QtGui import QColor, QTextCursor
    from PyQt6.QtWidgets import (
        QHBoxLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QPushButton,
        QSplitter,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False
    QWidget = object  # type: ignore[assignment,misc]


class SopPanel(QWidget):  # type: ignore[misc]
    """Run SOP tab — step list + log + control buttons."""

    def __init__(
        self,
        steps: Optional[List[Dict[str, Any]]] = None,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._steps: List[Dict[str, Any]] = steps or []
        self._worker: Any = None
        self._setup_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_steps(self, steps: List[Dict[str, Any]]) -> None:
        """Reload step list (called when sop_steps.json changes)."""
        self._steps = steps
        self._refresh_step_list()

    def append_log(self, text: str) -> None:
        """Append a line to the log area."""
        if not _QT_AVAILABLE:
            return
        self._log.append(text)
        self._log.moveCursor(QTextCursor.MoveOperation.End)

    def mark_step(self, index: int, running: bool = True) -> None:
        """Highlight the currently running step."""
        if not _QT_AVAILABLE:
            return
        for i in range(self._step_list.count()):
            item = self._step_list.item(i)
            if item is None:
                continue
            if i == index:
                fg = QColor("#ffffff")
                bg = QColor("#2196f3") if running else QColor("#4caf50")
            else:
                fg = QColor("#000000")
                bg = QColor("#ffffff")
            item.setForeground(fg)
            item.setBackground(bg)

    def mark_step_done(self, index: int, success: bool) -> None:
        """Mark a step as done (green=ok, red=fail)."""
        if not _QT_AVAILABLE:
            return
        item = self._step_list.item(index)
        if item is None:
            return
        bg = QColor("#c8e6c9") if success else QColor("#ffcdd2")
        item.setBackground(bg)
        item.setForeground(QColor("#000000"))

    def set_running(self, running: bool) -> None:
        """Toggle button state."""
        if not _QT_AVAILABLE:
            return
        self._btn_run.setEnabled(not running)
        self._btn_stop.setEnabled(running)

    # ------------------------------------------------------------------
    # Private — UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        if not _QT_AVAILABLE:
            return

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header label
        header = QLabel("📋 SOP 실행")
        header.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(header)

        # Splitter: step list (left) + log (right)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Step list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("SOP 단계:"))
        self._step_list = QListWidget()
        self._step_list.setFixedWidth(220)
        left_layout.addWidget(self._step_list)
        splitter.addWidget(left_widget)

        # Log output
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("실행 로그:"))
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 12px; background: #1e1e1e; color: #d4d4d4;"
        )
        right_layout.addWidget(self._log)
        splitter.addWidget(right_widget)

        splitter.setSizes([220, 580])
        layout.addWidget(splitter)

        # Buttons
        btn_layout = QHBoxLayout()
        self._btn_run = QPushButton("▶ SOP 실행")
        self._btn_run.setStyleSheet(
            "background-color: #4caf50; color: white; font-weight: bold; padding: 8px 20px;"
        )
        self._btn_stop = QPushButton("⏹ 중지")
        self._btn_stop.setStyleSheet(
            "background-color: #f44336; color: white; padding: 8px 20px;"
        )
        self._btn_stop.setEnabled(False)

        btn_clear = QPushButton("🗑 로그 지우기")
        btn_clear.clicked.connect(self._log.clear)

        btn_layout.addWidget(self._btn_run)
        btn_layout.addWidget(self._btn_stop)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_clear)
        layout.addLayout(btn_layout)

        self._refresh_step_list()

    def _refresh_step_list(self) -> None:
        if not _QT_AVAILABLE:
            return
        self._step_list.clear()
        for step in self._steps:
            name = step.get("name", step.get("id", "?"))
            step_type = step.get("type", "")
            enabled = step.get("enabled", True)
            label = f"{'☑' if enabled else '☐'} {name}  [{step_type}]"
            item = QListWidgetItem(label)
            if not enabled:
                item.setForeground(QColor("#9e9e9e"))
            self._step_list.addItem(item)

    # ------------------------------------------------------------------
    # Slots (connected by MainWindow)
    # ------------------------------------------------------------------

    @pyqtSlot(int, str)
    def on_step_started(self, index: int, name: str) -> None:
        self.mark_step(index, running=True)

    @pyqtSlot(int, str, bool, str)
    def on_step_finished(self, index: int, name: str, success: bool, msg: str) -> None:
        self.mark_step_done(index, success)

    @pyqtSlot(str)
    def on_log_message(self, text: str) -> None:
        self.append_log(text)

    @pyqtSlot(bool, str)
    def on_sop_finished(self, success: bool, summary: str) -> None:
        self.set_running(False)
        status = "✅ 완료" if success else "❌ 실패"
        self.append_log(f"\n{status}: {summary}")
