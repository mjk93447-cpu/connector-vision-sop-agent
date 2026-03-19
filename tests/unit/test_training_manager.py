"""
Unit tests for src/training/training_manager.py.

Covers:
- FileNotFoundError when start weights file is missing
- YOLO_OFFLINE environment variable is set before training starts
- FileNotFoundError when dataset.yaml is missing
- ValueError when no training images found (img_count == 0)
- ULTRALYTICS_OFFLINE env var is set
- _count_training_images() for flat yaml, list yaml, and invalid yaml
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_minimal_yaml(path: Path) -> None:
    """Write a minimal dataset.yaml so the file-check passes.

    Creates a dummy PNG in ``images/`` next to the yaml so that
    ``_count_training_images()`` returns >= 1 (not 0) and the pre-validation
    step doesn't raise ValueError before reaching the model-file check.
    """
    images_dir = path.parent / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    (images_dir / "dummy.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    yaml_root = str(path.parent.resolve()).replace("\\", "/")
    path.write_text(
        f"path: {yaml_root}\ntrain: images\nval: images\nnc: 1\nnames: ['button']\n",
        encoding="utf-8",
    )


def _write_dummy_pt(path: Path) -> None:
    """Write a dummy .pt file so the exists() check passes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00dummy_weights")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTrainingManagerFileNotFound:
    def test_raises_when_model_missing(self, tmp_path: Path) -> None:
        """train() must raise FileNotFoundError when start weights do not exist."""
        from src.training.training_manager import TrainingManager

        yaml_path = tmp_path / "dataset.yaml"
        _write_minimal_yaml(yaml_path)

        tm = TrainingManager(
            base_model=str(tmp_path / "nonexistent_yolo26x.pt"),
            target_weights=tmp_path / "target.pt",
        )

        with pytest.raises(FileNotFoundError, match="Model file not found"):
            tm.train(dataset_yaml=yaml_path, epochs=1)

    def test_raises_when_dataset_yaml_missing(self, tmp_path: Path) -> None:
        """train() must raise FileNotFoundError when dataset.yaml does not exist."""
        from src.training.training_manager import TrainingManager

        weights_path = tmp_path / "yolo26x.pt"
        _write_dummy_pt(weights_path)

        tm = TrainingManager(
            base_model=str(weights_path),
            target_weights=tmp_path / "target.pt",
        )

        with pytest.raises(FileNotFoundError, match="dataset.yaml not found"):
            tm.train(dataset_yaml=tmp_path / "no_such.yaml", epochs=1)

    def test_error_message_contains_instructions(self, tmp_path: Path) -> None:
        """FileNotFoundError message should guide the user."""
        from src.training.training_manager import TrainingManager

        yaml_path = tmp_path / "dataset.yaml"
        _write_minimal_yaml(yaml_path)

        tm = TrainingManager(
            base_model=str(tmp_path / "missing.pt"),
            target_weights=tmp_path / "out.pt",
        )

        with pytest.raises(FileNotFoundError) as exc_info:
            tm.train(dataset_yaml=yaml_path, epochs=1)

        # Message should hint that model needs to be placed locally
        assert "missing.pt" in str(exc_info.value)


class TestTrainingManagerOfflineGuard:
    def test_yolo_offline_env_is_set_to_one(self, tmp_path: Path) -> None:
        """After a FileNotFoundError is triggered, YOLO_OFFLINE should be '1'.

        The train() method sets YOLO_OFFLINE before any other work, so even
        when it exits early via FileNotFoundError the env var is set.
        """
        from src.training.training_manager import TrainingManager

        yaml_path = tmp_path / "dataset.yaml"
        _write_minimal_yaml(yaml_path)

        tm = TrainingManager(
            base_model=str(tmp_path / "nonexistent.pt"),
            target_weights=tmp_path / "out.pt",
        )

        # YOLO_OFFLINE is set at the very start of train() — before file checks.
        try:
            tm.train(dataset_yaml=yaml_path, epochs=1)
        except FileNotFoundError:
            pass

        assert os.environ.get("YOLO_OFFLINE") == "1"

    def test_yolo_offline_set_even_on_dataset_missing(self, tmp_path: Path) -> None:
        """YOLO_OFFLINE is set before the dataset.yaml check as well."""
        from src.training.training_manager import TrainingManager

        weights_path = tmp_path / "yolo26x.pt"
        _write_dummy_pt(weights_path)

        tm = TrainingManager(
            base_model=str(weights_path),
            target_weights=tmp_path / "out.pt",
        )

        try:
            tm.train(dataset_yaml=tmp_path / "no_such.yaml", epochs=1)
        except FileNotFoundError:
            pass

        assert os.environ.get("YOLO_OFFLINE") == "1"


