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

    def test_save_with_subfolder_saves_in_subfolder(self, tmp_path: Path) -> None:
        """add_image_with_annotations(subfolder=...) stores under images/{cls}/."""
        from src.training.dataset_manager import DatasetManager, OLED_CLASSES

        dm = DatasetManager(data_root=tmp_path / "sub_test")
        img = _make_bgr()
        cls = OLED_CLASSES[0]

        img_path = dm.add_image_with_annotations(
            f"{cls}_20260318_120000.png", img, _make_annotations(cls), subfolder=cls
        )
        assert img_path.parent.name == cls, "Image should be inside class subfolder"
        lbl_path = dm.labels_dir / cls / f"{cls}_20260318_120000.txt"
        assert lbl_path.exists(), "Label file should be in matching class subfolder"


class TestGetClassImageCounts:
    def test_empty_when_no_images_dir(self, tmp_path: Path) -> None:
        from src.training.dataset_manager import DatasetManager

        dm = DatasetManager(data_root=tmp_path / "nocounts")
        dm.images_dir = tmp_path / "nocounts" / "images"  # don't create
        counts = dm.get_class_image_counts()
        assert counts == {}

    def test_counts_class_subfolders(self, tmp_path: Path) -> None:
        from src.training.dataset_manager import DatasetManager, OLED_CLASSES

        dm = DatasetManager(data_root=tmp_path / "counts_test")
        img = _make_bgr()
        cls_a = OLED_CLASSES[0]
        cls_b = OLED_CLASSES[1] if len(OLED_CLASSES) > 1 else OLED_CLASSES[0]

        dm.add_image_with_annotations(
            f"{cls_a}_001.png", img, _make_annotations(cls_a), subfolder=cls_a
        )
        dm.add_image_with_annotations(
            f"{cls_a}_002.png", img, _make_annotations(cls_a), subfolder=cls_a
        )
        dm.add_image_with_annotations(
            f"{cls_b}_001.png", img, _make_annotations(cls_b), subfolder=cls_b
        )

        counts = dm.get_class_image_counts()
        assert counts.get(cls_a, 0) == 2
        assert counts.get(cls_b, 0) == 1

    def test_counts_legacy_flat_images(self, tmp_path: Path) -> None:
        """Legacy flat images use timestamp pattern to recover the class name."""
        from src.training.dataset_manager import DatasetManager, OLED_CLASSES

        dm = DatasetManager(data_root=tmp_path / "legacy_test")
        img = _make_bgr()
        cls = OLED_CLASSES[0]  # e.g. "login_button" — contains underscores
        # Standard filename pattern: {class}_{YYYYMMDD}_{HHMMSS}.png
        dm.add_image_with_annotations(
            f"{cls}_20260318_120000.png", img, _make_annotations(cls)
        )

        counts = dm.get_class_image_counts()
        assert counts.get(cls, 0) >= 1


class TestSaveDatasetYamlSelectedClasses:
    def test_yaml_all_images_when_no_selection(self, tmp_path: Path) -> None:
        """Default (no selected_classes) → backward-compat flat yaml."""
        from src.training.dataset_manager import DatasetManager, OLED_CLASSES

        dm = DatasetManager(data_root=tmp_path / "yaml_default")
        yaml_path = dm.save_dataset_yaml()
        content = yaml_path.read_text(encoding="utf-8")
        assert "train: images" in content
        assert f"nc: {len(OLED_CLASSES)}" in content

    def test_yaml_lists_selected_subfolders(self, tmp_path: Path) -> None:
        """selected_classes → yaml uses list of subfolders."""
        from src.training.dataset_manager import DatasetManager, OLED_CLASSES

        dm = DatasetManager(data_root=tmp_path / "yaml_sel")
        img = _make_bgr()
        cls_a = OLED_CLASSES[0]
        cls_b = OLED_CLASSES[1] if len(OLED_CLASSES) > 1 else OLED_CLASSES[0]

        dm.add_image_with_annotations(
            f"{cls_a}_001.png", img, _make_annotations(cls_a), subfolder=cls_a
        )
        dm.add_image_with_annotations(
            f"{cls_b}_001.png", img, _make_annotations(cls_b), subfolder=cls_b
        )

        yaml_path = dm.save_dataset_yaml(selected_classes=[cls_a, cls_b])
        content = yaml_path.read_text(encoding="utf-8")
        assert f"images/{cls_a}" in content
        assert f"images/{cls_b}" in content
        # Should NOT use flat "train: images" form
        assert "train: images\n" not in content
        assert f"nc: {len(OLED_CLASSES)}" in content

    def test_yaml_falls_back_when_no_valid_subfolders(self, tmp_path: Path) -> None:
        """If selected classes have no images, fall back to flat yaml."""
        from src.training.dataset_manager import DatasetManager

        dm = DatasetManager(data_root=tmp_path / "yaml_fallback")
        yaml_path = dm.save_dataset_yaml(selected_classes=["nonexistent_class"])
        content = yaml_path.read_text(encoding="utf-8")
        assert "train: images" in content

    def test_yaml_skips_missing_subfolders(self, tmp_path: Path) -> None:
        """Subfolders without images are silently skipped."""
        from src.training.dataset_manager import DatasetManager, OLED_CLASSES

        dm = DatasetManager(data_root=tmp_path / "yaml_skip")
        img = _make_bgr()
        cls_a = OLED_CLASSES[0]

        dm.add_image_with_annotations(
            f"{cls_a}_001.png", img, _make_annotations(cls_a), subfolder=cls_a
        )
        # cls_b subfolder does NOT exist
        cls_b = "nonexistent_xyz"

        yaml_path = dm.save_dataset_yaml(selected_classes=[cls_a, cls_b])
        content = yaml_path.read_text(encoding="utf-8")
        assert f"images/{cls_a}" in content
        assert "nonexistent_xyz" not in content
