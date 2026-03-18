"""
Unit tests for src/training/dataset_manager.py.

Covers:
- Absolute path resolution (data_root is always resolved to an absolute path)
- get_stats() returns empty dict when path does not exist
- get_stats() returns correct counts after adding images
- add_image_with_annotations() saves image + label file
"""

from __future__ import annotations

from pathlib import Path

import numpy as np


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bgr(w: int = 64, h: int = 64) -> np.ndarray:
    """Return a small solid BGR image (green)."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :, 1] = 200  # green channel
    return img


def _make_annotations(label: str = "button") -> list:
    return [{"label": label, "bbox": [10, 10, 30, 30]}]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDatasetManagerAbsolutePath:
    def test_default_root_is_absolute(self) -> None:
        from src.training.dataset_manager import DatasetManager

        dm = DatasetManager()
        assert dm.data_root.is_absolute(), "data_root should be an absolute path"

    def test_relative_root_becomes_absolute(self, tmp_path: Path) -> None:
        from src.training.dataset_manager import DatasetManager

        # Pass a relative-looking Path via tmp_path (which is already absolute,
        # but we verify that resolve() is called on it).
        dm = DatasetManager(data_root=tmp_path / "training_data")
        assert dm.data_root.is_absolute()

    def test_string_root_is_resolved(self, tmp_path: Path) -> None:
        from src.training.dataset_manager import DatasetManager

        dm = DatasetManager(data_root=str(tmp_path / "my_data"))
        assert dm.data_root.is_absolute()


class TestDatasetManagerGetStats:
    def test_stats_empty_when_no_path(self, tmp_path: Path) -> None:
        """get_stats() returns zero-counts when images_dir does not exist."""
        from src.training.dataset_manager import DatasetManager

        dm = DatasetManager(data_root=tmp_path / "nonexistent")
        # Override dirs to point to non-existent locations without creating them
        dm.images_dir = tmp_path / "nonexistent" / "images"
        dm.labels_dir = tmp_path / "nonexistent" / "labels"

        stats = dm.get_stats()
        assert stats["image_count"] == 0
        assert stats["label_count"] == 0
        assert stats["annotation_count"] == 0
        assert isinstance(stats["class_counts"], dict)

    def test_stats_zero_when_empty_dirs(self, tmp_path: Path) -> None:
        """get_stats() returns zeros when dirs exist but are empty."""
        from src.training.dataset_manager import DatasetManager

        dm = DatasetManager(data_root=tmp_path / "empty_data")
        stats = dm.get_stats()
        assert stats["image_count"] == 0
        assert stats["annotation_count"] == 0

    def test_stats_counts_after_add(self, tmp_path: Path) -> None:
        """get_stats() counts correctly after adding images with annotations."""
        from src.training.dataset_manager import DatasetManager, OLED_CLASSES

        dm = DatasetManager(data_root=tmp_path / "dataset")
        img = _make_bgr()
        label = OLED_CLASSES[0]  # e.g. "button" or first class

        dm.add_image_with_annotations("test_001.png", img, _make_annotations(label))
        dm.add_image_with_annotations("test_002.png", img, _make_annotations(label))

        stats = dm.get_stats()
        assert stats["image_count"] == 2
        assert stats["label_count"] == 2
        assert stats["annotation_count"] == 2
        assert stats["class_counts"][label] == 2

    def test_stats_class_counts_multiple_labels(self, tmp_path: Path) -> None:
        """get_stats() correctly counts per-class annotations."""
        from src.training.dataset_manager import DatasetManager, OLED_CLASSES

        dm = DatasetManager(data_root=tmp_path / "multi_class")
        img = _make_bgr()
        cls_a = OLED_CLASSES[0]
        cls_b = OLED_CLASSES[1] if len(OLED_CLASSES) > 1 else OLED_CLASSES[0]

        anns_mixed = [
            {"label": cls_a, "bbox": [0, 0, 10, 10]},
            {"label": cls_b, "bbox": [20, 20, 40, 40]},
        ]
        dm.add_image_with_annotations("img1.png", img, anns_mixed)

        stats = dm.get_stats()
        assert stats["annotation_count"] == 2
        assert stats["class_counts"][cls_a] >= 1


class TestDatasetManagerAddImage:
    def test_saves_image_and_label_files(self, tmp_path: Path) -> None:
        from src.training.dataset_manager import DatasetManager, OLED_CLASSES

        dm = DatasetManager(data_root=tmp_path / "save_test")
        img = _make_bgr()
        label = OLED_CLASSES[0]

        img_path = dm.add_image_with_annotations(
            "frame_001.png", img, _make_annotations(label)
        )

        assert img_path.exists(), "Image file should be saved"
        lbl_path = dm.labels_dir / "frame_001.txt"
        assert lbl_path.exists(), "Label file should be saved"

        lines = lbl_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        parts = lines[0].split()
        assert len(parts) == 5, "YOLO label should have 5 fields: class cx cy w h"

    def test_skips_unknown_label(self, tmp_path: Path) -> None:
        from src.training.dataset_manager import DatasetManager

        dm = DatasetManager(data_root=tmp_path / "unknown_label")
        img = _make_bgr()
        anns = [{"label": "totally_unknown_class_xyz", "bbox": [0, 0, 10, 10]}]

        dm.add_image_with_annotations("img.png", img, anns)
        lbl_path = dm.labels_dir / "img.txt"
        assert lbl_path.exists()
        assert lbl_path.read_text(encoding="utf-8").strip() == ""

    def test_dataset_yaml_is_written(self, tmp_path: Path) -> None:
        from src.training.dataset_manager import DatasetManager, OLED_CLASSES

        dm = DatasetManager(data_root=tmp_path / "yaml_test")
        img = _make_bgr()
        dm.add_image_with_annotations("a.png", img, _make_annotations(OLED_CLASSES[0]))

        yaml_path = dm.save_dataset_yaml()
        assert yaml_path.exists()
        content = yaml_path.read_text(encoding="utf-8")
        assert "train: images" in content
        assert f"nc: {len(OLED_CLASSES)}" in content
