"""
Tab 7 — Training Panel.

Three sub-sections:
  1. BBox Annotation canvas  — draw labelled bounding boxes on images
  2. Dataset stats           — count of images/annotations per class
  3. Fine-tuning controls    — epochs, batch, start training → progress bar

Saving weights: "학습 시작 & 저장" button triggers TrainingWorker, which
saves best.pt to assets/models/yolo26x.pt without any EXE rebuild.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
    from PyQt6.QtGui import (
        QColor,
        QCursor,
        QImage,
        QPainter,
        QPen,
        QPixmap,
    )
    from PyQt6.QtWidgets import (
        QComboBox,
        QFileDialog,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSpinBox,
        QSplitter,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False
    QWidget = object  # type: ignore[assignment,misc]
    pyqtSignal = object  # type: ignore[assignment]

from src.training.dataset_manager import OLED_CLASSES, DatasetManager


# ---------------------------------------------------------------------------
# BBoxCanvas — interactive annotation widget
# ---------------------------------------------------------------------------


class BBoxCanvas(QWidget):  # type: ignore[misc]
    """Widget for drawing YOLO bounding box annotations on an image.

    Emits ``annotation_added(dict)`` when the user finishes drawing a box.
    """

    annotation_added: Any = pyqtSignal(dict) if _QT_AVAILABLE else object()  # type: ignore[assignment]

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._image: Optional[Any] = None        # QPixmap
        self._annotations: List[Dict[str, Any]] = []
        self._current_label: str = OLED_CLASSES[0]
        self._drawing = False
        self._start: Optional[Any] = None
        self._current_rect: Optional[Any] = None
        if _QT_AVAILABLE:
            self.setMouseTracking(True)
            self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
            self.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )

    def set_image(self, pixmap: Any) -> None:
        self._image = pixmap
        self._annotations = []
        self.update()

    def set_label(self, label: str) -> None:
        self._current_label = label

    def get_annotations(self) -> List[Dict[str, Any]]:
        return list(self._annotations)

    def clear_annotations(self) -> None:
        self._annotations = []
        self.update()

    def undo_last(self) -> None:
        if self._annotations:
            self._annotations.pop()
            self.update()

    # ------------------------------------------------------------------
    # Qt paint / mouse events
    # ------------------------------------------------------------------

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        if not _QT_AVAILABLE:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._image is not None:
            scaled = self._image.scaled(
                self.width(),
                self.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            # Centre offset
            ox = (self.width() - scaled.width()) // 2
            oy = (self.height() - scaled.height()) // 2
            painter.drawPixmap(ox, oy, scaled)

            # Saved annotations
            pen = QPen(QColor("#4caf50"), 2)
            painter.setPen(pen)
            for ann in self._annotations:
                r = self._ann_to_widget_rect(ann, scaled, ox, oy)
                painter.drawRect(r)
                painter.drawText(r.topLeft() + QPoint(2, -4), ann.get("label", ""))

        # In-progress rect
        if self._drawing and self._start and self._current_rect:
            pen2 = QPen(QColor("#ff9800"), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen2)
            painter.drawRect(self._current_rect)

        painter.end()

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        if not _QT_AVAILABLE or self._image is None:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._drawing = True
            self._start = event.pos()
            self._current_rect = QRect(self._start, self._start)
            self.update()

    def mouseMoveEvent(self, event: Any) -> None:  # noqa: N802
        if not _QT_AVAILABLE or not self._drawing or self._start is None:
            return
        self._current_rect = QRect(self._start, event.pos()).normalized()
        self.update()

    def mouseReleaseEvent(self, event: Any) -> None:  # noqa: N802
        if not _QT_AVAILABLE or not self._drawing or self._start is None:
            return
        self._drawing = False
        end = event.pos()
        rect = QRect(self._start, end).normalized()

        if rect.width() < 5 or rect.height() < 5:
            self._current_rect = None
            self.update()
            return

        # Convert widget coords → image pixel coords
        ann = self._widget_rect_to_ann(rect)
        if ann:
            self._annotations.append(ann)
            try:
                self.annotation_added.emit(ann)
            except Exception:  # noqa: BLE001
                pass
        self._current_rect = None
        self.update()

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------

    def _image_display_params(self) -> tuple[Any, int, int]:
        """Return (scaled_pixmap, offset_x, offset_y)."""
        if self._image is None or not _QT_AVAILABLE:
            return None, 0, 0
        scaled = self._image.scaled(
            self.width(),
            self.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        ox = (self.width() - scaled.width()) // 2
        oy = (self.height() - scaled.height()) // 2
        return scaled, ox, oy

    def _widget_rect_to_ann(self, rect: Any) -> Optional[Dict[str, Any]]:
        scaled, ox, oy = self._image_display_params()
        if scaled is None or scaled.width() == 0 or scaled.height() == 0:
            return None
        sw, sh = scaled.width(), scaled.height()
        iw, ih = self._image.width(), self._image.height()
        # pixel coords in original image
        x1 = max(0, int((rect.left() - ox) * iw / sw))
        y1 = max(0, int((rect.top() - oy) * ih / sh))
        x2 = min(iw, int((rect.right() - ox) * iw / sw))
        y2 = min(ih, int((rect.bottom() - oy) * ih / sh))
        if x2 <= x1 or y2 <= y1:
            return None
        return {"label": self._current_label, "bbox": [x1, y1, x2, y2]}

    def _ann_to_widget_rect(
        self, ann: Dict[str, Any], scaled: Any, ox: int, oy: int
    ) -> Any:
        if not _QT_AVAILABLE or self._image is None:
            return QRect()
        iw, ih = self._image.width(), self._image.height()
        sw, sh = scaled.width(), scaled.height()
        x1, y1, x2, y2 = ann["bbox"]
        wx1 = int(x1 * sw / iw) + ox
        wy1 = int(y1 * sh / ih) + oy
        wx2 = int(x2 * sw / iw) + ox
        wy2 = int(y2 * sh / ih) + oy
        return QRect(QPoint(wx1, wy1), QPoint(wx2, wy2))


# ---------------------------------------------------------------------------
# TrainingPanel — full Tab 7 widget
# ---------------------------------------------------------------------------


class TrainingPanel(QWidget):  # type: ignore[misc]
    """Tab 7: YOLO annotation + local fine-tuning panel."""

    # Emitted when training finishes with the output weights path
    training_finished: Any = pyqtSignal(str) if _QT_AVAILABLE else object()  # type: ignore[assignment]

    def __init__(
        self,
        dataset_manager: Optional[Any] = None,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._dm = dataset_manager or DatasetManager()
        self._current_image_name: Optional[str] = None
        self._current_bgr: Optional[Any] = None
        self._training_worker: Optional[Any] = None

        if _QT_AVAILABLE:
            self._setup_ui()

    # ------------------------------------------------------------------
    # Public API (called by MainWindow / TrainingWorker)
    # ------------------------------------------------------------------

    def set_image_for_annotation(self, bgr_arr: Any, name: str = "capture.png") -> None:
        """Load a BGR numpy array into the annotation canvas."""
        if not _QT_AVAILABLE:
            return

        self._current_image_name = name
        self._current_bgr = bgr_arr
        rgb = bgr_arr[:, :, ::-1].copy()
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self._canvas.set_image(QPixmap.fromImage(qimg))
        self._lbl_image_name.setText(f"이미지: {name}")

    def on_training_progress(self, epoch: int, total: int) -> None:
        if not _QT_AVAILABLE:
            return
        self._progress.setMaximum(total)
        self._progress.setValue(epoch)
        pct = int(epoch / total * 100) if total > 0 else 0
        self._log(f"  Epoch {epoch}/{total} — {pct}%")

    def on_training_done(self, weights_path: str) -> None:
        if not _QT_AVAILABLE:
            return
        self._log(f"✅ 학습 완료! 가중치 저장: {weights_path}")
        self._progress.setValue(self._progress.maximum())
        self._btn_train.setEnabled(True)
        try:
            self.training_finished.emit(weights_path)
        except Exception:  # noqa: BLE001
            pass

    def on_training_error(self, err: str) -> None:
        if not _QT_AVAILABLE:
            return
        self._log(f"❌ 학습 오류: {err}")
        self._btn_train.setEnabled(True)

    # ------------------------------------------------------------------
    # Private — UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        header = QLabel("🧠 YOLO 추가 학습 (로컬 파인튜닝)")
        header.setStyleSheet("font-size: 14px; font-weight: bold;")
        outer.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ---- Left: annotation canvas ---------------------------------
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 4, 0)

        # Image name + load buttons
        img_row = QHBoxLayout()
        self._lbl_image_name = QLabel("이미지 없음")
        btn_load = QPushButton("📁 이미지 열기")
        btn_load.setToolTip("파일에서 이미지를 불러와 어노테이션")
        btn_load.clicked.connect(self._on_load_image)
        btn_capture = QPushButton("📷 캡처")
        btn_capture.setToolTip("현재 화면을 캡처하여 어노테이션")
        btn_capture.clicked.connect(self._on_capture_screen)
        img_row.addWidget(self._lbl_image_name)
        img_row.addStretch()
        img_row.addWidget(btn_load)
        img_row.addWidget(btn_capture)
        lv.addLayout(img_row)

        # Canvas
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._canvas = BBoxCanvas()
        self._canvas.setMinimumSize(400, 300)
        self._canvas.annotation_added.connect(self._on_annotation_added)
        scroll.setWidget(self._canvas)
        lv.addWidget(scroll)

        # Label + annotation controls
        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel("클래스:"))
        self._combo_label = QComboBox()
        self._combo_label.addItems(OLED_CLASSES)
        self._combo_label.currentTextChanged.connect(self._canvas.set_label)
        ctrl_row.addWidget(self._combo_label)

        btn_undo = QPushButton("↩ 취소")
        btn_undo.setToolTip("마지막 bbox 취소")
        btn_undo.clicked.connect(self._canvas.undo_last)

        btn_save_ann = QPushButton("💾 어노테이션 저장")
        btn_save_ann.setToolTip("현재 이미지와 bbox를 데이터셋에 저장")
        btn_save_ann.clicked.connect(self._on_save_annotation)

        btn_clear = QPushButton("🗑 초기화")
        btn_clear.clicked.connect(self._canvas.clear_annotations)

        ctrl_row.addWidget(btn_undo)
        ctrl_row.addWidget(btn_clear)
        ctrl_row.addStretch()
        ctrl_row.addWidget(btn_save_ann)
        lv.addLayout(ctrl_row)

        splitter.addWidget(left)

        # ---- Right: stats + training controls ------------------------
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(4, 0, 0, 0)

        # Dataset stats group
        stats_grp = QGroupBox("📊 데이터셋 현황")
        sv = QVBoxLayout(stats_grp)
        self._txt_stats = QTextEdit()
        self._txt_stats.setReadOnly(True)
        self._txt_stats.setMaximumHeight(200)
        sv.addWidget(self._txt_stats)
        btn_refresh = QPushButton("새로고침")
        btn_refresh.clicked.connect(self._refresh_stats)
        sv.addWidget(btn_refresh)
        rv.addWidget(stats_grp)

        # Training config group
        train_grp = QGroupBox("⚙ 학습 설정")
        tv = QVBoxLayout(train_grp)

        row_epochs = QHBoxLayout()
        row_epochs.addWidget(QLabel("Epochs:"))
        self._spin_epochs = QSpinBox()
        self._spin_epochs.setRange(1, 200)
        self._spin_epochs.setValue(10)
        row_epochs.addWidget(self._spin_epochs)
        tv.addLayout(row_epochs)

        row_batch = QHBoxLayout()
        row_batch.addWidget(QLabel("Batch:"))
        self._spin_batch = QSpinBox()
        self._spin_batch.setRange(1, 32)
        self._spin_batch.setValue(4)
        row_batch.addWidget(self._spin_batch)
        tv.addLayout(row_batch)

        self._lbl_base = QLabel("기반 모델: yolo26x.pt (COCO pretrained, 최고 정확도, NMS-free)")
        self._lbl_base.setStyleSheet("color: #607d8b; font-size: 11px;")
        tv.addWidget(self._lbl_base)

        rv.addWidget(train_grp)

        # Train button + progress
        self._btn_train = QPushButton("🚀 학습 시작 & 저장")
        self._btn_train.setStyleSheet(
            "QPushButton { background: #1565c0; color: white; "
            "font-weight: bold; padding: 8px; border-radius: 4px; } "
            "QPushButton:disabled { background: #90a4ae; }"
        )
        self._btn_train.clicked.connect(self._on_start_training)
        rv.addWidget(self._btn_train)

        self._progress = QProgressBar()
        self._progress.setValue(0)
        rv.addWidget(self._progress)

        # Log output
        rv.addWidget(QLabel("학습 로그:"))
        self._txt_log = QTextEdit()
        self._txt_log.setReadOnly(True)
        rv.addWidget(self._txt_log)

        splitter.addWidget(right)
        splitter.setSizes([550, 350])
        outer.addWidget(splitter)

        self._refresh_stats()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_load_image(self) -> None:
        if not _QT_AVAILABLE:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "이미지 파일 열기", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff *.webp)",
        )
        if not path:
            return
        try:
            import cv2  # noqa: PLC0415
            bgr = cv2.imread(path)
            if bgr is None:
                raise ValueError("cv2.imread returned None")
            name = Path(path).name
            self.set_image_for_annotation(bgr, name)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "로드 실패", str(exc))

    def _on_capture_screen(self) -> None:
        if not _QT_AVAILABLE:
            return
        try:
            import numpy as np  # noqa: PLC0415
            import pyautogui  # noqa: PLC0415
            screenshot = pyautogui.screenshot()
            rgb = np.array(screenshot)
            bgr = rgb[:, :, ::-1].copy()
            self.set_image_for_annotation(bgr, "capture.png")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "캡처 실패", str(exc))

    def _on_annotation_added(self, ann: Dict[str, Any]) -> None:
        label = ann.get("label", "?")
        bbox = ann.get("bbox", [])
        self._log(f"  + bbox: {label} {bbox}")

    def _on_save_annotation(self) -> None:
        if not _QT_AVAILABLE:
            return
        if self._current_bgr is None:
            QMessageBox.warning(self, "저장 실패", "이미지를 먼저 로드하세요.")
            return
        annotations = self._canvas.get_annotations()
        if not annotations:
            QMessageBox.warning(self, "저장 실패", "Bbox가 없습니다. 먼저 영역을 표시하세요.")
            return
        name = self._current_image_name or "capture.png"
        img_path = self._dm.add_image_with_annotations(name, self._current_bgr, annotations)
        self._dm.save_dataset_yaml()
        self._log(f"✅ 저장 완료: {img_path} ({len(annotations)}개 bbox)")
        self._refresh_stats()
        self._canvas.clear_annotations()

    def _on_start_training(self) -> None:
        if not _QT_AVAILABLE:
            return
        stats = self._dm.get_stats()
        if stats["image_count"] == 0:
            QMessageBox.warning(
                self, "학습 불가",
                "어노테이션된 이미지가 없습니다.\n이미지를 추가하고 bbox를 저장한 뒤 학습하세요.",
            )
            return

        yaml_path = self._dm.save_dataset_yaml()
        epochs = self._spin_epochs.value()
        batch = self._spin_batch.value()

        self._log(f"▶ 학습 시작: {epochs} epochs, batch={batch}")
        self._log(f"  데이터셋: {yaml_path}")
        self._progress.setValue(0)
        self._progress.setMaximum(epochs)
        self._btn_train.setEnabled(False)

        # Import here to avoid circular imports at module load
        try:
            from src.gui.workers import TrainingWorker  # noqa: PLC0415
        except ImportError:
            self._log("❌ TrainingWorker를 불러올 수 없습니다.")
            self._btn_train.setEnabled(True)
            return

        self._training_worker = TrainingWorker(
            dataset_yaml=str(yaml_path),
            epochs=epochs,
            batch=batch,
            parent=self,
        )
        self._training_worker.progress.connect(self.on_training_progress)
        self._training_worker.finished_ok.connect(self.on_training_done)
        self._training_worker.error_occurred.connect(self.on_training_error)
        self._training_worker.start()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _log(self, text: str) -> None:
        if _QT_AVAILABLE:
            self._txt_log.append(text)

    def _refresh_stats(self) -> None:
        if not _QT_AVAILABLE:
            return
        stats = self._dm.get_stats()
        lines = [
            f"이미지 수: {stats['image_count']}",
            f"어노테이션 수: {stats['annotation_count']}",
            "",
            "클래스별 bbox 수:",
        ]
        for cls, cnt in stats["class_counts"].items():
            if cnt > 0:
                lines.append(f"  {cls}: {cnt}")
        self._txt_stats.setText("\n".join(lines))
