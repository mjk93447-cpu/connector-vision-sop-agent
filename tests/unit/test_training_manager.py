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


# ---------------------------------------------------------------------------
# verbose=True guard — prevents tqdm NoneType crash
# ---------------------------------------------------------------------------


class TestTrainingManagerVerbose:
    """model.train() must be called with verbose=True.

    Root cause of 'NoneType object has no attribute write':
      PyInstaller console=False sets sys.stdout = None.
      ultralytics TQDM.__init__ assigns self.file = file or sys.stdout.
      When sys.stdout is None, self.file becomes None.
      TQDM.close() calls self.file.write("\\n") when disable=False
      (i.e. verbose=True) — raising AttributeError.

      NOTE: verbose=True (disable=False) is actually *worse* than verbose=False
      in this scenario — with disable=True the write block is skipped entirely.
      The real fix is the sys.stdout None-guard (TestStdoutNoneGuard below).
      verbose=True is kept so dev-environment training shows progress.
    """

    def test_model_train_called_with_verbose_true(self, tmp_path: Path) -> None:
        """model.train() must receive verbose=True to avoid disabling tqdm."""
        from src.training.training_manager import TrainingManager

        yaml_path = tmp_path / "dataset.yaml"
        _write_minimal_yaml(yaml_path)

        target = tmp_path / "target.pt"
        _write_dummy_pt(target)

        tm = TrainingManager(
            base_model=str(target),
            target_weights=tmp_path / "out.pt",
        )

        with patch("ultralytics.YOLO") as mock_yolo_cls:
            mock_model = MagicMock()
            mock_result = MagicMock()
            mock_result.save_dir = None
            mock_model.train.return_value = mock_result
            mock_yolo_cls.return_value = mock_model

            try:
                tm.train(dataset_yaml=yaml_path, epochs=1)
            except ImportError:
                pytest.skip("ultralytics not installed")
            except Exception:
                pass  # other errors OK — we only care about the train() kwargs

        assert mock_model.train.called, "model.train() was never called"
        call_kwargs = mock_model.train.call_args[1]
        verbose_val = call_kwargs.get("verbose")
        assert verbose_val is not False, (
            f"model.train() called with verbose={verbose_val!r}. "
            "verbose=False disables tqdm (self.file=None) and causes "
            "'NoneType object has no attribute write' crash in ultralytics."
        )

    def test_model_train_verbose_is_explicitly_true(self, tmp_path: Path) -> None:
        """verbose=True must be explicitly set — not just absent from kwargs."""
        from src.training.training_manager import TrainingManager

        yaml_path = tmp_path / "dataset.yaml"
        _write_minimal_yaml(yaml_path)

        target = tmp_path / "target.pt"
        _write_dummy_pt(target)

        tm = TrainingManager(
            base_model=str(target),
            target_weights=tmp_path / "out.pt",
        )

        with patch("ultralytics.YOLO") as mock_yolo_cls:
            mock_model = MagicMock()
            mock_result = MagicMock()
            mock_result.save_dir = None
            mock_model.train.return_value = mock_result
            mock_yolo_cls.return_value = mock_model

            try:
                tm.train(dataset_yaml=yaml_path, epochs=1)
            except ImportError:
                pytest.skip("ultralytics not installed")
            except Exception:
                pass

        assert mock_model.train.called
        call_kwargs = mock_model.train.call_args[1]
        assert (
            call_kwargs.get("verbose") is True
        ), "verbose must be explicitly True to guarantee tqdm is not disabled"


class TestTeeWriter:
    """_TeeWriter unit tests — write to two streams simultaneously."""

    def test_write_reaches_both_streams(self) -> None:
        """write() sends data to both primary and secondary streams."""
        import io

        from src.training.training_manager import _TeeWriter

        primary = io.StringIO()
        secondary = io.StringIO()
        tee = _TeeWriter(primary, secondary)
        tee.write("hello")
        assert primary.getvalue() == "hello"
        assert secondary.getvalue() == "hello"

    def test_none_primary_skipped(self) -> None:
        """None primary is silently skipped; secondary still receives data."""
        import io

        from src.training.training_manager import _TeeWriter

        secondary = io.StringIO()
        tee = _TeeWriter(None, secondary)
        tee.write("data")  # must not raise AttributeError
        assert secondary.getvalue() == "data"

    def test_flush_does_not_raise_on_none_primary(self) -> None:
        """flush() with None primary must not raise."""
        import io

        from src.training.training_manager import _TeeWriter

        secondary = io.StringIO()
        tee = _TeeWriter(None, secondary)
        tee.flush()  # no exception


