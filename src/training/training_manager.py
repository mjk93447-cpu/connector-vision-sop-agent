"""
YOLO fine-tuning manager for OLED line PC.

Wraps ultralytics YOLO.train() and saves the best weights to
``assets/models/yolo26x_local_pretrained.pt`` upon completion.

Usage
-----
  tm = TrainingManager()
  output_path = tm.train(
      dataset_yaml="training_data/dataset.yaml",
      base_model="yolo26x_local_pretrained.pt",
      epochs=10,
      image_size=640,
      progress_cb=lambda epoch, total: print(f"{epoch}/{total}"),
  )
  # output_path == "assets/models/yolo26x_local_pretrained.pt"
"""

from __future__ import annotations

import io
import os
import shutil
import sys
from pathlib import Path
from typing import Callable, Optional

from src.config_loader import detect_local_accelerator, get_base_dir
from src.model_artifacts import (
    LOCAL_PRETRAIN_MODEL_NAME,
    is_viable_model_artifact,
    promote_latest_finetune_checkpoint,
    resolve_finetune_seed_model,
    resolve_model_artifact,
    resolve_runtime_model,
)
from src.runtime_compat import ensure_numpy_compatibility, ensure_torch_cuda_wheel

_DEFAULT_BASE_MODEL = LOCAL_PRETRAIN_MODEL_NAME
_TARGET_WEIGHTS = get_base_dir() / f"assets/models/{LOCAL_PRETRAIN_MODEL_NAME}"


class _TeeWriter:
    """Write to two streams simultaneously.

    Primary stream  — the original sys.stdout (console in dev, connector_agent.log
                      in PyInstaller console=False EXE after main.py's startup guard).
    Secondary stream — a dedicated ``training.log`` file that the GUI can read and
                       display after training completes.

    Handles a None primary gracefully (EXE cold-start edge case) so the class
    never raises AttributeError regardless of environment.
    This replaces the previous io.StringIO() hack which silently discarded all
    ultralytics TQDM / training output.
    """

    def __init__(self, primary: object, secondary: object) -> None:
        self._primary = primary
        self._secondary = secondary

    def write(self, s: str) -> int:
        count = 0
        for stream in (self._primary, self._secondary):
            if stream is not None:
                try:
                    n = stream.write(s)
                    if n:
                        count = max(count, int(n))
                except Exception:  # noqa: BLE001
                    pass
        return count

    def flush(self) -> None:
        for stream in (self._primary, self._secondary):
            if stream is not None:
                try:
                    stream.flush()
                except Exception:  # noqa: BLE001
                    pass

    def fileno(self) -> int:
        for stream in (self._primary, self._secondary):
            if stream is not None:
                try:
                    return stream.fileno()  # type: ignore[union-attr]
                except Exception:  # noqa: BLE001
                    pass
        raise io.UnsupportedOperation("fileno")


def _to_float(value: object) -> Optional[float]:
    """Best-effort conversion of torch / numpy / scalar values to float."""
    if value is None:
        return None
    try:
        if isinstance(value, (list, tuple)):
            values = [_to_float(v) for v in value]
            numbers = [v for v in values if v is not None]
            if not numbers:
                return None
            return float(sum(numbers) / len(numbers))
        if hasattr(value, "detach"):
            value = value.detach()  # type: ignore[assignment]
        if hasattr(value, "cpu"):
            value = value.cpu()  # type: ignore[assignment]
        if hasattr(value, "item"):
            return float(value.item())  # type: ignore[call-arg]
        return float(value)  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001
        return None


