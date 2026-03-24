"""
YOLO fine-tuning manager for OLED line PC.

Wraps ultralytics YOLO.train() and saves the best weights to
``assets/models/yolo26x.pt`` upon completion.

Usage
-----
  tm = TrainingManager()
  output_path = tm.train(
      dataset_yaml="training_data/dataset.yaml",
      base_model="yolo26x.pt",     # or "assets/models/yolo26x.pt"
      epochs=10,
      image_size=640,
      progress_cb=lambda epoch, total: print(f"{epoch}/{total}"),
  )
  # output_path == "assets/models/yolo26x.pt"
"""

from __future__ import annotations

import io
import os
import shutil
import sys
from pathlib import Path
from typing import Callable, Optional

from src.config_loader import get_base_dir

_DEFAULT_BASE_MODEL = (
    "yolo26x.pt"  # YOLO26x: NMS-free, highest mAP in YOLO26 family (ultralytics>=8.4.0)
)
_TARGET_WEIGHTS = get_base_dir() / "assets/models/yolo26x.pt"


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
        batch: int = 4,
        base_model: Optional[str] = None,
        progress_cb: Optional[Callable[[int, int], None]] = None,
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

        Returns
        -------
        Path to the saved weights file (``assets/models/yolo26x.pt``).

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

        # Determine starting weights: prefer existing custom model if present,
        # then caller-supplied base_model override, then self.base_model default.
        if self.target_weights.exists():
            start_weights = str(self.target_weights)
        elif base_model is not None:
            start_weights = base_model
        else:
            start_weights = self.base_model

        # ------------------------------------------------------------------ #
        # Clean stale ultralytics label-cache files.                        #
        # Leftover *.cache.npy files from an interrupted previous run cause #
        # the infamous 'NoneType' object has no attribute 'write' crash on  #
        # the cache-rebuild path.  Deleting them here ensures a clean start #
        # and reproduces the "first run always works" behaviour the user     #
        # already observes.                                                  #
        # ------------------------------------------------------------------ #
        self._clean_stale_caches(dataset_yaml)

        # Guard: model file must exist — never auto-download from GitHub
        if not Path(start_weights).exists():
            raise FileNotFoundError(
                f"Model file not found: {start_weights}\n"
                "Place yolo26x.pt in assets/models/ before training."
            )

        model = YOLO(start_weights)

        # Patch the on_train_epoch_end callback to forward progress.
        if progress_cb is not None:

            def _epoch_cb(trainer: object) -> None:  # noqa: ANN001
                epoch = getattr(trainer, "epoch", 0) + 1
                total = getattr(trainer, "epochs", epochs)
                progress_cb(epoch, total)

            model.add_callback("on_train_epoch_end", _epoch_cb)

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
            sys.stdout = _TeeWriter(sys.stdout, _log_file)
            sys.stderr = _TeeWriter(sys.stderr, _log_file)
            results = model.train(
                data=str(dataset_yaml),
                epochs=epochs,
                imgsz=image_size,
                batch=batch,
                device="cpu",
                workers=0,  # single-process DataLoader (Windows multiprocessing fix)
                exist_ok=True,  # overwrite previous run directory
                rect=False,  # disable rectangular training
                verbose=True,
                plots=False,
            )
        finally:
            sys.stdout = _orig_stdout
            sys.stderr = _orig_stderr
            _log_file.close()

        # Copy best weights to target location.
        best_pt = self._find_best_weights(results)
        if best_pt and best_pt.exists():
            self.target_weights.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(best_pt, self.target_weights)

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