class TestTrainingManagerBaseModelPriority:
    def test_target_weights_takes_priority_when_exists(self, tmp_path: Path) -> None:
        """When target_weights exists, FileNotFoundError is NOT raised for missing base.

        This verifies that the priority logic (target > base_model override > default)
        works correctly: if target exists, base_model isn't needed.
        """
        from src.training.training_manager import TrainingManager

        yaml_path = tmp_path / "dataset.yaml"
        _write_minimal_yaml(yaml_path)

        target = tmp_path / "target.pt"
        _write_dummy_pt(target)

        # base_model does NOT exist — but target takes priority so no error
        tm = TrainingManager(
            base_model=str(tmp_path / "missing_base.pt"),
            target_weights=target,
        )

        # Patching ultralytics.YOLO at its source so the deferred import is caught
        with patch("ultralytics.YOLO") as mock_yolo_cls:
            mock_model = MagicMock()
            mock_result = MagicMock()
            mock_result.save_dir = None
            mock_model.train.return_value = mock_result
            mock_yolo_cls.return_value = mock_model

            # Should not raise FileNotFoundError (target exists)
            try:
                tm.train(dataset_yaml=yaml_path, epochs=1)
            except ImportError:
                pytest.skip("ultralytics not installed")
            except Exception as exc:
                # Accept any non-FileNotFoundError exception (e.g. model format errors)
                assert "Model file not found" not in str(exc)

    def test_filenotfounderror_when_both_target_and_base_missing(
        self, tmp_path: Path
    ) -> None:
        """FileNotFoundError if neither target nor base_model exists."""
        from src.training.training_manager import TrainingManager

        yaml_path = tmp_path / "dataset.yaml"
        _write_minimal_yaml(yaml_path)

        tm = TrainingManager(
            base_model=str(tmp_path / "missing_base.pt"),
            target_weights=tmp_path / "missing_target.pt",
        )

        with pytest.raises(FileNotFoundError):
            tm.train(dataset_yaml=yaml_path, epochs=1)


# ---------------------------------------------------------------------------
# No-images pre-validation
# ---------------------------------------------------------------------------


class TestTrainingManagerNoImages:
    def test_raises_valueerror_when_no_images_found(self, tmp_path: Path) -> None:
        """train() raises ValueError with helpful message when dataset has 0 images."""
        from src.training.training_manager import TrainingManager

        # Write yaml pointing at an empty images/ dir
        images_dir = tmp_path / "images"
        images_dir.mkdir()
        yaml_path = tmp_path / "dataset.yaml"
        yaml_path.write_text(
            f"path: {str(tmp_path).replace(chr(92), '/')}\n"
            "train: images\nval: images\nnc: 1\nnames: ['button']\n",
            encoding="utf-8",
        )

        weights_path = tmp_path / "yolo26x.pt"
        _write_dummy_pt(weights_path)

        tm = TrainingManager(
            base_model=str(weights_path),
            target_weights=tmp_path / "out.pt",
        )

        with pytest.raises(ValueError, match="No training images found"):
            tm.train(dataset_yaml=yaml_path, epochs=1)

    def test_valueerror_message_is_actionable(self, tmp_path: Path) -> None:
        """ValueError message should guide the user to annotate images first."""
        from src.training.training_manager import TrainingManager

        images_dir = tmp_path / "images"
        images_dir.mkdir()
        yaml_path = tmp_path / "dataset.yaml"
        yaml_path.write_text(
            f"path: {str(tmp_path).replace(chr(92), '/')}\n"
            "train: images\nval: images\nnc: 1\nnames: ['button']\n",
            encoding="utf-8",
        )

        weights_path = tmp_path / "yolo26x.pt"
        _write_dummy_pt(weights_path)

        tm = TrainingManager(
            base_model=str(weights_path),
            target_weights=tmp_path / "out.pt",
        )

        with pytest.raises(ValueError) as exc_info:
            tm.train(dataset_yaml=yaml_path, epochs=1)

        msg = str(exc_info.value)
        assert "Training" in msg or "annotate" in msg or "image" in msg.lower()


# ---------------------------------------------------------------------------
# Offline env-var verification
# ---------------------------------------------------------------------------