class TrainingManager:
    """Wraps ultralytics YOLO fine-tuning for local offline use."""

    def __init__(
        self,
        base_model: str = _DEFAULT_BASE_MODEL,
        target_weights: str | Path = _TARGET_WEIGHTS,
    ) -> None:
        self.base_model = base_model
        self.target_weights = Path(target_weights)

    def train(
        self,
        dataset_yaml: str | Path,
        epochs: int = 10,
        image_size: int = 640,
        batch: int = 2,  # CPU-only default: smaller batch to avoid OOM
        base_model: Optional[str] = None,
        progress_cb: Optional[Callable[[int, int], None]] = None,
        metrics_cb: Optional[Callable[[dict], None]] = None,
    ) -> Path:
        # last_training_log is set inside _run_training(); initialise here so
        # callers can always inspect it even if training raises an exception.
        self.last_training_log: Optional[Path] = None
        """Fine-tune the model and save the best weights.

        Parameters
        ----------
        dataset_yaml: Path to ``dataset.yaml`` produced by DatasetManager.
        epochs:       Number of training epochs.
        image_size:   Input resolution for YOLO.
        batch:        Batch size (use 2-4 for CPU-only line PC).
        base_model:   Override base model path (takes precedence over self.base_model).
        progress_cb:  Optional callback ``(epoch, total_epochs)`` for UI progress.
        metrics_cb:   Optional callback with per-epoch metrics after validation.

        Returns
        -------
        Path to the saved weights file (active runtime model path).

        Raises
        ------
        FileNotFoundError:  dataset.yaml or start weights file not found.
        ValueError:         No training images found in dataset.
        """
        # ------------------------------------------------------------------ #
        # Complete offline prevention — block ALL network calls from          #
        # ultralytics, W&B, Comet, ClearML, neptune, and PyTorch Hub.        #
        # This is an offline Windows program; no telemetry/download allowed.  #
        # ------------------------------------------------------------------ #
        os.environ["YOLO_OFFLINE"] = "1"
        os.environ["ULTRALYTICS_OFFLINE"] = "1"  # newer ultralytics guard
        os.environ.setdefault("WANDB_DISABLED", "true")  # Weights & Biases off
        os.environ.setdefault("WANDB_MODE", "disabled")
        os.environ.setdefault("COMET_MODE", "disabled")  # Comet.ml off
        os.environ.setdefault("CLEARML_LOG_MODEL", "false")  # ClearML off
        os.environ.setdefault("NEPTUNE_MODE", "offline")  # Neptune off
        # Prevent PyTorch Hub from downloading backbone weights
        os.environ.setdefault("TORCH_HOME", str(Path.home() / ".cache" / "torch"))

        try:
            from ultralytics.utils import SETTINGS  # noqa: PLC0415

            SETTINGS.update({"sync": False, "api_key": ""})
        except Exception:  # noqa: BLE001
            pass  # ultralytics not installed — proceed; YOLO import will fail later

        ensure_numpy_compatibility()

        from ultralytics import YOLO  # noqa: PLC0415 — heavy import, defer

        dataset_yaml = Path(dataset_yaml)
        if not dataset_yaml.exists():
            raise FileNotFoundError(f"dataset.yaml not found: {dataset_yaml}")

        # ------------------------------------------------------------------ #
        # Pre-validate: count training images BEFORE calling model.train().   #
        # ultralytics gives a cryptic "NoneType has no attribute 'write'"     #
        # when no images are found (im_files=[]).  We detect this early and   #
        # raise a clear, actionable error.                                    #
        # ------------------------------------------------------------------ #
        img_count = self._count_training_images(dataset_yaml)
        if img_count == 0:
            raise ValueError(
                "No training images found in dataset.\n"
                "Please annotate and save at least one image in the Training tab\n"
                "before starting training.\n"
                f"Dataset config: {dataset_yaml}"
            )

        # Determine starting weights.
        # Priority:
        # 1. explicit UI/base_model override
        # 2. existing target weights (resume fine-tuning)
        # 3. default fine-tune seed chain
        if base_model:
            start_weights = resolve_model_artifact(base_model)
        elif is_viable_model_artifact(self.target_weights):
            start_weights = self.target_weights
        else:
            start_weights = resolve_runtime_model(
                self.base_model or resolve_finetune_seed_model()
            )

        # ------------------------------------------------------------------ #
        # Clean stale ultralytics label-cache files.                        #
        # Leftover *.cache.npy files from an interrupted previous run cause #
        # the infamous 'NoneType' object has no attribute 'write' crash on  #
        # the cache-rebuild path.  Deleting them here ensures a clean start #
        # and reproduces the "first run always works" behaviour the user     #
        # already observes.                                                  #
        # ------------------------------------------------------------------ #
        self._clean_stale_caches(dataset_yaml)

        # Guard: sufficient RAM must be available for YOLO26x model init
        self._check_memory_requirements()

        # Guard: model file must exist — never auto-download from GitHub
        if not Path(start_weights).exists():
            raise FileNotFoundError(
                f"Model file not found: {start_weights}\n"
                "Place yolo26x_local_pretrained.pt, yolo26x_pretrain.pt, or yolo26x.pt "
                "in assets/models/ before training."
            )

        accelerator = self._resolve_accelerator()
        model = YOLO(str(start_weights))
        device = self._resolve_device(accelerator)

        # Patch the on_train_epoch_end callback to forward progress.
        if progress_cb is not None:

            def _epoch_cb(trainer: object) -> None:  # noqa: ANN001
                epoch = getattr(trainer, "epoch", 0) + 1
                total = getattr(trainer, "epochs", epochs)
                progress_cb(epoch, total)

            model.add_callback("on_train_epoch_end", _epoch_cb)

        if metrics_cb is not None:

            def _metrics_cb(trainer: object) -> None:  # noqa: ANN001
                metrics = self._extract_epoch_metrics(trainer)
                if metrics is not None:
                    metrics_cb(metrics)

            model.add_callback("on_fit_epoch_end", _metrics_cb)

        # ------------------------------------------------------------------ #
        # Tee stdout/stderr to a dedicated training.log file.               #
        #                                                                    #
        # Root cause of AttributeError 'NoneType.write':                    #
        #   PyInstaller console=False → sys.stdout = None.                  #
        #   ultralytics TQDM: self.file = file or sys.stdout = None.        #
        #   TQDM.close() calls self.file.write("\n") → AttributeError.      #
        #                                                                    #
        # Two-layer fix:                                                     #
        #   Layer 1 (app-level): main.py redirects sys.stdout to            #
        #     connector_agent.log at EXE startup (permanent, whole app).    #
        #   Layer 2 (training-level, here): _TeeWriter routes every write   #
        #     to BOTH the current sys.stdout AND a training-specific        #
        #     training.log file.                                             #
        #     • If sys.stdout is still None (edge case), _TeeWriter skips   #
        #       the None stream and writes only to training.log — no crash. #
        #     • training.log preserves the full ultralytics output           #
        #       (loss curves, mAP, TQDM lines) for the GUI to display.      #
        #                                                                    #
        # Previous approach (io.StringIO) silently discarded all output.    #
        # ------------------------------------------------------------------ #
        training_log = dataset_yaml.parent / "training.log"
        self.last_training_log = training_log

        _orig_stdout = sys.stdout
        _orig_stderr = sys.stderr
        _log_file = training_log.open("w", encoding="utf-8", buffering=1)
        try:
            self._apply_ultralytics_tqdm_patch()  # ① patch first
            sys.stdout = _TeeWriter(sys.stdout, _log_file)  # ② then wrap
            sys.stderr = _TeeWriter(sys.stderr, _log_file)
            try:
                results = model.train(
                    data=str(dataset_yaml),
                    epochs=epochs,
                    imgsz=image_size,
                    batch=batch,
                    device=device,
                    workers=0,  # single-process DataLoader (Windows multiprocessing fix)
                    exist_ok=True,  # overwrite previous run directory
                    rect=False,  # disable rectangular training
                    hsv_h=0.0,
                    hsv_s=0.0,
                    hsv_v=0.12,
                    degrees=0.0,
                    translate=0.04,
                    scale=0.08,
                    shear=0.0,
                    perspective=0.0,
                    flipud=0.0,
                    fliplr=0.0,
                    mosaic=0.0,
                    mixup=0.0,
                    copy_paste=0.0,
                    erasing=0.0,
                    close_mosaic=0,
                    patience=max(10, min(epochs // 2, 20)),
                    pretrained=True,
                    verbose=True,
                    plots=False,
                )
            except RuntimeError as _oom_exc:
                self._handle_train_oom(_oom_exc)
        finally:
            sys.stdout = _orig_stdout
            sys.stderr = _orig_stderr
            _log_file.close()

        # Copy best weights to target location.
        best_pt = self._find_best_weights(results)
        if best_pt and best_pt.exists():
            self.target_weights.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(best_pt, self.target_weights)
        promote_latest_finetune_checkpoint(force=True)

        return self.target_weights

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _count_training_images(dataset_yaml: Path) -> int:
        """Count images referenced by ``dataset.yaml``'s ``train:`` field.

        Returns the total number of image files found, or ``-1`` if the yaml
        cannot be parsed (caller treats -1 as "unknown — proceed anyway").

        Supports both the flat string form (``train: images``) and the list
        form (``train: [images/button, images/icon]``).
        """
        try:
            import yaml as _yaml  # noqa: PLC0415

            with open(dataset_yaml, encoding="utf-8") as f:
                data = _yaml.safe_load(f)

            # Resolve root (forward-slash paths are safe on both platforms)
            root = Path(
                str(data.get("path", str(dataset_yaml.parent))).replace("/", os.sep)
            )
            train_entries = data.get("train", "images")
            if isinstance(train_entries, str):
                train_entries = [train_entries]

            _IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}
            count = 0
            for entry in train_entries:
                p = root / Path(entry)
                if p.is_dir():
                    count += sum(
                        1 for f in p.rglob("*") if f.suffix.lower() in _IMG_EXTS
                    )
                elif p.is_file() and p.suffix.lower() in _IMG_EXTS:
                    count += 1
            return count
        except Exception:  # noqa: BLE001
            return -1  # unknown — let ultralytics decide

    @staticmethod
    def _extract_epoch_metrics(trainer: object) -> Optional[dict]:
        """Normalize Ultralytics trainer metrics into a UI-friendly payload."""
        metrics = getattr(trainer, "metrics", None) or {}
        if not isinstance(metrics, dict):
            try:
                metrics = dict(metrics)
            except Exception:  # noqa: BLE001
                metrics = {}

        epoch = getattr(trainer, "epoch", None)
        total_epochs = getattr(trainer, "epochs", None)
        fitness = _to_float(getattr(trainer, "fitness", None))
        loss = _to_float(getattr(trainer, "tloss", None))

        def _find_metric(*needles: str) -> Optional[float]:
            for key, value in metrics.items():
                key_l = str(key).lower().replace(" ", "")
                if "map50" in needles and (
                    "map50-95" in key_l
                    or "map5095" in key_l
                    or "map50_95" in key_l
                ):
                    continue
                if all(needle in key_l for needle in needles):
                    found = _to_float(value)
                    if found is not None:
                        return found
            return None

        map50 = _find_metric("map50")
        map50_95 = _find_metric("map50-95")
        if map50_95 is None:
            map50_95 = _find_metric("map5095")

        if map50 is None and map50_95 is None and fitness is None and loss is None:
            return None

        return {
            "epoch": epoch,
            "total_epochs": total_epochs,
            "fitness": fitness,
            "loss": loss,
            "map50": map50,
            "map50_95": map50_95,
            "raw_metrics": metrics,
        }

    @staticmethod
    def _clean_stale_caches(dataset_yaml: Path) -> None:
        """Delete stale ultralytics label-cache files before training.

        ultralytics stores per-split label caches as ``*.cache`` files
        adjacent to the ``labels/`` subdirectories (e.g.
        ``training_data/labels/image_source.cache``).  The save sequence is:

        1. ``np.save(str(cache_path), data)``  → creates ``*.cache.npy``
        2. ``cache_path.with_suffix(".cache.npy").rename(cache_path)``

        If a previous training run was **interrupted between steps 1 and 2**
        (common when the GUI is closed mid-training), the ``*.cache.npy`` file
        is left on disk but ``*.cache`` never appears.  On the next run:

        * ``load_dataset_cache_file("*.cache")``  → ``FileNotFoundError``
        * ``cache_labels(cache_path)`` tries to rebuild and re-save
        * ``Path("*.cache.npy").rename(cache_path)`` fails on Windows
          when destination already exists (Python < 3.9) or when the
          ``np.save()`` path resolves to ``None`` in some ultralytics builds
        * Result: ``'NoneType' object has no attribute 'write'``

        Pre-emptively deleting all ``*.cache`` and ``*.cache.npy`` files in
        ``<yaml_dir>/labels/`` before every training call guarantees a clean
        slate and reproduces the "first-run always works" behaviour.
        """
        labels_dir = dataset_yaml.parent / "labels"
        if not labels_dir.exists():
            return
        for pattern in ("*.cache", "*.cache.npy"):
            for stale in labels_dir.rglob(pattern):
                try:
                    stale.unlink()
                except OSError:
                    pass  # read-only or locked — skip silently

    @staticmethod
    def _apply_ultralytics_tqdm_patch() -> None:
        """ultralytics TQDM.close()의 file=None 크래시를 근본 수정.

        근본 원인 (2단계):
          1. ultralytics.utils.VERBOSE 전역이 False이면 TQDM(disable=True)로
             초기화되고 base tqdm이 self.file = None으로 설정한다.
          2. TQDM.close()가 self.file.write('\\n')을 호출할 때 AttributeError 발생.

        verbose=True를 model.train()에 전달해도 ultralytics.utils.VERBOSE 전역에
        propagate되지 않으므로 이 패치가 필요하다.

        이 메서드는:
          1. ultralytics.utils.VERBOSE = True 강제 설정 (disable=False 보장)
          2. TQDM.close()에 self.file is None 가드 추가 (2중 안전망)
        두 가지를 동시에 적용하여 완전한 근본 해결을 보장한다.
        """
        try:
            import ultralytics.utils as _ult_utils  # noqa: PLC0415

            _ult_utils.VERBOSE = True  # tqdm disable=False 강제

            from ultralytics.utils.tqdm import TQDM as _UltTQDM  # noqa: PLC0415

            if getattr(_UltTQDM, "_safe_close_patched", False):
                return  # 이미 패치됨 — idempotent

            _orig_close = _UltTQDM.close

            def _safe_close(self: object) -> None:  # noqa: ANN001
                if getattr(self, "file", None) is None:
                    import io as _io  # noqa: PLC0415
                    import sys as _sys  # noqa: PLC0415 — re-read at call time (TeeWriter may be active)

                    self.file = _sys.stderr or _sys.stdout or _io.StringIO()  # type: ignore[union-attr]
                _orig_close(self)  # type: ignore[call-arg]

            _UltTQDM.close = _safe_close  # type: ignore[method-assign]
            _UltTQDM._safe_close_patched = True  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass  # ultralytics 없거나 API 변경 시 무시 (방어적)

    _MIN_FREE_GB: float = 1.5

    def _check_memory_requirements(self) -> None:
        """Raise early with a clear English message when RAM is insufficient."""
        try:
            import psutil  # noqa: PLC0415

            free_gb = psutil.virtual_memory().available / (1024**3)
            if free_gb < self._MIN_FREE_GB:
                raise RuntimeError(
                    f"Insufficient memory: {free_gb:.1f} GB available, "
                    f"{self._MIN_FREE_GB} GB required. "
                    "Close other applications or reduce batch size."
                )
        except ImportError:
            pass  # psutil not installed — skip check

    @staticmethod
    def _handle_train_oom(exc: RuntimeError) -> None:
        """Convert PyTorch CPU OOM errors into actionable English messages."""
        msg = str(exc).lower()
        if "not enough memory" in msg or "alloc" in msg or "out of memory" in msg:
            raise RuntimeError(
                "Training failed: CPU out of memory.\n"
                "Fix: 1) Reduce batch to 1-2   "
                "2) Close other apps   "
                "3) Reduce image size 640 \u2192 320"
            ) from exc
        raise exc

    def _find_best_weights(self, results: object) -> Optional[Path]:
        """Locate ``best.pt`` from the training run results."""
        # ultralytics stores best.pt inside the run's save_dir
        save_dir = getattr(results, "save_dir", None)
        if save_dir is not None:
            best = Path(save_dir) / "weights" / "best.pt"
            if best.exists():
                return best

        # Fallback: search the default ultralytics runs/ directory.
        for candidate in Path("runs").rglob("best.pt"):
            return candidate

        return None

    @staticmethod
    def _resolve_accelerator() -> dict:
        """Prefer CUDA on NVIDIA PCs and fail loudly when it is unavailable."""

        accelerator = detect_local_accelerator()
        if accelerator.get("gpu_present"):
            ensure_torch_cuda_wheel(require_cuda_wheel=True)
            if not accelerator.get("cuda_usable"):
                raise RuntimeError(
                    "NVIDIA GPU detected but torch CUDA is not usable. "
                    "Merge the CUDA runtime artifact and verify the driver before "
                    "starting YOLO26x fine-tuning."
                )
        return accelerator

    @staticmethod
    def _resolve_device(accelerator: Optional[dict] = None) -> object:
        """Use CUDA when available, otherwise fall back to CPU."""

        if accelerator is None:
            accelerator = TrainingManager._resolve_accelerator()
        return accelerator["device"]
