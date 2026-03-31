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
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from src.config_loader import get_base_dir
from src.vision_engine import DEFAULT_TARGET_LABELS

# Dataset root: absolute path so EXE and source-run both resolve correctly
_DEFAULT_DATA_ROOT = get_base_dir() / "training_data"

# Matches the systematic timestamp suffix: _{YYYYMMDD}_{HHMMSS}[_{n}] at end of stem
# e.g.  "login_button_20260318_143022"  →  class = "login_button"
#        "connector_pin_20260318_143022_001"  →  class = "connector_pin"
_TIMESTAMP_RE = re.compile(r"_\d{8}_\d{6}(?:_\d+)?$")

# OLED class names in fixed order (index == YOLO class id)
OLED_CLASSES: List[str] = list(DEFAULT_TARGET_LABELS)

_CLASS_ALIASES = {
    "mold_left": "mold_left_label",
    "mold_right": "mold_right_label",
}


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

    def get_class_image_counts(self) -> Dict[str, int]:
        """Return number of images per class subfolder under ``images/``.

        Scans ``images/{cls}/`` for every directory that exists.
        Classes without a subfolder return 0.
        Also counts legacy flat images (``images/{cls}_*.png``) for any class
        not yet stored in a subfolder.
        """
        counts: Dict[str, int] = {}
        if not self.images_dir.exists():
            return counts

        # Class subfolders created by new save logic
        for cls_dir in sorted(self.images_dir.iterdir()):
            if cls_dir.is_dir():
                counts[cls_dir.name] = len(list(cls_dir.rglob("*.png")))

        # Legacy flat images: credit them to the class derived from the filename.
        # Filename convention: {class}_{YYYYMMDD}_{HHMMSS}[_{n}].png
        # Strip the trailing timestamp to recover the class name.
        for img_file in self.images_dir.glob("*.png"):
            stem = img_file.stem
            m = _TIMESTAMP_RE.search(stem)
            cls = stem[: m.start()] if m else stem
            if cls:
                counts[cls] = counts.get(cls, 0) + 1

        return counts

    def save_dataset_yaml(self, selected_classes: Optional[List[str]] = None) -> Path:
        """Write ``training_data/dataset.yaml`` for ultralytics training.

        Parameters
        ----------
        selected_classes:
            Optional list of class names to include.  When provided only the
            matching ``images/{cls}/`` subfolders are listed in the yaml so
            YOLO trains on exactly those classes' images.  Subfolders that
            do not exist on disk are silently skipped.

            Pass ``None`` (default) to scan the entire ``images/`` directory
            recursively — equivalent to the previous behaviour.
        """
        yaml_path = self.data_root / "dataset.yaml"

        # Always use forward slashes in the yaml path field.
        # Windows backslashes (e.g. C:\training_data) can confuse ultralytics'
        # YAML parser — especially \t → tab and \n → newline sequences —
        # causing path resolution to silently fail and im_files to be empty,
        # which leads to cache_path=None and the cryptic
        # "NoneType has no attribute 'write'" error.
        yaml_root = str(self.data_root.resolve()).replace("\\", "/")

        if selected_classes:
            # Keep only subfolders that exist and contain at least one image
            valid_classes = [
                cls
                for cls in selected_classes
                if (self.images_dir / cls).is_dir()
                and any((self.images_dir / cls).rglob("*.png"))
            ]
            if valid_classes:
                paths_str = "\n".join(f"  - images/{cls}" for cls in valid_classes)
                content = (
                    f"path: {yaml_root}\n"
                    f"train:\n{paths_str}\n"
                    f"val:\n{paths_str}\n"
                    f"nc: {len(OLED_CLASSES)}\n"
                    f"names: {json.dumps(OLED_CLASSES, ensure_ascii=False)}\n"
                )
                yaml_path.write_text(content, encoding="utf-8")
                return yaml_path
            # Fall through to default if no valid subfolders found

        # Default: scan entire images/ directory (ultralytics handles subfolders
        # recursively when given a parent directory path)
        content = (
            f"path: {yaml_root}\n"
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
        label = _CLASS_ALIASES.get(label, label)
        try:
            return OLED_CLASSES.index(label)
        except ValueError:
            return -1