class TestTrainingManagerOfflineEnvVars:
    def test_ultralytics_offline_env_is_set(self, tmp_path: Path) -> None:
        """ULTRALYTICS_OFFLINE must be set to '1' even when train() exits early."""
        from src.training.training_manager import TrainingManager

        yaml_path = tmp_path / "dataset.yaml"
        _write_minimal_yaml(yaml_path)

        tm = TrainingManager(
            base_model=str(tmp_path / "nonexistent.pt"),
            target_weights=tmp_path / "out.pt",
        )

        try:
            tm.train(dataset_yaml=yaml_path, epochs=1)
        except (FileNotFoundError, ValueError):
            pass

        import os

        assert os.environ.get("ULTRALYTICS_OFFLINE") == "1"

    def test_wandb_disabled_env_is_set(self, tmp_path: Path) -> None:
        """WANDB_DISABLED must be set after train() is called."""
        from src.training.training_manager import TrainingManager

        yaml_path = tmp_path / "dataset.yaml"
        _write_minimal_yaml(yaml_path)

        tm = TrainingManager(
            base_model=str(tmp_path / "nonexistent.pt"),
            target_weights=tmp_path / "out.pt",
        )

        try:
            tm.train(dataset_yaml=yaml_path, epochs=1)
        except (FileNotFoundError, ValueError):
            pass

        import os

        assert os.environ.get("WANDB_DISABLED") == "true"


# ---------------------------------------------------------------------------
# _count_training_images helper
# ---------------------------------------------------------------------------


class TestCountTrainingImages:
    def test_flat_yaml_with_images(self, tmp_path: Path) -> None:
        """Flat 'train: images' yaml → counts *.png under images/ dir."""
        from src.training.training_manager import TrainingManager

        images_dir = tmp_path / "images"
        images_dir.mkdir()
        (images_dir / "a.png").write_bytes(b"\x89PNG")
        (images_dir / "b.png").write_bytes(b"\x89PNG")
        (images_dir / "c.jpg").write_bytes(b"\xff\xd8")  # not counted if not png

        yaml_path = tmp_path / "dataset.yaml"
        yaml_path.write_text(
            f"path: {str(tmp_path).replace(chr(92), '/')}\n"
            "train: images\nval: images\nnc: 1\nnames: ['button']\n",
            encoding="utf-8",
        )

        count = TrainingManager._count_training_images(yaml_path)
        # 2 png + 1 jpg → jpg also counted (any image ext)
        assert count >= 2

    def test_flat_yaml_empty_images_dir(self, tmp_path: Path) -> None:
        """Flat yaml with empty images/ dir → count == 0."""
        from src.training.training_manager import TrainingManager

        (tmp_path / "images").mkdir()
        yaml_path = tmp_path / "dataset.yaml"
        yaml_path.write_text(
            f"path: {str(tmp_path).replace(chr(92), '/')}\n"
            "train: images\nval: images\nnc: 1\nnames: ['button']\n",
            encoding="utf-8",
        )

        count = TrainingManager._count_training_images(yaml_path)
        assert count == 0

    def test_list_yaml_counts_subfolders(self, tmp_path: Path) -> None:
        """List-form 'train: [images/cls_a, images/cls_b]' yaml → counts correctly."""
        from src.training.training_manager import TrainingManager

        cls_a = tmp_path / "images" / "cls_a"
        cls_b = tmp_path / "images" / "cls_b"
        cls_a.mkdir(parents=True)
        cls_b.mkdir(parents=True)
        (cls_a / "img1.png").write_bytes(b"\x89PNG")
        (cls_a / "img2.png").write_bytes(b"\x89PNG")
        (cls_b / "img3.png").write_bytes(b"\x89PNG")

        yaml_root = str(tmp_path).replace("\\", "/")
        yaml_path = tmp_path / "dataset.yaml"
        yaml_path.write_text(
            f"path: {yaml_root}\n"
            "train:\n  - images/cls_a\n  - images/cls_b\n"
            "val:\n  - images/cls_a\nnc: 1\nnames: ['button']\n",
            encoding="utf-8",
        )

        count = TrainingManager._count_training_images(yaml_path)
        assert count == 3

    def test_returns_minus_one_on_invalid_yaml(self, tmp_path: Path) -> None:
        """Unparseable / binary yaml → returns -1 (proceed anyway)."""
        from src.training.training_manager import TrainingManager

        yaml_path = tmp_path / "broken.yaml"
        # Write binary garbage that cannot be decoded as UTF-8 by yaml.safe_load
        yaml_path.write_bytes(b"\xff\xfe\x00\x01invalid\x00")

        count = TrainingManager._count_training_images(yaml_path)
        assert count == -1

    def test_returns_minus_one_when_yaml_missing(self, tmp_path: Path) -> None:
        """Missing yaml file → returns -1."""
        from src.training.training_manager import TrainingManager

        count = TrainingManager._count_training_images(tmp_path / "no_file.yaml")
        assert count == -1


