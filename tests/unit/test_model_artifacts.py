from __future__ import annotations

from pathlib import Path

import pytest

import src.model_artifacts as model_artifacts
from src.model_artifacts import (
    CLOUD_PRETRAIN_MODEL_NAME,
    COCO_BASE_MODEL_NAME,
    LEGACY_CLOUD_PRETRAIN_MODEL_NAME,
    LOCAL_PRETRAIN_MODEL_NAME,
    resolve_model_artifact,
)


def _fake_resolve_app_path(root: Path):
    def _resolver(path: str | Path) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        return root / candidate

    return _resolver


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

