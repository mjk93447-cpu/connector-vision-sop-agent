"""
Tab 2 — Vision Canvas Panel.

Displays a live screenshot with YOLO bounding-box overlays.
Phase 1: static placeholder + capture button.
Phase 2: live PyAutoGUI screenshot + YOLO bbox QPainter overlay.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap
    from PyQt6.QtWidgets import (
        QHBoxLayout,
        QLabel,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QVBoxLayout,
        QWidget,
    )

    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False
    QWidget = object  # type: ignore[assignment,misc]


class VisionPanel(QWidget):  # type: ignore[misc]
    """Vision Canvas tab — screenshot + YOLO bbox overlay."""

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._detections: List[Dict[str, Any]] = []
        self._pixmap: Optional[Any] = None
        self._setup_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_screenshot(self, pixmap: Any) -> None:
        """Update the displayed screenshot (QPixmap)."""
        if not _QT_AVAILABLE:
            return
        self._pixmap = pixmap
        self._render()

    def set_detections(self, detections: List[Dict[str, Any]]) -> None:
        """Update YOLO detections: [{'label': str, 'bbox': [x,y,w,h], 'conf': float}]."""
        self._detections = detections
        self._render()

    def clear(self) -> None:
        if not _QT_AVAILABLE:
            return
        self._pixmap = None
        self._detections = []
        self._canvas.setText("📷 스크린샷 없음 — [캡처] 버튼을 눌러 촬영하세요")

    # ------------------------------------------------------------------
    # Private — UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        if not _QT_AVAILABLE:
            return

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header = QLabel("👁 비전 캔버스")
        header.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(header)

        # Canvas inside scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._canvas = QLabel()
        self._canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._canvas.setText("📷 스크린샷 없음 — [캡처] 버튼을 눌러 촬영하세요")
        self._canvas.setStyleSheet(
            "background: #263238; color: #90a4ae; font-size: 14px;"
        )
        self._canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        scroll.setWidget(self._canvas)
        layout.addWidget(scroll)

        # Buttons
        btn_row = QHBoxLayout()
        btn_capture = QPushButton("📷 캡처")
        btn_capture.setToolTip("현재 화면을 캡처하여 YOLO 분석")
        btn_capture.clicked.connect(self._on_capture)

        btn_clear = QPushButton("🗑 지우기")
        btn_clear.clicked.connect(self.clear)

        self._lbl_status = QLabel("검출: 0개")
        self._lbl_status.setStyleSheet("color: #607d8b;")

        btn_row.addWidget(btn_capture)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        btn_row.addWidget(self._lbl_status)
        layout.addLayout(btn_row)

    def _render(self) -> None:
        """Draw pixmap + bbox overlays onto the canvas label."""
        if not _QT_AVAILABLE or self._pixmap is None:
            return

        # Clone pixmap and paint bboxes
        pmap = self._pixmap.copy()
        if self._detections:
            painter = QPainter(pmap)
            pen = QPen(QColor("#ff5722"), 3)
            painter.setPen(pen)
            for det in self._detections:
                bbox = det.get("bbox", [])
                if len(bbox) >= 4:
                    x, y, w, h = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
                    painter.drawRect(x, y, w, h)
                    label = det.get("label", "")
                    conf = det.get("conf", 0.0)
                    painter.drawText(x + 2, y - 4, f"{label} {conf:.2f}")
            painter.end()

        # Scale to fit canvas
        scaled = pmap.scaled(
            self._canvas.width(),
            self._canvas.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._canvas.setPixmap(scaled)
        n = len(self._detections)
        self._lbl_status.setText(f"검출: {n}개")

    def _on_capture(self) -> None:
        """Capture current screen (Phase 2 — placeholder for Phase 1)."""
        if not _QT_AVAILABLE:
            return
        try:
            import pyautogui  # optional in Phase 1

            screenshot = pyautogui.screenshot()
            # Convert PIL image → QPixmap
            from io import BytesIO

            buf = BytesIO()
            screenshot.save(buf, format="PNG")
            buf.seek(0)
            pmap = QPixmap()
            pmap.loadFromData(buf.read())
            self.set_screenshot(pmap)
        except Exception as exc:  # noqa: BLE001
            self._canvas.setText(f"캡처 실패: {exc}")
