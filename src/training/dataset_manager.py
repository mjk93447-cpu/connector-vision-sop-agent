"""
YOLO-format dataset manager for OLED line PC annotations.

Folder layout produced by this module:
  training_data/
    images/
      {class}/     *.png  (source images, organised by primary class)
    labels/
      {class}/     *.txt  (YOLO annotation: class cx cy w h, normalised 0-1)
    dataset.yaml   (ultralytics training config)

  Legacy flat layout (images/*.png, labels/*.txt) is still supported for
  backward-compatibility — get_stats() scans recursively.

Usage
-----
  dm = DatasetManager()
  dm.add_image_with_annotations("screen.png", img_array, annotations)
  dm.save_dataset_yaml()
  stats = dm.get_stats()
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import cv2
import numpy as np

from src.config_loader import get_base_dir
from src.vision_engine import DEFAULT_TARGET_LABELS

# Dataset root: absolute path so EXE and source-run both resolve correctly
_DEFAULT_DATA_ROOT = get_base_dir() / "training_data"

# OLED class names in fixed order (index == YOLO class id)
OLED_CLASSES: List[str] = list(DEFAULT_TARGET_LABELS)


class DatasetManager:
    """Manages a YOLO-format annotation dataset for OLED UI fine-tuning."""

    def __init__(self, data_root: str | Path = _DEFAULT_DATA_ROOT) -> None:
        self.data_root = Path(data_root).resolve()  # always absolute
        self.images_dir = self.data_root / "images"
        self.labels_dir = self.data_root / "labels"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.labels_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def class_names(self) -> List[str]:
        return OLED_CLASSES

    def add_image_with_annotations(
        self,
        image_name: str,
        image: np.ndarray,
        annotations: List[Dict[str, Any]],
        subfolder: str = "",
    ) -> Path:
        """Save an image and its YOLO-format label file.

        Parameters
        ----------
        image_name:   Filename without path (e.g. ``"button_20260318_143022.png"``).
        image:        BGR numpy array.
        annotations:  List of dicts::

                        {
                          "label": "login_button",
                          "bbox": [x1, y1, x2, y2]   # pixel coords, absolute
                        }
        subfolder:    Optional class-based subfolder name (e.g. ``"button"``).
                      When provided, images and labels are stored in
                      ``images/{subfolder}/`` and ``labels/{subfolder}/``
                      respectively. Defaults to ``""`` (flat layout).

        Returns the path to the saved image.
        """
        stem = Path(image_name).stem
        if subfolder:
            img_dir = self.images_dir / subfolder
            lbl_dir = self.labels_dir / subfolder
            img_dir.mkdir(parents=True, exist_ok=True)
            lbl_dir.mkdir(parents=True, exist_ok=True)
        else:
            img_dir = self.images_dir
            lbl_dir = self.labels_dir
        img_path = img_dir / f"{stem}.png"
        lbl_path = lbl_dir / f"{stem}.txt"

        cv2.imwrite(str(img_path), image)

        h, w = image.shape[:2]
        lines: List[str] = []
        for ann in annotations:
            class_id = self._label_to_id(ann.get("label", ""))
            if class_id < 0:
                continue
            x1, y1, x2, y2 = [float(v) for v in ann["bbox"][:4]]
            cx = (x1 + x2) / 2.0 / w
            cy = (y1 + y2) / 2.0 / h
            bw = abs(x2 - x1) / w
            bh = abs(y2 - y1) / h
            lines.append(f"{class_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

        lbl_path.write_text("\n".join(lines), encoding="utf-8")
        return img_path

    def save_dataset_yaml(self) -> Path:
        """Write ``training_data/dataset.yaml`` for ultralytics training."""
        yaml_path = self.data_root / "dataset.yaml"
        content = (
            f"path: {self.data_root.resolve()}\n"
            "train: images\n"
            "val: images\n"
            f"nc: {len(OLED_CLASSES)}\n"
            f"names: {json.dumps(OLED_CLASSES, ensure_ascii=False)}\n"
        )
        yaml_path.write_text(content, encoding="utf-8")
        return yaml_path

    def get_stats(self) -> Dict[str, Any]:
        """Return basic dataset stats for the Training panel display."""
        if not self.images_dir.exists():
            return {
                "image_count": 0,
                "label_count": 0,
                "annotation_count": 0,
                "class_counts": {name: 0 for name in OLED_CLASSES},
            }
        img_count = len(list(self.images_dir.rglob("*.png")))
        lbl_count = (
            len(list(self.labels_dir.rglob("*.txt"))) if self.labels_dir.exists() else 0
        )
        ann_count = 0
        class_counts: Dict[str, int] = {name: 0 for name in OLED_CLASSES}

        if not self.labels_dir.exists():
            return {
                "image_count": img_count,
                "label_count": 0,
                "annotation_count": 0,
                "class_counts": class_counts,
            }

        for lbl_file in self.labels_dir.rglob("*.txt"):
            text = lbl_file.read_text(encoding="utf-8").strip()
            for line in text.splitlines():
                parts = line.split()
                if parts:
                    try:
                        cid = int(parts[0])
                        if 0 <= cid < len(OLED_CLASSES):
                            class_counts[OLED_CLASSES[cid]] += 1
                            ann_count += 1
                    except ValueError:
                        pass

        return {
            "image_count": img_count,
            "label_count": lbl_count,
            "annotation_count": ann_count,
            "class_counts": class_counts,
        }

    def delete_annotation(self, image_name: str) -> None:
        """Remove an image and its label file from the dataset."""
        stem = Path(image_name).stem
        img_path = self.images_dir / f"{stem}.png"
        lbl_path = self.labels_dir / f"{stem}.txt"
        for p in (img_path, lbl_path):
            if p.exists():
                p.unlink()

    def list_images(self) -> List[str]:
        """Return sorted list of image stems in the dataset."""
        return sorted(p.name for p in self.images_dir.glob("*.png"))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _label_to_id(self, label: str) -> int:
        try:
            return OLED_CLASSES.index(label)
        except ValueError:
            return -1
