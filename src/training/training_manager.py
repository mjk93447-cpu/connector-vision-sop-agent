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

import os
import shutil
from pathlib import Path
from typing import Callable, Optional


_DEFAULT_BASE_MODEL = (
    "yolo26x.pt"  # YOLO26x: NMS-free, highest mAP in YOLO26 family (ultralytics>=8.4.0)
)
_TARGET_WEIGHTS = Path("assets/models/yolo26x.pt")


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
        FileNotFoundError: dataset.yaml or start weights file not found.
        """
        # Prevent ultralytics from auto-downloading models from GitHub
        os.environ["YOLO_OFFLINE"] = "1"
        try:
            from ultralytics.utils import SETTINGS  # noqa: PLC0415

            SETTINGS.update({"sync": False})
        except Exception:  # noqa: BLE001
            pass  # ultralytics not installed or SETTINGS not accessible — proceed

        from ultralytics import YOLO  # noqa: PLC0415 — heavy import, defer

        dataset_yaml = Path(dataset_yaml)
        if not dataset_yaml.exists():
            raise FileNotFoundError(f"dataset.yaml not found: {dataset_yaml}")

        # Determine starting weights: prefer existing custom model if present,
        # then caller-supplied base_model override, then self.base_model default.
        if self.target_weights.exists():
            start_weights = str(self.target_weights)
        elif base_model is not None:
            start_weights = base_model
        else:
            start_weights = self.base_model

        # Guard: model file must exist — never auto-download from GitHub
        if not Path(start_weights).exists():
            raise FileNotFoundError(
                f"Model file not found: {start_weights}\n"
                "Download yolo26x.pt from GitHub Actions artifacts and place in assets/models/"
            )

        model = YOLO(start_weights)

        # Patch the on_train_epoch_end callback to forward progress.
        if progress_cb is not None:

            def _epoch_cb(trainer: object) -> None:  # noqa: ANN001
                epoch = getattr(trainer, "epoch", 0) + 1
                total = getattr(trainer, "epochs", epochs)
                progress_cb(epoch, total)

            model.add_callback("on_train_epoch_end", _epoch_cb)

        # Run training (blocking; call from a QThread for GUI use).
        results = model.train(
            data=str(dataset_yaml),
            epochs=epochs,
            imgsz=image_size,
            batch=batch,
            device="cpu",
            verbose=False,
            plots=False,
        )

        # Copy best weights to target location.
        best_pt = self._find_best_weights(results)
        if best_pt and best_pt.exists():
            self.target_weights.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(best_pt, self.target_weights)

        return self.target_weights

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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
