"""Canonical model artifact names and resolution helpers.

Fine-tuning is the active training path. Pretrain generation is archived for
legacy/manual rebuilds only, but the resulting checkpoints are still valid
seed models for Tab 7.
"""

from __future__ import annotations

from pathlib import Path

from src.config_loader import resolve_app_path

MODEL_ASSETS_DIR = Path("assets/models")

COCO_BASE_MODEL_NAME = "yolo26x.pt"
CLOUD_PRETRAIN_MODEL_NAME = "yolo26x_pretrain.pt"
LEGACY_CLOUD_PRETRAIN_MODEL_NAME = "yolo26x_pretrained.pt"
LOCAL_PRETRAIN_MODEL_NAME = "yolo26x_local_pretrained.pt"


def model_asset_path(name: str | Path) -> Path:
    """Return the resolved path for a model asset.

    Relative model names are interpreted inside ``assets/models``. Absolute
    paths are returned as-is after runtime-aware resolution.
    """

    candidate = Path(name)
    if candidate.is_absolute():
        return candidate

    if len(candidate.parts) >= 2 and candidate.parts[0] == "assets" and candidate.parts[1] == "models":
        return resolve_app_path(candidate)

    return resolve_app_path(MODEL_ASSETS_DIR / candidate.name)


def resolve_model_artifact(*candidates: str | Path) -> Path:
    """Return the first existing model artifact among the provided candidates.

    The first candidate is treated as the canonical name. Later candidates act
    as compatibility fallbacks. If none exist yet, the canonical candidate is
    returned so callers can still create the file there.
    """

    if not candidates:
        raise ValueError("At least one model candidate must be provided")

    resolved_candidates = [model_asset_path(candidate) for candidate in candidates]
    for candidate in resolved_candidates:
        if candidate.exists():
            return candidate
    return resolved_candidates[0]


def resolve_coco_base_model() -> Path:
    """Resolve the shipped COCO base model path."""

    return resolve_model_artifact(COCO_BASE_MODEL_NAME)


def resolve_cloud_pretrain_model() -> Path:
    """Resolve the cloud/GitHub pretrain checkpoint path."""

    return resolve_model_artifact(
        CLOUD_PRETRAIN_MODEL_NAME,
        LEGACY_CLOUD_PRETRAIN_MODEL_NAME,
    )


def resolve_local_pretrained_model() -> Path:
    """Resolve the offline local-pretrain output path."""

    return resolve_model_artifact(LOCAL_PRETRAIN_MODEL_NAME)


def resolve_finetune_seed_model() -> Path:
    """Resolve the preferred seed model for active fine-tuning work.

    Preference order:
    1. ``yolo26x_local_pretrained.pt``: completed offline/local pretrain result
    2. ``yolo26x_pretrain.pt``: archived cloud pretrain checkpoint
    3. ``yolo26x_pretrained.pt``: legacy alias during migration
    4. ``yolo26x.pt``: plain COCO fallback
    """

    return resolve_model_artifact(
        LOCAL_PRETRAIN_MODEL_NAME,
        CLOUD_PRETRAIN_MODEL_NAME,
        LEGACY_CLOUD_PRETRAIN_MODEL_NAME,
        COCO_BASE_MODEL_NAME,
    )
