"""
Unit tests for src/training/training_manager.py.

Covers:
- FileNotFoundError when start weights file is missing
- YOLO_OFFLINE environment variable is set before training starts
- FileNotFoundError when dataset.yaml is missing
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
    """Write a minimal dataset.yaml so the file-check passes."""
    path.write_text(
        "path: .\ntrain: images\nval: images\nnc: 1\nnames: ['button']\n",
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