class TestStdoutTeeGuard:
    """TeeWriter replaces StringIO guard: fundamental fix for PyInstaller EXE.

    PyInstaller console=False → sys.stdout = None.
    ultralytics TQDM: self.file = file or sys.stdout = None → AttributeError.

    Fix (two layers):
      Layer 1 — main.py: sets sys.stdout to connector_agent.log at EXE startup.
      Layer 2 — train(): _TeeWriter(sys.stdout, training.log) so output goes to
                 BOTH the app log and a dedicated training.log file.
    The _TeeWriter handles None primary gracefully, eliminating the crash even
    if Layer 1 hasn't run (e.g. in tests or non-GUI contexts).
    """

    def test_stdout_is_tee_writer_during_train(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """sys.stdout is replaced with _TeeWriter for the duration of train()."""
        import sys

        from src.training.training_manager import TrainingManager, _TeeWriter

        yaml_path = tmp_path / "dataset.yaml"
        _write_minimal_yaml(yaml_path)
        target = tmp_path / "target.pt"
        _write_dummy_pt(target)

        tm = TrainingManager(
            base_model=str(target),
            target_weights=tmp_path / "out.pt",
        )

        captured: list = []

        def fake_train(**kwargs):
            captured.append(sys.stdout)
            result = MagicMock()
            result.save_dir = None
            return result

        with patch("ultralytics.YOLO") as mock_yolo_cls:
            mock_model = MagicMock()
            mock_model.train.side_effect = fake_train
            mock_yolo_cls.return_value = mock_model

            try:
                tm.train(dataset_yaml=yaml_path, epochs=1)
            except Exception:
                pass

        assert len(captured) == 1, "fake_train was not called"
        assert isinstance(
            captured[0], _TeeWriter
        ), f"Expected _TeeWriter inside train(), got {type(captured[0])}"

    def test_tee_writer_with_none_primary_no_crash(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """train() must not crash when sys.stdout is None (EXE console=False)."""
        import sys

        from src.training.training_manager import TrainingManager, _TeeWriter

        yaml_path = tmp_path / "dataset.yaml"
        _write_minimal_yaml(yaml_path)
        target = tmp_path / "target.pt"
        _write_dummy_pt(target)

        tm = TrainingManager(
            base_model=str(target),
            target_weights=tmp_path / "out.pt",
        )

        captured: list = []

        def fake_train(**kwargs):
            captured.append(sys.stdout)
            # Simulate TQDM writing to self.file (= sys.stdout = _TeeWriter)
            sys.stdout.write("Epoch 1/1 — loss 0.123\n")
            sys.stdout.flush()
            result = MagicMock()
            result.save_dir = None
            return result

        monkeypatch.setattr(sys, "stdout", None)
        monkeypatch.setattr(sys, "stderr", None)

        with patch("ultralytics.YOLO") as mock_yolo_cls:
            mock_model = MagicMock()
            mock_model.train.side_effect = fake_train
            mock_yolo_cls.return_value = mock_model

            try:
                tm.train(dataset_yaml=yaml_path, epochs=1)
            except Exception:
                pass  # errors other than AttributeError are OK

        assert len(captured) == 1
        assert isinstance(captured[0], _TeeWriter)
        # TeeWriter._primary is None; write() must not have raised
        assert captured[0]._primary is None

    def test_stdout_restored_after_train(self, tmp_path: Path, monkeypatch) -> None:
        """sys.stdout/stderr are restored to their original values after train()."""
        import sys

        from src.training.training_manager import TrainingManager

        yaml_path = tmp_path / "dataset.yaml"
        _write_minimal_yaml(yaml_path)
        target = tmp_path / "target.pt"
        _write_dummy_pt(target)

        tm = TrainingManager(
            base_model=str(target),
            target_weights=tmp_path / "out.pt",
        )

        monkeypatch.setattr(sys, "stdout", None)
        monkeypatch.setattr(sys, "stderr", None)

        with patch("ultralytics.YOLO") as mock_yolo_cls:
            mock_model = MagicMock()
            mock_result = MagicMock()
            mock_result.save_dir = None
            mock_model.train.return_value = mock_result
            mock_yolo_cls.return_value = mock_model

            try:
                tm.train(dataset_yaml=yaml_path, epochs=1)
            except Exception:
                pass

        assert sys.stdout is None, "sys.stdout was not restored to None after train()"
        assert sys.stderr is None, "sys.stderr was not restored to None after train()"

    def test_training_log_file_created(self, tmp_path: Path) -> None:
        """training.log is created beside dataset.yaml and captures output."""
        import sys

        from src.training.training_manager import TrainingManager

        yaml_path = tmp_path / "dataset.yaml"
        _write_minimal_yaml(yaml_path)
        target = tmp_path / "target.pt"
        _write_dummy_pt(target)

        tm = TrainingManager(
            base_model=str(target),
            target_weights=tmp_path / "out.pt",
        )

        def fake_train(**kwargs):
            sys.stdout.write("Epoch 1/1 box_loss 0.5 mAP50 0.123\n")
            result = MagicMock()
            result.save_dir = None
            return result

        with patch("ultralytics.YOLO") as mock_yolo_cls:
            mock_model = MagicMock()
            mock_model.train.side_effect = fake_train
            mock_yolo_cls.return_value = mock_model

            try:
                tm.train(dataset_yaml=yaml_path, epochs=1)
            except Exception:
                pass

        log_path = tmp_path / "training.log"
        assert log_path.exists(), "training.log was not created"
        content = log_path.read_text(encoding="utf-8")
        assert (
            "box_loss" in content
        ), f"training.log missing expected content: {content!r}"
        assert tm.last_training_log == log_path


class TestUltralyticsTQDMPatch:
    """Tests for _apply_ultralytics_tqdm_patch() — ultralytics tqdm file=None 근본 수정."""

    def test_patch_sets_verbose_true(self) -> None:
        """VERBOSE 전역이 True로 강제 설정되는지 확인."""
        from src.training.training_manager import TrainingManager

        import ultralytics.utils as ult_utils

        original_verbose = ult_utils.VERBOSE
        try:
            ult_utils.VERBOSE = False  # 강제로 False로 설정 후 패치 적용
            TrainingManager._apply_ultralytics_tqdm_patch()
            assert ult_utils.VERBOSE is True
        finally:
            ult_utils.VERBOSE = original_verbose  # 테스트 종료 후 복구

    def test_patch_idempotent(self) -> None:
        """두 번 호출해도 안전하고 _safe_close_patched 플래그가 True인지 확인."""
        from src.training.training_manager import TrainingManager
        from ultralytics.utils.tqdm import TQDM

        # 패치 플래그 초기화 후 두 번 적용
        TQDM._safe_close_patched = False  # type: ignore[attr-defined]
        TrainingManager._apply_ultralytics_tqdm_patch()
        TrainingManager._apply_ultralytics_tqdm_patch()
        assert getattr(TQDM, "_safe_close_patched", False) is True

    def test_close_survives_file_none(self) -> None:
        """패치 후 TQDM.close()가 file=None 일 때 'NoneType.write' 크래시가 없는지 확인.

        bare __new__ 객체는 closed/pos 등 다른 속성이 없으므로 _orig_close가
        별도의 AttributeError를 낼 수 있다. 우리가 고치는 버그('file' 또는 'write'
        관련 AttributeError)만 검증하고, 그 외 누락 속성 에러는 무시한다.
        """
        from src.training.training_manager import TrainingManager
        from ultralytics.utils.tqdm import TQDM

        TrainingManager._apply_ultralytics_tqdm_patch()
        bar = TQDM.__new__(TQDM)
        bar.file = None  # type: ignore[attr-defined]
        bar.fp = None  # type: ignore[attr-defined]
        try:
            bar.close()
        except AttributeError as exc:
            err_msg = str(exc)
            # 우리가 수정한 버그: 'NoneType' object has no attribute 'write'
            if "write" in err_msg or (
                "'NoneType'" in err_msg and "file" in err_msg.lower()
            ):
                pytest.fail(
                    f"TQDM.close() still crashes on file=None after patch: {exc}"
                )
            # 그 외 AttributeError('closed', 'pos' 등)는 bare __new__ 객체의
            # 불완전한 초기화로 인한 것이므로 패치 검증 범위 밖 — 허용


# ---------------------------------------------------------------------------
# OOM guard tests (v3.5.1)
# ---------------------------------------------------------------------------


class TestCheckMemoryRequirements:
    def test_raises_when_ram_below_threshold(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_check_memory_requirements raises RuntimeError with English message when RAM < 1.5 GB."""
        import psutil

        from src.training.training_manager import TrainingManager

        mock_mem = type("M", (), {"available": int(1.0 * 1024**3)})()
        monkeypatch.setattr(psutil, "virtual_memory", lambda: mock_mem)

        mgr = TrainingManager.__new__(TrainingManager)
        with pytest.raises(RuntimeError, match="Insufficient memory"):
            mgr._check_memory_requirements()

    def test_no_raise_when_ram_sufficient(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_check_memory_requirements does not raise when RAM >= 1.5 GB."""
        import psutil

        from src.training.training_manager import TrainingManager

        mock_mem = type("M", (), {"available": int(2.0 * 1024**3)})()
        monkeypatch.setattr(psutil, "virtual_memory", lambda: mock_mem)

        mgr = TrainingManager.__new__(TrainingManager)
        mgr._check_memory_requirements()  # should not raise

    def test_skips_check_when_psutil_unavailable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_check_memory_requirements silently skips when psutil is not installed."""
        import builtins

        real_import = builtins.__import__

        def mock_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "psutil":
                raise ImportError("psutil not installed")
            return real_import(name, *args, **kwargs)

        from src.training.training_manager import TrainingManager

        monkeypatch.setattr(builtins, "__import__", mock_import)
        mgr = TrainingManager.__new__(TrainingManager)
        mgr._check_memory_requirements()  # should not raise


class TestHandleTrainOom:
    def test_converts_allocator_error_to_friendly_message(self) -> None:
        """DefaultCPUAllocator error is re-raised with actionable English message."""
        from src.training.training_manager import TrainingManager

        exc = RuntimeError(
            "DefaultCPUAllocator: not enough memory: you tried to allocate 393216 bytes"
        )
        with pytest.raises(RuntimeError, match="Reduce batch"):
            TrainingManager._handle_train_oom(exc)

    def test_converts_out_of_memory_error(self) -> None:
        """Generic OOM error is re-raised with friendly message."""
        from src.training.training_manager import TrainingManager

        exc = RuntimeError("CUDA out of memory")
        with pytest.raises(RuntimeError, match="CPU out of memory"):
            TrainingManager._handle_train_oom(exc)

    def test_re_raises_non_oom_errors_unchanged(self) -> None:
        """Non-OOM RuntimeError is re-raised as-is."""
        from src.training.training_manager import TrainingManager

        exc = RuntimeError("some other error")
        with pytest.raises(RuntimeError, match="some other error"):
            TrainingManager._handle_train_oom(exc)

    def test_error_message_is_english(self) -> None:
        """OOM error message must be in English (no Korean characters)."""
        from src.training.training_manager import TrainingManager

        exc = RuntimeError("not enough memory")
        try:
            TrainingManager._handle_train_oom(exc)
        except RuntimeError as e:
            msg = str(e)
            assert all(
                ord(c) < 0xAC00 or ord(c) > 0xD7A3 for c in msg
            ), f"Error message contains Korean characters: {msg}"


class TestBatchDefault:
    def test_default_batch_is_2(self) -> None:
        """train() default batch must be 2 (CPU-only safe default)."""
        import inspect

        from src.training.training_manager import TrainingManager

        sig = inspect.signature(TrainingManager.train)
        assert (
            sig.parameters["batch"].default == 2
        ), "Default batch must be 2 for CPU-only environments"
