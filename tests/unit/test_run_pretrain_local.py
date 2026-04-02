from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock
from types import SimpleNamespace

import pytest

import scripts.run_pretrain_local as run_pretrain_local


def test_run_pretrain_local_dry_run_skips_training(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path / "pretrain_data"
    (data_root / "train" / "images").mkdir(parents=True, exist_ok=True)
    (data_root / "val" / "images").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        run_pretrain_local,
        "resolve_pretrain_data_root",
        lambda explicit_root=None: data_root,
    )
    monkeypatch.setattr(run_pretrain_local, "count_prepared_images", lambda root: 128)
    monkeypatch.setattr(
        run_pretrain_local,
        "suggest_pretrain_profile",
        lambda image_count=None, explicit_device=None: SimpleNamespace(
            device="cpu",
            epochs=6,
            batch=8,
            image_size=320,
            workers=4,
        ),
    )
    monkeypatch.setattr(
        run_pretrain_local,
        "detect_pretrain_hardware",
        lambda: {
            "device": "cpu",
            "name": None,
            "memory_gb": None,
            "gpu_present": False,
            "cuda_usable": False,
            "logical_cores": 48,
            "physical_cores": 24,
            "ram_gb": 128.0,
        },
    )

    train_mock = Mock(return_value=Path("unused.pt"))
    monkeypatch.setattr(
        run_pretrain_local.CompactPretrainPipeline,
        "train_and_save",
        train_mock,
    )
    monkeypatch.setattr(sys, "argv", ["run_pretrain_local.py", "--dry-run", "--epochs", "9", "--batch", "12"])

    run_pretrain_local.main()

    train_mock.assert_not_called()