# ---------------------------------------------------------------------------
# Stale-cache cleanup
# ---------------------------------------------------------------------------


class TestCleanStaleCaches:
    """_clean_stale_caches() removes leftover *.cache / *.cache.npy files.

    Background
    ----------
    ultralytics saves label caches as ``labels/<split>.cache`` (e.g.
    ``labels/image_source.cache``).  If a prior training run was interrupted
    after ``np.save()`` but before the ``*.cache.npy`` → ``*.cache`` rename,
    or if the hash mismatches on a subsequent run, the stale ``.cache.npy``
    causes ultralytics to fail with::

        'NoneType' object has no attribute 'write'

    Pre-emptive deletion before every training call ensures a clean start.
    """

    def test_removes_cache_files_adjacent_to_labels(self, tmp_path: Path) -> None:
        """*.cache files directly in labels/ are deleted."""
        from src.training.training_manager import TrainingManager

        labels_dir = tmp_path / "labels"
        labels_dir.mkdir()
        stale = labels_dir / "image_source.cache"
        stale.write_bytes(b"stale-cache-data")

        yaml_path = tmp_path / "dataset.yaml"
        yaml_path.write_text("dummy: yaml\n", encoding="utf-8")

        TrainingManager._clean_stale_caches(yaml_path)

        assert not stale.exists(), "stale .cache file should have been deleted"

    def test_removes_cache_npy_files(self, tmp_path: Path) -> None:
        """*.cache.npy files (partial writes) are deleted."""
        from src.training.training_manager import TrainingManager

        labels_dir = tmp_path / "labels"
        labels_dir.mkdir()
        stale = labels_dir / "image_source.cache.npy"
        stale.write_bytes(b"partial-write")

        yaml_path = tmp_path / "dataset.yaml"
        yaml_path.write_text("dummy: yaml\n", encoding="utf-8")

        TrainingManager._clean_stale_caches(yaml_path)

        assert not stale.exists(), "stale .cache.npy file should have been deleted"

    def test_removes_multiple_class_cache_files(self, tmp_path: Path) -> None:
        """All *.cache and *.cache.npy under labels/ are cleaned, not just one."""
        from src.training.training_manager import TrainingManager

        labels_dir = tmp_path / "labels"
        labels_dir.mkdir()
        files = [
            labels_dir / "image_source.cache",
            labels_dir / "button.cache",
            labels_dir / "button.cache.npy",
        ]
        for f in files:
            f.write_bytes(b"stale")

        yaml_path = tmp_path / "dataset.yaml"
        yaml_path.write_text("dummy: yaml\n", encoding="utf-8")

        TrainingManager._clean_stale_caches(yaml_path)

        for f in files:
            assert not f.exists(), f"{f.name} should have been deleted"

    def test_no_error_when_labels_dir_missing(self, tmp_path: Path) -> None:
        """Silent no-op when labels/ directory does not exist."""
        from src.training.training_manager import TrainingManager

        yaml_path = tmp_path / "dataset.yaml"
        yaml_path.write_text("dummy: yaml\n", encoding="utf-8")

        # Should not raise any exception
        TrainingManager._clean_stale_caches(yaml_path)

    def test_preserves_non_cache_files(self, tmp_path: Path) -> None:
        """Regular .txt label files are NOT deleted."""
        from src.training.training_manager import TrainingManager

        labels_dir = tmp_path / "labels"
        labels_dir.mkdir()
        label_file = labels_dir / "image_source_20260319_123456.txt"
        label_file.write_text("0 0.5 0.5 0.3 0.2\n", encoding="utf-8")

        yaml_path = tmp_path / "dataset.yaml"
        yaml_path.write_text("dummy: yaml\n", encoding="utf-8")

        TrainingManager._clean_stale_caches(yaml_path)

        assert label_file.exists(), ".txt label files must be preserved"

    def test_cleans_nested_subdirectory_caches(self, tmp_path: Path) -> None:
        """*.cache.npy inside labels/image_source/ subdir is also cleaned."""
        from src.training.training_manager import TrainingManager

        subdir = tmp_path / "labels" / "image_source"
        subdir.mkdir(parents=True)
        stale = subdir / "temp.cache.npy"
        stale.write_bytes(b"partial")

        yaml_path = tmp_path / "dataset.yaml"
        yaml_path.write_text("dummy: yaml\n", encoding="utf-8")

        TrainingManager._clean_stale_caches(yaml_path)

        assert not stale.exists(), "nested .cache.npy should be cleaned"
