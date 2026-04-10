"""Canonical model artifact names and resolution helpers.

Fine-tuning is the active training path. Pretrain generation is archived for
legacy/manual rebuilds only, but the resulting checkpoints are still valid
seed models for Tab 7.
"""

from __future__ import annotations

from pathlib import Path
import shutil

from src.config_loader import resolve_app_path

MODEL_ASSETS_DIR = Path("assets/models")
MIN_VIABLE_MODEL_BYTES = 1024 * 1024

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


def resolve_latest_finetune_checkpoint() -> Path | None:
    """Return the newest viable fine-tuning checkpoint from Ultralytics runs/.

    Primary expected location is ``runs/detect/train/weights/best.pt``.
    A compatibility fallback also checks ``runs/detect/train/best.pt`` and then
    scans the whole ``runs/`` tree for viable ``best.pt`` artifacts.
    """

    preferred_candidates = (
        Path("runs/detect/train/weights/best.pt"),
        Path("runs/detect/train/best.pt"),
    )
    for candidate in preferred_candidates:
        resolved = resolve_app_path(candidate)
        if is_viable_model_artifact(resolved):
            return resolved

    runs_root = resolve_app_path("runs")
    if not runs_root.exists():
        return None

    viable: list[Path] = []
    for candidate in runs_root.rglob("best.pt"):
        if is_viable_model_artifact(candidate):
            viable.append(candidate)
    if not viable:
        return None
    return max(viable, key=lambda path: path.stat().st_mtime)


def promote_latest_finetune_checkpoint(force: bool = False) -> Path | None:
    """Promote the latest viable fine-tuning ``best.pt`` into the runtime slot.

    Returns the target ``assets/models/yolo26x_local_pretrained.pt`` when a
    promotion happened, otherwise ``None``.
    """

    source = resolve_latest_finetune_checkpoint()
    if source is None:
        return None

    target = resolve_local_pretrained_model()
    target.parent.mkdir(parents=True, exist_ok=True)

    if not force and target.exists():
        try:
            target_stat = target.stat()
            source_stat = source.stat()
            if (
                target_stat.st_size >= MIN_VIABLE_MODEL_BYTES
                and target_stat.st_mtime >= source_stat.st_mtime
            ):
                return None
        except OSError:
            pass

    shutil.copy2(source, target)
    return target


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


def is_viable_model_artifact(candidate: str | Path) -> bool:
    """Return True when the candidate looks like a real YOLO checkpoint.

    Release/app bundles have historically shipped tiny placeholder files such as
    ``fake_weights``. Those files satisfy ``exists()`` but are not usable by live
    SOP detection. A practical offline guard is enough here: real YOLO weights are
    megabytes large, so anything below 1 MiB is treated as non-viable.
    """

    path = model_asset_path(candidate)
    try:
        return path.is_file() and path.stat().st_size >= MIN_VIABLE_MODEL_BYTES
    except OSError:
        return False


def resolve_runtime_model(configured: str | Path | None = None) -> Path:
    """Resolve the model path that live SOP detection should load.

    Runtime rule for v5.0.0:
    1. If the config explicitly points to a non-COCO model and it exists, honor it.
    2. If the config still points at the legacy COCO base path, auto-upgrade to the
       best available fine-tuned/pretrained seed when one exists.
    3. Fall back to the fine-tune seed chain, then finally the COCO base model.
    """

    promote_latest_finetune_checkpoint()

    if configured:
        configured_path = model_asset_path(configured)
        configured_name = Path(configured).name
        if (
            configured_name != COCO_BASE_MODEL_NAME
            and is_viable_model_artifact(configured_path)
        ):
            return configured_path

    preferred_candidates = (
        LOCAL_PRETRAIN_MODEL_NAME,
        CLOUD_PRETRAIN_MODEL_NAME,
        LEGACY_CLOUD_PRETRAIN_MODEL_NAME,
        COCO_BASE_MODEL_NAME,
    )
    for candidate in preferred_candidates:
        if is_viable_model_artifact(candidate):
            return model_asset_path(candidate)

    if configured:
        return model_asset_path(configured)
    return resolve_coco_base_model()
