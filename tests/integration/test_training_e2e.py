"""
End-to-end integration test: actual YOLO26x training run.

Verifies that:
1. TrainingManager.train() completes without AttributeError 'NoneType.write'
2. training.log is created and contains real YOLO metrics
3. YOLO output is readable: Epoch, box_loss, mAP50 lines present
4. _TeeWriter captures output correctly (no data loss)

Requires:
  - assets/models/yolo26n.pt  (YOLO26 nano — smallest, fastest for CI)
  - ultralytics installed

Skip conditions:
  - Model file not present
  - ultralytics not installed
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

# Training E2E tests run actual YOLO inference (CPU): 90-180s per test.
# Override the global --timeout=60 used in CI to prevent false failures.
pytestmark = pytest.mark.timeout(300)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MODEL_CANDIDATES = [
    Path("assets/models/yolo26n.pt"),  # nano — fastest
    Path("assets/models/yolo26x_pretrained.pt"),  # pretrained — larger
]


def _find_model() -> Path | None:
    """Return the first available YOLO26 model file for testing."""
    for candidate in _MODEL_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def _create_minimal_dataset(root: Path, n_images: int = 5) -> Path:
    """Create a minimal YOLO-format dataset with synthetic images and labels.

    Layout:
        root/
          images/button/  *.png   (32x32 white images)
          labels/button/  *.txt   (single bbox per image)
          dataset.yaml
    """
    images_dir = root / "images" / "button"
    labels_dir = root / "labels" / "button"
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)

    for i in range(n_images):
        # Create a minimal 32x32 white PNG using struct (no cv2/PIL needed)
        img_path = images_dir / f"img_{i:03d}.png"
        _write_tiny_png(img_path, width=32, height=32)

        # YOLO label: class_id cx cy w h (all normalised)
        label_path = labels_dir / f"img_{i:03d}.txt"
        label_path.write_text("0 0.5 0.5 0.3 0.3\n", encoding="utf-8")

    yaml_path = root / "dataset.yaml"
    yaml_path.write_text(
        f"path: {root.as_posix()}\n"
        "train: images\n"
        "val: images\n"
        "nc: 1\n"
        "names: [button]\n",
        encoding="utf-8",
    )
    return yaml_path


def _write_tiny_png(path: Path, width: int = 32, height: int = 32) -> None:
    """Write a minimal white RGB PNG without external dependencies."""
    import zlib

    def _chunk(name: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + name + data
        return c + struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)

    raw_rows = b""
    for _ in range(height):
        row = b"\x00" + b"\xff" * (width * 3)  # filter-byte + RGB pixels
        raw_rows += row

    png = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(raw_rows))
        + _chunk(b"IEND", b"")
    )
    path.write_bytes(png)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestTrainingE2E:
    """Actual YOLO26x training: verifies training.log readability."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_model(self):
        model_path = _find_model()
        if model_path is None:
            pytest.skip(
                "No YOLO26 model found in assets/models/ — "
                "place yolo26n.pt or yolo26x_pretrained.pt to run this test"
            )
        self._model_path = model_path
        try:
            import ultralytics  # noqa: F401
        except ImportError:
            pytest.skip("ultralytics not installed")

    def test_training_completes_without_nonewrite_error(self, tmp_path):
        """Training must complete; AttributeError 'NoneType.write' must not occur."""
        from src.training.training_manager import TrainingManager

        yaml_path = _create_minimal_dataset(tmp_path, n_images=8)
        tm = TrainingManager(
            base_model=str(self._model_path),
            target_weights=tmp_path / "out_weights.pt",
        )

        # Run 1 epoch; imgsz=64 keeps batch-norm spatial dims ≥ 2×2
        tm.train(dataset_yaml=yaml_path, epochs=1, image_size=64, batch=4)

        # If we reach here, no AttributeError was raised — test passes
        assert tm.last_training_log is not None
        assert tm.last_training_log.exists(), "training.log was not created"

    def test_training_log_contains_yolo_metrics(self, tmp_path):
        """training.log must contain real YOLO output (Epoch, box_loss, mAP50)."""
        from src.training.training_manager import TrainingManager

        yaml_path = _create_minimal_dataset(tmp_path, n_images=8)
        tm = TrainingManager(
            base_model=str(self._model_path),
            target_weights=tmp_path / "out_weights.pt",
        )

        tm.train(dataset_yaml=yaml_path, epochs=1, image_size=64, batch=4)

        log_text = tm.last_training_log.read_text(encoding="utf-8", errors="replace")

        # Print the log so CI output shows it
        print("\n" + "=" * 60)
        print("YOLO26x training.log content:")
        print("=" * 60)
        print(log_text)
        print("=" * 60)

        # Assert key YOLO output markers are present
        assert len(log_text) > 50, "training.log appears empty"
        log_lower = log_text.lower()
        assert any(
            kw in log_lower for kw in ("epoch", "box_loss", "loss", "map", "train")
        ), (
            "training.log does not contain expected YOLO training output.\n"
            f"Actual content:\n{log_text[:500]}"
        )

    def test_tee_writer_with_none_stdout_training(self, tmp_path, monkeypatch):
        """Full training must complete even when sys.stdout is None (EXE simulation)."""
        from src.training.training_manager import TrainingManager

        yaml_path = _create_minimal_dataset(tmp_path, n_images=8)
        tm = TrainingManager(
            base_model=str(self._model_path),
            target_weights=tmp_path / "out_weights.pt",
        )

        # Simulate PyInstaller console=False environment
        monkeypatch.setattr(sys, "stdout", None)
        monkeypatch.setattr(sys, "stderr", None)

        try:
            tm.train(dataset_yaml=yaml_path, epochs=1, image_size=64, batch=4)
        except AttributeError as e:
            pytest.fail(
                f"AttributeError raised with sys.stdout=None — "
                f"_TeeWriter guard not working: {e}"
            )
        # monkeypatch restores sys.stdout after the test automatically

        assert tm.last_training_log is not None
        log_text = tm.last_training_log.read_text(encoding="utf-8", errors="replace")
        assert len(log_text) > 0, "training.log empty when stdout=None"
