from __future__ import annotations

from pathlib import Path

import pytest

import src.model_artifacts as model_artifacts
from src.model_artifacts import (
    CLOUD_PRETRAIN_MODEL_NAME,
    COCO_BASE_MODEL_NAME,
    LEGACY_CLOUD_PRETRAIN_MODEL_NAME,
    LOCAL_PRETRAIN_MODEL_NAME,
    promote_latest_finetune_checkpoint,
    resolve_finetune_seed_model,
    resolve_latest_finetune_checkpoint,
    resolve_model_artifact,
    resolve_runtime_model,
)


def _fake_resolve_app_path(root: Path):
    def _resolver(path: str | Path) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        return root / candidate

    return _resolver


def _write_viable_model(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"0" * (model_artifacts.MIN_VIABLE_MODEL_BYTES + 128))


def test_model_name_constants_are_canonical() -> None:
    assert CLOUD_PRETRAIN_MODEL_NAME == "yolo26x_pretrain.pt"
    assert LEGACY_CLOUD_PRETRAIN_MODEL_NAME == "yolo26x_pretrained.pt"
    assert COCO_BASE_MODEL_NAME == "yolo26x.pt"
    assert LOCAL_PRETRAIN_MODEL_NAME == "yolo26x_local_pretrained.pt"


def test_resolve_model_artifact_prefers_canonical_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        model_artifacts, "resolve_app_path", _fake_resolve_app_path(tmp_path)
    )

    canonical = tmp_path / "assets/models/yolo26x_pretrain.pt"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("canonical", encoding="utf-8")
    legacy = tmp_path / "assets/models/yolo26x_pretrained.pt"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text("legacy", encoding="utf-8")

    resolved = resolve_model_artifact(
        "assets/models/yolo26x_pretrain.pt",
        "assets/models/yolo26x_pretrained.pt",
    )

    assert resolved == canonical


def test_resolve_model_artifact_falls_back_to_legacy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        model_artifacts, "resolve_app_path", _fake_resolve_app_path(tmp_path)
    )

    legacy = tmp_path / "assets/models/yolo26x_pretrained.pt"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("legacy", encoding="utf-8")

    resolved = resolve_model_artifact(
        "assets/models/yolo26x_pretrain.pt",
        "assets/models/yolo26x_pretrained.pt",
    )

    assert resolved == legacy


def test_resolve_finetune_seed_model_prefers_local_pretrained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        model_artifacts, "resolve_app_path", _fake_resolve_app_path(tmp_path)
    )

    local_seed = tmp_path / "assets/models/yolo26x_local_pretrained.pt"
    _write_viable_model(local_seed)
    archived_cloud = tmp_path / "assets/models/yolo26x_pretrain.pt"
    _write_viable_model(archived_cloud)

    resolved = resolve_finetune_seed_model()

    assert resolved == local_seed


def test_resolve_runtime_model_upgrades_legacy_coco_config_to_local_pretrained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        model_artifacts, "resolve_app_path", _fake_resolve_app_path(tmp_path)
    )

    coco = tmp_path / "assets/models/yolo26x.pt"
    _write_viable_model(coco)
    local_seed = tmp_path / "assets/models/yolo26x_local_pretrained.pt"
    _write_viable_model(local_seed)

    resolved = resolve_runtime_model("assets/models/yolo26x.pt")

    assert resolved == local_seed


def test_resolve_runtime_model_honors_explicit_non_coco_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        model_artifacts, "resolve_app_path", _fake_resolve_app_path(tmp_path)
    )

    explicit = tmp_path / "assets/models/custom-best.pt"
    _write_viable_model(explicit)
    local_seed = tmp_path / "assets/models/yolo26x_local_pretrained.pt"
    _write_viable_model(local_seed)

    resolved = resolve_runtime_model("assets/models/custom-best.pt")

    assert resolved == explicit


def test_resolve_runtime_model_skips_tiny_placeholder_local_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        model_artifacts, "resolve_app_path", _fake_resolve_app_path(tmp_path)
    )

    local_seed = tmp_path / "assets/models/yolo26x_local_pretrained.pt"
    local_seed.parent.mkdir(parents=True, exist_ok=True)
    local_seed.write_bytes(b"fake_weights")
    archived = tmp_path / "assets/models/yolo26x_pretrained.pt"
    _write_viable_model(archived)

    resolved = resolve_runtime_model("assets/models/yolo26x_local_pretrained.pt")

    assert resolved == archived


def test_resolve_latest_finetune_checkpoint_prefers_runs_detect_train_weights(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        model_artifacts, "resolve_app_path", _fake_resolve_app_path(tmp_path)
    )

    latest = tmp_path / "runs/detect/train/weights/best.pt"
    _write_viable_model(latest)

    resolved = resolve_latest_finetune_checkpoint()

    assert resolved == latest


def test_promote_latest_finetune_checkpoint_overwrites_placeholder_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        model_artifacts, "resolve_app_path", _fake_resolve_app_path(tmp_path)
    )

    latest = tmp_path / "runs/detect/train/weights/best.pt"
    _write_viable_model(latest)
    target = tmp_path / "assets/models/yolo26x_local_pretrained.pt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"fake_weights")

    promoted = promote_latest_finetune_checkpoint()

    assert promoted == target
    assert target.read_bytes() == latest.read_bytes()
