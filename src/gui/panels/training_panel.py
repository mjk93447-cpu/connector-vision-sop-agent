"""
Tab 7 — Training Panel (v3.0 — English UI + Polygon Mask + reload_model hook).

Three sub-sections:
  1. Annotation Canvas  — BBox (rect) + Polygon Mask annotation modes
  2. Dataset Stats      — image/annotation counts per class
  3. Fine-tuning Controls — epochs, batch, base model selector, start training

Key features (v3.0):
  - Polygon mask mode: click to add polygon vertices → right-click to close
  - Reload model button: load new weights into running VisionEngine (no restart)
  - Base model priority: yolo26x_local_pretrained.pt → yolo26x_pretrain.pt → yolo26x.pt
  - All UI text in English for Indian line engineers
  - on_training_done() calls VisionEngine.reload_model() automatically

YOLO Fine-Tuning Strategy:
  Pretraining is complete and archived. Active field work starts from the
  completed local seed yolo26x_local_pretrained.pt, with the older cloud
  checkpoint retained only as a compatibility fallback. Local Tab 7 fine-tuning
  then needs only 30-50 OLED connector photos (vs 200+ from scratch) to reach
  sufficient mAP50 for production use.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
    from PyQt6.QtGui import (
        QColor,
        QCursor,
        QImage,
        QPainter,
        QPen,
        QPixmap,
        QPolygon,
    )
    from PyQt6.QtWidgets import (
        QButtonGroup,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QRadioButton,
        QScrollArea,
        QSizePolicy,
        QSpinBox,
        QSplitter,
        QTableWidget,
        QTableWidgetItem,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False
    QWidget = object  # type: ignore[assignment,misc]
    pyqtSignal = object  # type: ignore[assignment]

from src.class_registry import ClassRegistry
from src.config_loader import suggest_training_profile
from src.model_artifacts import (
    CLOUD_PRETRAIN_MODEL_NAME,
    COCO_BASE_MODEL_NAME,
    LOCAL_PRETRAIN_MODEL_NAME,
    resolve_finetune_seed_model,
    resolve_model_artifact,
)
from src.training.annotation_queue import AnnotationQueue
from src.training.dataset_manager import OLED_CLASSES, DatasetManager

# Extended class list: add legacy aliases + connector_pin if not present
_TRAIN_CLASSES = list(OLED_CLASSES)
for _cls in ["mold_left_label", "mold_right_label", "connector_pin", "pin_cluster"]:
    if _cls not in _TRAIN_CLASSES:
        _TRAIN_CLASSES.append(_cls)

# Base model priority (highest quality first)
def _resolve_base_model_options() -> list[tuple[str, str]]:
    """Build the base-model selector entries with migration-aware paths."""

    return [
        (
            f"Local Pretrained ({LOCAL_PRETRAIN_MODEL_NAME}) — Recommended",
            f"assets/models/{LOCAL_PRETRAIN_MODEL_NAME}",
        ),
        (
            f"Archived Cloud Pretrain ({CLOUD_PRETRAIN_MODEL_NAME}) — Compatibility fallback",
            f"assets/models/{CLOUD_PRETRAIN_MODEL_NAME}",
        ),
        (
            f"COCO Base ({COCO_BASE_MODEL_NAME}) — Lowest baseline",
            f"assets/models/{COCO_BASE_MODEL_NAME}",
        ),
    ]


_BASE_MODEL_OPTIONS = _resolve_base_model_options()


# ---------------------------------------------------------------------------
# BBoxCanvas — supports BBox rect + Polygon mask annotation
# ---------------------------------------------------------------------------


class BBoxCanvas(QWidget):  # type: ignore[misc]
    """Interactive annotation widget.

    Modes:
      bbox    : click-drag to draw bounding box rectangle
      polygon : click to add vertices, right-click or double-click to close polygon
    """

    annotation_added: Any = pyqtSignal(dict) if _QT_AVAILABLE else object()  # type: ignore[assignment]

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._image: Optional[Any] = None  # QPixmap
        self._annotations: List[Dict[str, Any]] = []
        self._current_label: str = _TRAIN_CLASSES[0]
        self._mode: str = "bbox"  # "bbox" | "polygon"

        # BBox state
        self._drawing = False
        self._start: Optional[Any] = None
        self._current_rect: Optional[Any] = None

        # Polygon state
        self._poly_points: List[Any] = []  # list of QPoint (widget coords)
        self._poly_cursor: Optional[Any] = None  # current mouse pos for preview

        if _QT_AVAILABLE:
            self.setMouseTracking(True)
            self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
            self.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_image(self, pixmap: Any) -> None:
        self._image = pixmap
        self._annotations = []
        self._reset_drawing_state()
        self.update()

    def set_label(self, label: str) -> None:
        self._current_label = label

    def set_mode(self, mode: str) -> None:
        """Set annotation mode: 'bbox' or 'polygon'."""
        self._mode = mode
        self._reset_drawing_state()
        self.update()

    def get_annotations(self) -> List[Dict[str, Any]]:
        return list(self._annotations)

    def clear_annotations(self) -> None:
        self._annotations = []
        self._reset_drawing_state()
        self.update()

    def undo_last(self) -> None:
        if self._poly_points and self._mode == "polygon":
            # Undo last polygon vertex
            self._poly_points.pop()
            self.update()
        elif self._annotations:
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

        scaled, ox, oy = self._image_display_params()
        if scaled is not None:
            painter.drawPixmap(ox, oy, scaled)

            # Saved annotations
            for ann in self._annotations:
                if ann.get("type") == "polygon":
                    self._draw_polygon_ann(painter, ann, scaled, ox, oy)
                else:
                    self._draw_bbox_ann(painter, ann, scaled, ox, oy)

        # In-progress BBox rect
        if self._mode == "bbox" and self._drawing and self._current_rect:
            pen = QPen(QColor("#ff9800"), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(self._current_rect)

        # In-progress polygon vertices + preview line
        if self._mode == "polygon" and self._poly_points:
            pen = QPen(QColor("#e91e63"), 2)
            painter.setPen(pen)
            for i in range(len(self._poly_points) - 1):
                painter.drawLine(self._poly_points[i], self._poly_points[i + 1])
            # Preview line to cursor
            if self._poly_cursor:
                pen2 = QPen(QColor("#e91e63"), 1, Qt.PenStyle.DashLine)
                painter.setPen(pen2)
                painter.drawLine(self._poly_points[-1], self._poly_cursor)
            # Draw dots at vertices
            painter.setBrush(QColor("#e91e63"))
            for pt in self._poly_points:
                painter.drawEllipse(pt, 4, 4)

        painter.end()

    def _draw_bbox_ann(
        self, painter: Any, ann: Dict[str, Any], scaled: Any, ox: int, oy: int
    ) -> None:
        pen = QPen(QColor("#4caf50"), 2)
        painter.setPen(pen)
        r = self._ann_to_widget_rect(ann, scaled, ox, oy)
        painter.drawRect(r)
        painter.drawText(r.topLeft() + QPoint(2, -4), ann.get("label", ""))

    def _draw_polygon_ann(
        self, painter: Any, ann: Dict[str, Any], scaled: Any, ox: int, oy: int
    ) -> None:
        if self._image is None or scaled is None:
            return
        iw, ih = self._image.width(), self._image.height()
        sw, sh = scaled.width(), scaled.height()
        pts = ann.get("polygon", [])
        if len(pts) < 3:
            return
        widget_pts = [
            QPoint(int(p[0] * sw / iw) + ox, int(p[1] * sh / ih) + oy) for p in pts
        ]
        pen = QPen(QColor("#9c27b0"), 2)
        painter.setPen(pen)
        painter.setBrush(QColor(156, 39, 176, 40))  # semi-transparent purple
        poly = QPolygon(widget_pts)
        painter.drawPolygon(poly)
        if widget_pts:
            painter.drawText(widget_pts[0] + QPoint(2, -4), ann.get("label", ""))

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        if not _QT_AVAILABLE or self._image is None:
            return

        if self._mode == "bbox":
            if event.button() == Qt.MouseButton.LeftButton:
                self._drawing = True
                self._start = event.pos()
                self._current_rect = QRect(self._start, self._start)
                self.update()

        elif self._mode == "polygon":
            if event.button() == Qt.MouseButton.LeftButton:
                self._poly_points.append(event.pos())
                self.update()
            elif event.button() == Qt.MouseButton.RightButton:
                self._close_polygon()

    def mouseDoubleClickEvent(self, event: Any) -> None:  # noqa: N802
        if self._mode == "polygon" and len(self._poly_points) >= 3:
            self._close_polygon()

    def mouseMoveEvent(self, event: Any) -> None:  # noqa: N802
        if not _QT_AVAILABLE:
            return
        if self._mode == "bbox" and self._drawing and self._start:
            self._current_rect = QRect(self._start, event.pos()).normalized()
        elif self._mode == "polygon":
            self._poly_cursor = event.pos()
        self.update()

    def mouseReleaseEvent(self, event: Any) -> None:  # noqa: N802
        if not _QT_AVAILABLE or self._mode != "bbox" or not self._drawing:
            return
        self._drawing = False
        end = event.pos()
        rect = QRect(self._start, end).normalized()

        if rect.width() < 5 or rect.height() < 5:
            self._current_rect = None
            self.update()
            return

        ann = self._widget_rect_to_ann(rect)
        if ann:
            ann["type"] = "bbox"
            self._annotations.append(ann)
            try:
                self.annotation_added.emit(ann)
            except Exception:  # noqa: BLE001
                pass
        self._current_rect = None
        self.update()

    # ------------------------------------------------------------------
    # Polygon helper
    # ------------------------------------------------------------------

    def _close_polygon(self) -> None:
        """Close current polygon annotation."""
        if len(self._poly_points) < 3:
            self._reset_drawing_state()
            self.update()
            return

        scaled, ox, oy = self._image_display_params()
        if scaled is None or self._image is None:
            self._reset_drawing_state()
            return

        iw, ih = self._image.width(), self._image.height()
        sw, sh = scaled.width(), scaled.height()
        if sw == 0 or sh == 0:
            return

        image_pts = [
            (
                int(max(0, (pt.x() - ox) * iw / sw)),
                int(max(0, (pt.y() - oy) * ih / sh)),
            )
            for pt in self._poly_points
        ]

        ann = {
            "label": self._current_label,
            "type": "polygon",
            "polygon": image_pts,
            # Also compute bounding bbox for YOLO training compatibility
            "bbox": self._polygon_to_bbox(image_pts),
        }
        self._annotations.append(ann)
        try:
            self.annotation_added.emit(ann)
        except Exception:  # noqa: BLE001
            pass

        self._poly_points = []
        self._poly_cursor = None
        self.update()

    @staticmethod
    def _polygon_to_bbox(
        pts: List[Tuple[int, int]],
    ) -> List[int]:
        if not pts:
            return [0, 0, 0, 0]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return [min(xs), min(ys), max(xs), max(ys)]

    def _reset_drawing_state(self) -> None:
        self._drawing = False
        self._start = None
        self._current_rect = None
        self._poly_points = []
        self._poly_cursor = None

    # ------------------------------------------------------------------
    # Coordinate helpers (shared)
    # ------------------------------------------------------------------

    def _image_display_params(self) -> Tuple[Any, int, int]:
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

    training_finished: Any = pyqtSignal(str) if _QT_AVAILABLE else object()  # type: ignore[assignment]
    registry_changed: Any = pyqtSignal() if _QT_AVAILABLE else object()  # type: ignore[assignment]

    def __init__(
        self,
        dataset_manager: Optional[Any] = None,
        vision_engine: Optional[Any] = None,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._dm = dataset_manager or DatasetManager()
        self._vision_engine = vision_engine  # for hot-reload after training
        self._current_image_name: Optional[str] = None
        self._current_bgr: Optional[Any] = None
        self._training_worker: Optional[Any] = None
        self._last_training_metrics_epoch: Optional[int] = None
        self._last_training_metrics_line: str = ""
        self._image_queue = AnnotationQueue()
        self._current_image_path: Optional[Path] = None
        self._last_saved_label: str = _TRAIN_CLASSES[0] if _TRAIN_CLASSES else ""
        self._auto_advance: bool = True
        # Class selection checkboxes: {class_name: QCheckBox}
        self._class_checkboxes: Dict[str, Any] = {}
        # Class registry (loaded once; mutated via panel UI)
        try:
            self._registry: ClassRegistry = ClassRegistry.load()
        except Exception:  # noqa: BLE001
            self._registry = ClassRegistry([], Path("assets/class_registry.json"))

        if _QT_AVAILABLE:
            self._setup_ui()

    def set_vision_engine(self, engine: Any) -> None:
        """Inject VisionEngine reference for post-training model reload."""
        self._vision_engine = engine

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_image_for_annotation(self, bgr_arr: Any, name: str = "capture.png") -> None:
        if not _QT_AVAILABLE:
            return
        self._current_image_name = name
        self._current_image_path = None
        self._current_bgr = bgr_arr
        rgb = bgr_arr[:, :, ::-1].copy()
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self._canvas.set_image(QPixmap.fromImage(qimg))
        self._lbl_image_name.setText(f"Image: {name}")
        if hasattr(self, "_combo_label") and self._last_saved_label:
            idx = self._combo_label.findText(self._last_saved_label)
            if idx >= 0:
                self._combo_label.setCurrentIndex(idx)

    def on_training_progress(self, epoch: int, total: int) -> None:
        if not _QT_AVAILABLE:
            return
        self._progress.setMaximum(total)
        self._progress.setValue(epoch)
        pct = int(epoch / total * 100) if total > 0 else 0
        self._lbl_epoch_progress.setText(f"Epoch {epoch}/{total} ({pct}%)")
        self._progress_detail.setText(f"Progress: {epoch}/{total} epochs")
        self._log(f"  Epoch {epoch}/{total} — {pct}%")

    def on_training_metrics(self, metrics: Dict[str, Any]) -> None:
        """Update live validation metrics after each epoch."""
        if not _QT_AVAILABLE:
            return

        epoch = metrics.get("epoch")
        total = metrics.get("total_epochs")
        map50 = metrics.get("map50")
        map50_95 = metrics.get("map50_95")
        fitness = metrics.get("fitness")
        loss = metrics.get("loss")

        def _fmt(value: Any) -> str:
            try:
                if value is None:
                    return "--"
                return f"{float(value):.4f}"
            except Exception:  # noqa: BLE001
                return "--"

        self._lbl_map50.setText(f"mAP50: {_fmt(map50)}")
        self._lbl_map50_95.setText(f"mAP50-95: {_fmt(map50_95)}")
        self._lbl_fitness.setText(f"Fitness: {_fmt(fitness)}")
        self._lbl_loss.setText(f"Loss: {_fmt(loss)}")

        if epoch is not None and total is not None:
            line = (
                f"Epoch {int(epoch)}/{int(total)} | "
                f"mAP50={_fmt(map50)} | mAP50-95={_fmt(map50_95)} | "
                f"fitness={_fmt(fitness)} | loss={_fmt(loss)}"
            )
            if line != self._last_training_metrics_line:
                self._last_training_metrics_line = line
                self._lbl_metric_status.setText(line)
                self._log(f"  {line}")

    def on_training_done(self, weights_path: str) -> None:
        if not _QT_AVAILABLE:
            return
        self._log(f"✅ Training complete! Weights saved: {weights_path}")
        self._progress.setValue(self._progress.maximum())
        self._btn_train.setEnabled(True)
        self._btn_reload.setEnabled(True)

        # Auto-reload the new model into VisionEngine (no restart needed)
        if self._vision_engine is not None:
            try:
                ok = self._vision_engine.reload_model()
                if ok:
                    self._log("✅ New model loaded — no restart required")
                else:
                    self._log("⚠ Model reload failed — restart manually if needed")
            except Exception as exc:
                self._log(f"⚠ Model reload error: {exc}")

        try:
            self.training_finished.emit(weights_path)
        except Exception:  # noqa: BLE001
            pass

    def on_training_log_ready(self, log_path: str) -> None:
        """Called when training.log is ready; show last lines in the log panel."""
        if not _QT_AVAILABLE:
            return
        self._training_log_path = log_path
        self._log(f"📋 YOLO training log: {log_path}")
        try:
            lines = (
                Path(log_path)
                .read_text(encoding="utf-8", errors="replace")
                .splitlines()
            )
            tail = lines[-30:] if len(lines) > 30 else lines
            self._log("─── YOLO26x training output (last 30 lines) ───")
            for line in tail:
                self._log(line)
            self._log("─────────────────────────────────────────────")
        except Exception as exc:  # noqa: BLE001
            self._log(f"⚠ Could not read training log: {exc}")

    def on_training_error(self, err: str) -> None:
        if not _QT_AVAILABLE:
            return
        self._log(f"❌ Training error: {err}")
        self._btn_train.setEnabled(True)
        self._btn_reload.setEnabled(True)

    # ------------------------------------------------------------------
    # Private — UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # ---- Class Registry collapsible panel (always at top) --------
        outer.addWidget(self._setup_registry_panel())

        header = QLabel("🧠 YOLO26x Local Fine-Tuning (Tab 7)")
        header.setStyleSheet("font-size: 14px; font-weight: bold;")
        outer.addWidget(header)

        # Training minimization note
        note = QLabel(
            "Tip: Use the completed local pretrained seed "
            "(yolo26x_local_pretrained.pt) as base — "
            "requires only 30-50 annotated photos for OLED connector fine-tuning."
        )
        note.setStyleSheet("color: #1565c0; font-size: 11px;")
        note.setWordWrap(True)
        note.setText(
            "Tip: Use the completed local pretrained seed "
            "(yolo26x_local_pretrained.pt) as base — "
            "requires only 30-50 annotated photos for OLED connector fine-tuning."
        )
        outer.addWidget(note)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ---- Left: annotation canvas ---------------------------------
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 4, 0)

        # Image controls row
        img_row = QHBoxLayout()
        self._lbl_image_name = QLabel("No image loaded")
        self._lbl_queue_pos = QLabel("Queue: 0/0")
        btn_load = QPushButton("📁 Open Image")
        btn_load.setToolTip("Load an image file for annotation")
        btn_load.clicked.connect(self._on_load_image)
        btn_load_many = QPushButton("Batch Files")
        btn_load_many.setToolTip("Load many image files at once")
        btn_load_many.clicked.connect(self._on_load_image_files)
        btn_load_folder = QPushButton("Batch Folder")
        btn_load_folder.setToolTip("Load all images from a folder recursively")
        btn_load_folder.clicked.connect(self._on_load_image_folder)
        btn_prev = QPushButton("Prev")
        btn_prev.setToolTip("Go to previous image in the queue")
        btn_prev.clicked.connect(self._on_prev_image)
        btn_next = QPushButton("Next")
        btn_next.setToolTip("Go to next image in the queue")
        btn_next.clicked.connect(self._on_next_image)
        self._chk_auto_advance = QCheckBox("Auto Next")
        self._chk_auto_advance.setChecked(True)
        self._chk_auto_advance.setToolTip(
            "After saving an annotation, automatically move to the next queued image."
        )
        btn_capture = QPushButton("📷 Capture Screen")
        btn_capture.setToolTip("Capture current screen for annotation")
        btn_capture.clicked.connect(self._on_capture_screen)
        img_row.addWidget(self._lbl_image_name)
        img_row.addWidget(self._lbl_queue_pos)
        img_row.addStretch()
        img_row.addWidget(btn_load)
        img_row.addWidget(btn_load_many)
        img_row.addWidget(btn_load_folder)
        img_row.addWidget(btn_prev)
        img_row.addWidget(btn_next)
        img_row.addWidget(self._chk_auto_advance)
        img_row.addWidget(btn_capture)
        lv.addLayout(img_row)

        # Annotation mode selector
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))
        self._mode_group = QButtonGroup()
        self._radio_bbox = QRadioButton("BBox (Rect)")
        self._radio_bbox.setChecked(True)
        self._radio_polygon = QRadioButton("Polygon Mask")
        self._radio_polygon.setToolTip(
            "Click to add polygon vertices.\n"
            "Right-click or double-click to close the polygon.\n"
            "Use for irregular mold/connector shapes."
        )
        self._mode_group.addButton(self._radio_bbox)
        self._mode_group.addButton(self._radio_polygon)
        self._radio_bbox.toggled.connect(self._on_mode_changed)
        mode_row.addWidget(self._radio_bbox)
        mode_row.addWidget(self._radio_polygon)
        mode_row.addStretch()
        lv.addLayout(mode_row)

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
        ctrl_row.addWidget(QLabel("Class:"))
        self._combo_label = QComboBox()
        self._combo_label.addItems(_TRAIN_CLASSES)
        self._combo_label.currentTextChanged.connect(self._canvas.set_label)
        ctrl_row.addWidget(self._combo_label)

        btn_undo = QPushButton("↩ Undo")
        btn_undo.setToolTip("Undo last bbox or polygon vertex")
        btn_undo.clicked.connect(self._canvas.undo_last)

        btn_save_ann = QPushButton("💾 Save Annotation")
        btn_save_ann.setToolTip("Save current image and annotations to dataset")
        btn_save_ann.clicked.connect(self._on_save_annotation)

        btn_clear = QPushButton("🗑 Clear All")
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

        # Dataset stats
        stats_grp = QGroupBox("📊 Dataset Status")
        sv = QVBoxLayout(stats_grp)
        self._txt_stats = QTextEdit()
        self._txt_stats.setReadOnly(True)
        self._txt_stats.setMaximumHeight(180)
        sv.addWidget(self._txt_stats)
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self._refresh_stats)
        sv.addWidget(btn_refresh)
        rv.addWidget(stats_grp)

        # ---- Class selection -----------------------------------------
        class_grp = QGroupBox("📚 Training Classes")
        class_grp.setToolTip(
            "Select which class folders to include in training.\n"
            "Only classes that have saved annotated images are enabled.\n"
            "Refresh Stats to update counts after adding new annotations."
        )
        class_cv = QVBoxLayout(class_grp)
        class_cv.setSpacing(4)

        # Select All / Deselect All buttons
        sel_btn_row = QHBoxLayout()
        btn_sel_all = QPushButton("✅ Select All")
        btn_sel_all.setToolTip("Check all classes that have annotated images")
        btn_sel_all.clicked.connect(self._on_select_all_classes)
        btn_desel_all = QPushButton("☐ Deselect All")
        btn_desel_all.setToolTip("Uncheck all class checkboxes")
        btn_desel_all.clicked.connect(self._on_deselect_all_classes)
        sel_btn_row.addWidget(btn_sel_all)
        sel_btn_row.addWidget(btn_desel_all)
        sel_btn_row.addStretch()
        class_cv.addLayout(sel_btn_row)

        # Checkbox grid — 2 columns
        grid_widget = QWidget()
        self._class_grid = QGridLayout(grid_widget)
        self._class_grid.setContentsMargins(0, 0, 0, 0)
        self._class_grid.setHorizontalSpacing(8)
        self._class_grid.setVerticalSpacing(2)
        for i, cls in enumerate(_TRAIN_CLASSES):
            cb = QCheckBox(f"{cls}  (0 imgs)")
            cb.setEnabled(False)
            cb.setChecked(False)
            self._class_checkboxes[cls] = cb
            self._class_grid.addWidget(cb, i // 2, i % 2)
        class_cv.addWidget(grid_widget)

        # Note about all-images fallback
        note_lbl = QLabel(
            "ℹ If no class is selected, all images in training_data/images/ are used."
        )
        note_lbl.setStyleSheet("color: #546e7a; font-size: 10px;")
        note_lbl.setWordWrap(True)
        class_cv.addWidget(note_lbl)

        rv.addWidget(class_grp)

        # Training config
        train_grp = QGroupBox("⚙ Training Settings")
        tv = QVBoxLayout(train_grp)

        # Base model selector
        tv.addWidget(QLabel("Base Model:"))
        self._combo_base = QComboBox()
        for label, path in _BASE_MODEL_OPTIONS:
            available = resolve_model_artifact(path).exists()
            display = f"{'✓' if available else '✗'} {label}"
            self._combo_base.addItem(display, userData=path)
        self._combo_base.setToolTip(
            "Local pretrained (yolo26x_local_pretrained.pt) is the preferred seed.\n"
            "Archived cloud pretrain (yolo26x_pretrain.pt) is compatibility-only.\n"
            "COCO base (yolo26x.pt) is the last-resort fallback."
        )
        tv.addWidget(self._combo_base)

        stats = self._dm.get_stats()
        profile = suggest_training_profile(image_count=stats.get("image_count", 0))
        row_epochs = QHBoxLayout()
        row_epochs.addWidget(QLabel("Epochs:"))
        self._spin_epochs = QSpinBox()
        self._spin_epochs.setRange(1, 200)
        self._spin_epochs.setValue(int(profile["epochs"]))
        self._spin_epochs.setToolTip(
            "GPU workstation: use the higher preset automatically.\n"
            "CPU fallback: lower preset keeps the run responsive."
        )
        row_epochs.addWidget(self._spin_epochs)
        tv.addLayout(row_epochs)

        row_batch = QHBoxLayout()
        row_batch.addWidget(QLabel("Batch:"))
        self._spin_batch = QSpinBox()
        self._spin_batch.setRange(1, 32)
        self._spin_batch.setValue(int(profile["batch"]))
        row_batch.addWidget(self._spin_batch)
        tv.addLayout(row_batch)

        rv.addWidget(train_grp)

        # Train + Reload buttons
        btn_row = QHBoxLayout()
        self._btn_train = QPushButton("🚀 Start Training & Save")
        self._btn_train.setStyleSheet(
            "QPushButton { background: #1565c0; color: white; "
            "font-weight: bold; padding: 8px; border-radius: 4px; } "
            "QPushButton:disabled { background: #90a4ae; }"
        )
        self._btn_train.clicked.connect(self._on_start_training)
        btn_row.addWidget(self._btn_train)

        self._btn_reload = QPushButton("🔄 Reload Model")
        self._btn_reload.setStyleSheet(
            "QPushButton { background: #2e7d32; color: white; "
            "font-weight: bold; padding: 8px; border-radius: 4px; } "
            "QPushButton:disabled { background: #90a4ae; }"
        )
        self._btn_reload.setToolTip(
            "Reload YOLO26x weights into running engine (no restart)"
        )
        self._btn_reload.setEnabled(False)
        self._btn_reload.clicked.connect(self._on_reload_model)
        btn_row.addWidget(self._btn_reload)
        rv.addLayout(btn_row)

        self._progress = QProgressBar()
        self._progress.setValue(0)
        rv.addWidget(self._progress)

        metrics_grp = QGroupBox("Live Metrics")
        mg = QGridLayout(metrics_grp)
        self._lbl_epoch_progress = QLabel("Epoch --/--")
        self._progress_detail = QLabel("Progress: 0/0 epochs")
        self._lbl_map50 = QLabel("mAP50: --")
        self._lbl_map50_95 = QLabel("mAP50-95: --")
        self._lbl_fitness = QLabel("Fitness: --")
        self._lbl_loss = QLabel("Loss: --")
        self._lbl_metric_status = QLabel("Waiting for first validation pass...")
        self._lbl_metric_status.setWordWrap(True)
        mg.addWidget(self._lbl_epoch_progress, 0, 0)
        mg.addWidget(self._progress_detail, 0, 1)
        mg.addWidget(self._lbl_map50, 1, 0)
        mg.addWidget(self._lbl_map50_95, 1, 1)
        mg.addWidget(self._lbl_fitness, 2, 0)
        mg.addWidget(self._lbl_loss, 2, 1)
        mg.addWidget(self._lbl_metric_status, 3, 0, 1, 2)
        rv.addWidget(metrics_grp)

        rv.addWidget(QLabel("Training Log:"))
        self._txt_log = QTextEdit()
        self._txt_log.setReadOnly(True)
        rv.addWidget(self._txt_log)

        splitter.addWidget(right)
        splitter.setSizes([550, 380])
        outer.addWidget(splitter)

        self._refresh_stats()

    # ------------------------------------------------------------------
    # Class Registry panel builder
    # ------------------------------------------------------------------

    def _setup_registry_panel(self) -> Any:
        """Build the collapsible Class Registry panel widget and return it."""
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(2)

        # Toggle button
        self._btn_registry_toggle = QPushButton("📋 Class Registry ▶")
        self._btn_registry_toggle.setCheckable(True)
        self._btn_registry_toggle.setChecked(False)
        self._btn_registry_toggle.setStyleSheet(
            "QPushButton { text-align: left; font-weight: bold; padding: 4px 8px; "
            "background: #e3f2fd; border: 1px solid #90caf9; border-radius: 4px; } "
            "QPushButton:checked { background: #bbdefb; }"
        )
        self._btn_registry_toggle.clicked.connect(self._on_registry_toggle)
        vbox.addWidget(self._btn_registry_toggle)

        # Content widget (hidden by default)
        self._registry_content = QWidget()
        cv = QVBoxLayout(self._registry_content)
        cv.setContentsMargins(4, 4, 4, 4)
        cv.setSpacing(4)

        # Table: Class Name | Type | Actions
        self._tbl_registry = QTableWidget(0, 3)
        self._tbl_registry.setHorizontalHeaderLabels(["Class Name", "Type", "Actions"])
        self._tbl_registry.horizontalHeader().setStretchLastSection(True)
        self._tbl_registry.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers  # type: ignore[attr-defined]
        )
        self._tbl_registry.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection  # type: ignore[attr-defined]
        )
        self._tbl_registry.setMaximumHeight(200)
        cv.addWidget(self._tbl_registry)

        # Add row: [line edit] [combo type] [+ Add Class] [💾 Save]
        add_row = QHBoxLayout()
        self._edit_new_class = QLineEdit()
        self._edit_new_class.setPlaceholderText("Class Name")
        self._edit_new_class.setMaximumWidth(200)
        add_row.addWidget(self._edit_new_class)
        self._combo_new_type = QComboBox()
        self._combo_new_type.addItems(["TEXT", "NON_TEXT"])
        self._combo_new_type.setMaximumWidth(110)
        add_row.addWidget(self._combo_new_type)
        btn_add_cls = QPushButton("+ Add Class")
        btn_add_cls.setToolTip("Add a new class to the registry")
        btn_add_cls.clicked.connect(self._on_registry_add)
        add_row.addWidget(btn_add_cls)
        add_row.addStretch()
        btn_save_reg = QPushButton("💾 Save Registry")
        btn_save_reg.setToolTip("Save registry to assets/class_registry.json")
        btn_save_reg.clicked.connect(self._on_registry_save)
        add_row.addWidget(btn_save_reg)
        cv.addLayout(add_row)

        self._registry_content.setVisible(False)
        vbox.addWidget(self._registry_content)

        # Populate table from loaded registry
        self._refresh_registry_table()

        return container

    def _refresh_registry_table(self) -> None:
        """Repopulate the registry table from self._registry."""
        if not _QT_AVAILABLE:
            return
        tbl = self._tbl_registry
        tbl.setRowCount(0)
        for entry in self._registry.all_classes():
            row = tbl.rowCount()
            tbl.insertRow(row)
            tbl.setItem(row, 0, QTableWidgetItem(entry.name))
            type_icon = "👁 NON_TEXT" if entry.type == "NON_TEXT" else "🔤 TEXT"
            tbl.setItem(row, 1, QTableWidgetItem(type_icon))

            # Actions cell: toggle type + delete
            actions_widget = QWidget()
            ah = QHBoxLayout(actions_widget)
            ah.setContentsMargins(2, 0, 2, 0)
            ah.setSpacing(4)

            if entry.type == "NON_TEXT":
                btn_toggle = QPushButton("🔤 →TEXT")
                btn_toggle.setToolTip("Switch type to TEXT")
            else:
                btn_toggle = QPushButton("👁 →NON_TEXT")
                btn_toggle.setToolTip("Switch type to NON_TEXT")
            btn_toggle.setMaximumWidth(110)
            # Capture name at definition time via default arg
            btn_toggle.clicked.connect(
                lambda _checked, n=entry.name: self._on_registry_toggle_type(n)
            )
            ah.addWidget(btn_toggle)

            btn_del = QPushButton("🗑 Del")
            btn_del.setToolTip(f"Remove class '{entry.name}' from registry")
            btn_del.setMaximumWidth(70)
            btn_del.clicked.connect(
                lambda _checked, n=entry.name: self._on_registry_delete(n)
            )
            ah.addWidget(btn_del)
            ah.addStretch()
            tbl.setCellWidget(row, 2, actions_widget)

        tbl.resizeColumnToContents(0)
        tbl.resizeColumnToContents(1)

    # ------------------------------------------------------------------
    # Registry slots
    # ------------------------------------------------------------------

    def _on_registry_toggle(self) -> None:
        """Expand or collapse the registry content area."""
        expanded = self._btn_registry_toggle.isChecked()
        self._registry_content.setVisible(expanded)
        self._btn_registry_toggle.setText(
            "📋 Class Registry ▼" if expanded else "📋 Class Registry ▶"
        )

    def _on_registry_add(self) -> None:
        """Add a new class from the input line edit."""
        if not _QT_AVAILABLE:
            return
        name = self._edit_new_class.text().strip()
        if not name:
            QMessageBox.warning(self, "Invalid Name", "Class name cannot be empty.")
            return
        type_ = self._combo_new_type.currentText()
        try:
            self._registry.add_class(name, type_)
        except ValueError as exc:
            QMessageBox.warning(self, "Add Failed", str(exc))
            return
        self._edit_new_class.clear()
        self._refresh_registry_table()

    def _on_registry_toggle_type(self, name: str) -> None:
        """Toggle a class between TEXT and NON_TEXT."""
        if not _QT_AVAILABLE:
            return
        current = self._registry.get_type(name)
        new_type = "NON_TEXT" if current == "TEXT" else "TEXT"
        try:
            self._registry.set_type(name, new_type)
        except KeyError as exc:
            QMessageBox.warning(self, "Toggle Failed", str(exc))
            return
        self._refresh_registry_table()

    def _on_registry_delete(self, name: str) -> None:
        """Remove a class from the registry."""
        if not _QT_AVAILABLE:
            return
        try:
            self._registry.remove_class(name)
        except KeyError as exc:
            QMessageBox.warning(self, "Delete Failed", str(exc))
            return
        self._refresh_registry_table()

    def _on_registry_save(self) -> None:
        """Save registry and update annotation class combo."""
        if not _QT_AVAILABLE:
            return
        try:
            self._registry.save()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Save Failed", str(exc))
            return

        # Refresh annotation class combo with registry class names
        reg_names = self._registry.class_names()
        if reg_names and hasattr(self, "_combo_label"):
            current = self._combo_label.currentText()
            self._combo_label.blockSignals(True)
            self._combo_label.clear()
            self._combo_label.addItems(reg_names)
            # Restore previous selection if still present
            idx = self._combo_label.findText(current)
            if idx >= 0:
                self._combo_label.setCurrentIndex(idx)
            self._combo_label.blockSignals(False)

        try:
            self.registry_changed.emit()
        except Exception:  # noqa: BLE001
            pass

        self._log(f"✅ Class Registry saved ({len(reg_names)} classes)")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_mode_changed(self) -> None:
        mode = "bbox" if self._radio_bbox.isChecked() else "polygon"
        self._canvas.set_mode(mode)

    def _on_load_image(self) -> None:
        if not _QT_AVAILABLE:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Image File",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff *.webp)",
        )
        if not path:
            return
        self._image_queue.clear()
        self._refresh_queue_label()
        self._load_image_path(Path(path))

    def _on_load_image_files(self) -> None:
        if not _QT_AVAILABLE:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Load Image Files",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff *.webp)",
        )
        if not paths:
            return
        self._load_queue_from_paths([Path(p) for p in paths])

    def _on_load_image_folder(self) -> None:
        if not _QT_AVAILABLE:
            return
        folder = QFileDialog.getExistingDirectory(self, "Load Image Folder", "")
        if not folder:
            return
        root = Path(folder)
        paths = [
            p
            for p in sorted(root.rglob("*"))
            if p.is_file()
            and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}
        ]
        self._load_queue_from_paths(paths)

    def _load_queue_from_paths(self, paths: List[Path]) -> None:
        if not _QT_AVAILABLE:
            return
        count = self._image_queue.load(paths)
        self._refresh_queue_label()
        if count == 0:
            QMessageBox.warning(
                self, "Load Failed", "No supported image files were found."
            )
            return
        self._load_image_path(self._image_queue.current())
        self._log(f"Loaded {count} images into the annotation queue")

    def _load_image_path(self, path: Optional[Path]) -> None:
        if not _QT_AVAILABLE or path is None:
            return
        try:
            import cv2  # noqa: PLC0415

            bgr = cv2.imread(str(path))
            if bgr is None:
                raise ValueError("cv2.imread returned None")
            self.set_image_for_annotation(bgr, path.name)
            self._current_image_path = path
            self._refresh_queue_label()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Load Failed", str(exc))

    def _on_prev_image(self) -> None:
        if not _QT_AVAILABLE:
            return
        self._load_image_path(self._image_queue.prev())

    def _on_next_image(self) -> None:
        if not _QT_AVAILABLE:
            return
        self._load_image_path(self._image_queue.next())

    def _refresh_queue_label(self) -> None:
        if not _QT_AVAILABLE:
            return
        cur, total = self._image_queue.position()
        self._lbl_queue_pos.setText(f"Queue: {cur}/{total}")

    def _on_capture_screen(self) -> None:
        if not _QT_AVAILABLE:
            return
        try:
            import numpy as np  # noqa: PLC0415
            import pyautogui  # noqa: PLC0415

            screenshot = pyautogui.screenshot()
            rgb = np.array(screenshot)
            bgr = rgb[:, :, ::-1].copy()
            # Use current class + timestamp so the capture filename is meaningful
            cls = self._combo_label.currentText() if _QT_AVAILABLE else "capture"
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.set_image_for_annotation(bgr, f"{cls}_{ts}_capture.png")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Capture Failed", str(exc))

    def _on_annotation_added(self, ann: Dict[str, Any]) -> None:
        label = ann.get("label", "?")
        ann_type = ann.get("type", "bbox")
        if ann_type == "polygon":
            pts = ann.get("polygon", [])
            self._log(f"  + polygon: {label} ({len(pts)} vertices)")
        else:
            bbox = ann.get("bbox", [])
            self._log(f"  + bbox: {label} {bbox}")

    def _on_save_annotation(self) -> None:
        if not _QT_AVAILABLE:
            return
        if self._current_bgr is None:
            QMessageBox.warning(self, "Save Failed", "Please load an image first.")
            return
        annotations = self._canvas.get_annotations()
        if not annotations:
            QMessageBox.warning(
                self,
                "Save Failed",
                "No annotations found. Please draw bounding boxes or polygons first.",
            )
            return

        # Determine primary class: most frequent label in current annotations
        label_counts = Counter(ann.get("label", "") for ann in annotations)
        primary_class = label_counts.most_common(1)[0][0] if label_counts else "unknown"

        # Generate systematic filename: {class}_{YYYYMMDD}_{HHMMSS}[_{n}].png
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_stem = f"{primary_class}_{ts}"
        save_name = f"{base_stem}.png"

        # Avoid overwriting an existing file in the same second (rare)
        subfolder_dir = self._dm.images_dir / primary_class
        counter = 1
        while (subfolder_dir / save_name).exists():
            save_name = f"{base_stem}_{counter:03d}.png"
            counter += 1

        img_path = self._dm.add_image_with_annotations(
            save_name, self._current_bgr, annotations, subfolder=primary_class
        )
        self._dm.save_dataset_yaml()
        self._last_saved_label = primary_class
        self._log(
            f"✅ Saved: {img_path.relative_to(self._dm.data_root)}"
            f" ({len(annotations)} annotations)"
        )
        self._refresh_stats()
        self._canvas.clear_annotations()

        if self._auto_advance and self._image_queue.has_items():
            next_path = self._image_queue.next()
            if next_path is not None:
                self._load_image_path(next_path)

    def _on_start_training(self) -> None:
        if not _QT_AVAILABLE:
            return
        stats = self._dm.get_stats()
        if stats["image_count"] == 0:
            QMessageBox.warning(
                self,
                "Cannot Train",
                "No annotated images found.\n"
                "Please add images and draw annotations, then save them before training.",
            )
            return

        # Collect selected training classes (checked + enabled checkboxes)
        selected_classes = [
            cls
            for cls, cb in self._class_checkboxes.items()
            if cb.isChecked() and cb.isEnabled()
        ]

        yaml_path = self._dm.save_dataset_yaml(
            selected_classes=selected_classes if selected_classes else None
        )
        epochs = self._spin_epochs.value()
        batch = self._spin_batch.value()

        # Get selected base model
        base_model = resolve_model_artifact(
            self._combo_base.currentData() or f"assets/models/{COCO_BASE_MODEL_NAME}"
        )

        if selected_classes:
            self._log(f"▶ Starting training: {epochs} epochs, batch={batch}")
            self._log(f"  Classes: {', '.join(selected_classes)}")
        else:
            self._log(f"▶ Starting training: {epochs} epochs, batch={batch}")
            self._log("  Classes: all images (no class filter)")
        self._log(f"  Dataset: {yaml_path}")
        self._log(f"  Base model: {base_model}")
        self._progress.setValue(0)
        self._progress.setMaximum(epochs)
        self._lbl_epoch_progress.setText("Epoch --/--")
        self._progress_detail.setText("Progress: 0/0 epochs")
        self._lbl_map50.setText("mAP50: --")
        self._lbl_map50_95.setText("mAP50-95: --")
        self._lbl_fitness.setText("Fitness: --")
        self._lbl_loss.setText("Loss: --")
        self._lbl_metric_status.setText("Waiting for first validation pass...")
        self._last_training_metrics_line = ""
        self._btn_train.setEnabled(False)
        self._btn_reload.setEnabled(False)

        try:
            from src.gui.workers import TrainingWorker  # noqa: PLC0415
        except ImportError:
            self._log("❌ TrainingWorker not available.")
            self._btn_train.setEnabled(True)
            return

        self._training_worker = TrainingWorker(
            dataset_yaml=str(yaml_path),
            epochs=epochs,
            batch=batch,
            base_model=base_model,
            parent=self,
        )
        self._training_worker.progress.connect(self.on_training_progress)
        self._training_worker.metrics_ready.connect(self.on_training_metrics)
        self._training_worker.finished_ok.connect(self.on_training_done)
        self._training_worker.log_ready.connect(self.on_training_log_ready)
        self._training_worker.error_occurred.connect(self.on_training_error)
        self._training_worker.start()

    def _on_reload_model(self) -> None:
        if self._vision_engine is None:
            QMessageBox.warning(self, "Reload Failed", "VisionEngine not available.")
            return
        try:
            ok = self._vision_engine.reload_model()
            if ok:
                self._log("✅ Model reloaded successfully")
                QMessageBox.information(
                    self, "Model Reloaded", "New YOLO26x weights loaded."
                )
            else:
                self._log("⚠ Reload failed — weights file may be missing")
                QMessageBox.warning(
                    self, "Reload Failed", "Could not load new model weights."
                )
        except Exception as exc:
            QMessageBox.warning(self, "Reload Error", str(exc))

    # ------------------------------------------------------------------
    # Class selection helpers
    # ------------------------------------------------------------------

    def _update_class_checkboxes(self) -> None:
        """Refresh checkbox labels with current per-class image counts.

        Classes that have at least one image in their subfolder are enabled
        and auto-checked.  Classes with zero images are disabled and unchecked.
        Called automatically by _refresh_stats().
        """
        if not self._class_checkboxes:
            return
        counts = self._dm.get_class_image_counts()
        for cls, cb in self._class_checkboxes.items():
            cnt = counts.get(cls, 0)
            cb.setText(f"{cls}  ({cnt} imgs)")
            if cnt > 0:
                cb.setEnabled(True)
                cb.setChecked(True)  # auto-select classes that have images
            else:
                cb.setEnabled(False)
                cb.setChecked(False)

    def _on_select_all_classes(self) -> None:
        """Check all enabled (image-bearing) class checkboxes."""
        for cb in self._class_checkboxes.values():
            if cb.isEnabled():
                cb.setChecked(True)

    def _on_deselect_all_classes(self) -> None:
        """Uncheck all class checkboxes."""
        for cb in self._class_checkboxes.values():
            cb.setChecked(False)

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
            f"Images: {stats['image_count']}",
            f"Annotations: {stats['annotation_count']}",
            "",
            "Per-class annotation count:",
        ]
        for cls, cnt in stats["class_counts"].items():
            if cnt > 0:
                lines.append(f"  {cls}: {cnt}")

        # Training readiness hint
        total_imgs = stats["image_count"]
        if total_imgs == 0:
            lines.append("\n⚠ Add annotated images to enable training.")
        elif total_imgs < 10:
            lines.append(
                f"\n⚠ {total_imgs} images — recommend at least 30 for reliable results."
            )
        elif total_imgs < 30:
            lines.append(
                f"\n✓ {total_imgs} images — acceptable with the pretrained seed."
            )
        else:
            lines.append(f"\n✓ {total_imgs} images — sufficient for fine-tuning.")

        self._txt_stats.setText("\n".join(lines))

        # Sync class checkboxes with latest per-class image counts
        self._update_class_checkboxes()

    def _set_default_base_model(self) -> None:
        if not _QT_AVAILABLE:
            return

        for idx, (_, path) in enumerate(_BASE_MODEL_OPTIONS):
            if resolve_model_artifact(path).exists():
                self._combo_base.setCurrentIndex(idx)
                return

        preferred = resolve_finetune_seed_model()
        for idx, (_, path) in enumerate(_BASE_MODEL_OPTIONS):
            if resolve_model_artifact(path) == preferred:
                self._combo_base.setCurrentIndex(idx)
                return

        if self._combo_base.count() > 0:
            self._combo_base.setCurrentIndex(0)
