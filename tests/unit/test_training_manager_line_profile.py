from __future__ import annotations

import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _write_dataset(tmp_path: Path) -> Path:
    images_dir = tmp_path / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    (images_dir / "sample.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    yaml_path = tmp_path / "dataset.yaml"
    yaml_path.write_text(
        f"path: {str(tmp_path).replace(chr(92), '/')}\n"
        "train: images\nval: images\nnc: 1\nnames: ['button']\n",
        encoding="utf-8",
    )
    return yaml_path


def _write_weights(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"weights")


def test_training_manager_passes_line_image_augmentations(tmp_path: Path) -> None:
    from src.training.training_manager import TrainingManager

    yaml_path = _write_dataset(tmp_path)
    weights = tmp_path / "yolo26x.pt"
    _write_weights(weights)

    tm = TrainingManager(base_model=str(weights), target_weights=tmp_path / "out.pt")

    captured: dict[str, object] = {}

    class _Model:
        def add_callback(self, *args, **kwargs):  # noqa: ANN002,ANN003
            return None

        def train(self, **kwargs):  # noqa: ANN003
            captured.update(kwargs)
            result = types.SimpleNamespace(save_dir=tmp_path / "runs")
            (tmp_path / "runs" / "weights").mkdir(parents=True, exist_ok=True)
            (tmp_path / "runs" / "weights" / "best.pt").write_bytes(b"best")
            return result

    with patch("ultralytics.YOLO", return_value=_Model()):
        with patch.object(
            TrainingManager, "_clean_stale_caches", autospec=True, return_value=None
        ):
            with patch.object(
                TrainingManager, "_check_memory_requirements", autospec=True, return_value=None
            ):
                with patch.object(
                    TrainingManager, "_apply_ultralytics_tqdm_patch",
                    autospec=True,
                    return_value=None,
                ):
                    with patch.object(
                        TrainingManager, "_resolve_device", autospec=True, return_value="cpu"
                    ):
                        tm.train(dataset_yaml=yaml_path, epochs=3, batch=1)

    assert captured["hsv_h"] == 0.0
    assert captured["mosaic"] == 0.0
    assert captured["fliplr"] == 0.0
    assert captured["close_mosaic"] == 0


def test_suggest_training_profile_uses_longer_runs_for_small_gpu_sets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src import config_loader

    monkeypatch.setattr(
        config_loader,
        "detect_local_accelerator",
        lambda: {
            "device": 0,
            "name": "RTX 4090",
            "memory_gb": 20.0,
            "gpu_present": True,
            "cuda_usable": True,
        },
    )

    profile = config_loader.suggest_training_profile(image_count=30)
    assert profile["epochs"] >= 60
    assert profile["batch"] >= 8
    assert profile["image_size"] == 640
