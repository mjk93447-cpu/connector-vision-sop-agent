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


def test_run_pretrain_local_shows_clear_error_when_pipeline_import_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        run_pretrain_local,
        "_PIPELINE_IMPORT_ERROR",
        ImportError("No module named 'numpy._core._exceptions'"),
    )
    monkeypatch.setattr(run_pretrain_local, "CompactPretrainPipeline", None)
    monkeypatch.setattr(run_pretrain_local, "CompactPretrainConfig", None)
    monkeypatch.setattr(sys, "argv", ["run_pretrain_local.py", "--dry-run"])

    with pytest.raises(SystemExit) as exc_info:
        run_pretrain_local.main()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Failed to load the compact pretrain pipeline" in captured.out
    assert "numpy/cv2/dataset bundle" in captured.out


def test_run_pretrain_local_skip_bundle_prep_does_not_build_dataset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path / "pretrain_data"
    data_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        run_pretrain_local,
        "resolve_pretrain_data_root",
        lambda explicit_root=None: data_root,
    )
    monkeypatch.setattr(run_pretrain_local, "count_prepared_images", lambda root: 0)
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

    build_mock = Mock()
    train_mock = Mock(return_value=Path("unused.pt"))
    monkeypatch.setattr(run_pretrain_local.CompactPretrainPipeline, "build_bundle", build_mock)
    monkeypatch.setattr(run_pretrain_local.CompactPretrainPipeline, "train_and_save", train_mock)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_pretrain_local.py", "--dry-run", "--skip-bundle-prep", "--epochs", "9", "--batch", "12"],
    )

    run_pretrain_local.main()

    build_mock.assert_not_called()
    train_mock.assert_not_called()
