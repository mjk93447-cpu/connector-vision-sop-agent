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
    pyqtSlot = lambda *a, **kw: (lambda f: f)  # type: ignore[assignment]  # noqa: E731


class SopPanel(QWidget):  # type: ignore[misc]
    """Run SOP tab — step list + log + control buttons."""

    def __init__(
        self,
        steps: Optional[List[Dict[str, Any]]] = None,
        ocr_engine: Any = None,
        vision_engine: Any = None,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._steps: List[Dict[str, Any]] = steps or []
        self._worker: Any = None
        self._ocr_engine: Any = ocr_engine
        self._vision_engine: Any = vision_engine
        self._setup_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_steps(self, steps: List[Dict[str, Any]]) -> None:
        """Reload step list (called when sop_steps.json changes)."""
        self._steps = steps
        self._refresh_step_list()

    def set_ocr_engine(self, ocr: Any) -> None:
        """Inject an OCREngine instance for the Test OCR button."""
        self._ocr_engine = ocr

    def set_vision_engine(self, vision: Any) -> None:
        """Inject a VisionEngine instance for screen capture in OCR test."""
        self._vision_engine = vision

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
        header = QLabel("📋 Run SOP")
        header.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(header)

        # Splitter: step list (left) + log (right)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Step list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("SOP Steps:"))
        self._step_list = QListWidget()
        self._step_list.setFixedWidth(220)
        left_layout.addWidget(self._step_list)
        splitter.addWidget(left_widget)

        # Log output
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("Execution Log:"))
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
        self._btn_run = QPushButton("▶ Run SOP")
        self._btn_run.setStyleSheet(
            "background-color: #4caf50; color: white; font-weight: bold; padding: 8px 20px;"
        )
        self._btn_stop = QPushButton("⏹ Stop")
        self._btn_stop.setStyleSheet(
            "background-color: #f44336; color: white; padding: 8px 20px;"
        )
        self._btn_stop.setEnabled(False)

        btn_clear = QPushButton("🗑 Clear Log")
        btn_clear.clicked.connect(self._log.clear)

        btn_test_ocr = QPushButton("🔍 Test OCR")
        btn_test_ocr.setToolTip("Capture screen and run OCR to verify detection")
        btn_test_ocr.clicked.connect(self._on_test_ocr)

        btn_layout.addWidget(self._btn_run)
        btn_layout.addWidget(self._btn_stop)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_test_ocr)
        btn_layout.addWidget(btn_clear)
        layout.addLayout(btn_layout)

        self._refresh_step_list()

    def _on_test_ocr(self) -> None:
        """Capture current screen and run OCR, display results in log."""
        self.append_log("[OCR Test] Capturing screen...")
        try:
            if self._vision_engine is not None:
                img = self._vision_engine.capture_screen()
            else:
                import numpy as np  # noqa: PLC0415
                import pyautogui  # noqa: PLC0415
                import cv2  # noqa: PLC0415

                img = np.array(pyautogui.screenshot())
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

            if self._ocr_engine is not None:
                regions = self._ocr_engine.scan_all(img)
                backend = getattr(self._ocr_engine, "_backend", "unknown")
                self.append_log(
                    f"[OCR Test] Backend: {backend} | "
                    f"Detected {len(regions)} region(s)"
                )
                for r in regions[:20]:
                    self.append_log(f"  '{r.text}' at {r.center}")
                if not regions:
                    self.append_log(
                        "[OCR Test] FAILED: 0 regions — OCR non-functional. "
                        "Check console for details."
                    )
            else:
                self.append_log("[OCR Test] OCR engine not available.")
        except Exception as exc:  # noqa: BLE001
            self.append_log(f"[OCR Test] Error: {exc}")

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
        status = "✅ Complete" if success else "❌ Failed"
        self.append_log(f"\n{status}: {summary}")
