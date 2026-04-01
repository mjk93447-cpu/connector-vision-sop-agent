"""Compact local pretrain pipeline for PCB / electronics line data."""

from __future__ import annotations

import json
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np

from src.config_loader import detect_local_accelerator, get_base_dir
from src.training.dataset_converter import split_train_val

LINE_PRETRAIN_CLASSES: list[str] = [
    "pcb",
    "connector",
    "pins",
    "flex_cable",
    "ic",
    "led",
    "capacitor",
    "resistor",
    "switch",
    "diode",
    "inductor",
    "transistor",
    "clock",
    "fuse",
    "potentiometer",
    "test_point",
    "pads",
    "buzzer",
    "open",
    "short",
    "mousebite",
    "spur",
    "copper",
    "pin_hole",
]

_RAW_TO_TARGET: dict[str, str] = {
    "pcb": "pcb",
    "printed circuit board": "pcb",
    "printed-circuit-board": "pcb",
    "circuit": "pcb",
    "connector": "connector",
    "pins": "pins",
    "pin": "pins",
    "flex cable": "flex_cable",
    "flex-cable": "flex_cable",
    "ic": "ic",
    "ic ": "ic",
    "i c": "ic",
    "led": "led",
    "capacitor": "capacitor",
    "capacitor jumper": "capacitor",
    "capacitor network": "capacitor",
    "electrolytic capacitor": "capacitor",
    "resistor": "resistor",
    "resistor jumper": "resistor",
    "resistor network": "resistor",
    "switch": "switch",
    "diode": "diode",
    "inductor": "inductor",
    "transistor": "transistor",
    "clock": "clock",
    "fuse": "fuse",
    "potentiometer": "potentiometer",
    "test point": "test_point",
    "testpoint": "test_point",
    "pads": "pads",
    "buzzer": "buzzer",
}

_SOURCE_SPECS: list[dict[str, str]] = [
    {
        "name": "pcb_inspection",
        "repo_id": "Francesco/printed-circuit-board",
    },
    {
        "name": "pcb_component_detection",
        "repo_id": "Francesco/circuit-elements",
    },
]


def _normalize_label(label: str) -> str:
    key = re.sub(r"[\s_\-]+", " ", label.strip().lower())
    return re.sub(r"\s+", " ", key)


def _target_label(raw_label: str) -> Optional[str]:
    normalized = _normalize_label(raw_label)
    return _RAW_TO_TARGET.get(normalized)


def _raw_category_names(repo_id: str) -> list[str]:
    from datasets import load_dataset_builder  # noqa: PLC0415

    builder = load_dataset_builder(repo_id)
    objects = builder.info.features["objects"]
    category_feature = objects["category"]
    return list(category_feature.feature.names)


def _grayscale_profile(img_bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


@dataclass
class CompactPretrainConfig:
    output_dir: Path = field(default_factory=lambda: get_base_dir() / "pretrain_data")
    base_model: Path = field(
        default_factory=lambda: get_base_dir() / "assets/models/yolo26x.pt"
    )
    output_weights: Path = field(
        default_factory=lambda: get_base_dir()
        / "assets/models/yolo26x_local_pretrained.pt"
    )
    epochs: int = 40
    batch: int = 16
    image_size: int = 640
    val_ratio: float = 0.2
    random_seed: int = 42
    device: object = "cpu"
    class_names: list[str] = field(default_factory=lambda: LINE_PRETRAIN_CLASSES.copy())

    def __post_init__(self) -> None:
        self.output_dir = Path(self.output_dir)
        self.base_model = Path(self.base_model)
        self.output_weights = Path(self.output_weights)


class CompactPretrainPipeline:
    """Build a compact pretrain bundle and fine-tune YOLO26x locally."""

    def __init__(self, output_dir: str | Path | None = None, config: Optional[CompactPretrainConfig] = None) -> None:
        self.cfg = config or CompactPretrainConfig()
        if output_dir is not None:
            self.cfg.output_dir = Path(output_dir)
        self.output_dir = self.cfg.output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir = self.output_dir / "images"
        self.labels_dir = self.output_dir / "labels"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.labels_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def suggest_runtime_defaults(image_count: int | None = None) -> dict[str, Any]:
        accelerator = detect_local_accelerator()
        sample_count = image_count or 0
        if accelerator["device"] == "cpu":
            return {
                "device": "cpu",
                "epochs": 8 if sample_count <= 30 else 5,
                "batch": 2,
                "image_size": 320,
            }
        memory_gb = accelerator.get("memory_gb")
        batch = 16 if memory_gb and memory_gb >= 20 else 8 if memory_gb and memory_gb >= 12 else 4
        epochs = 60 if sample_count <= 30 else 40 if sample_count <= 120 else 30
        return {
            "device": accelerator["device"],
            "epochs": epochs,
            "batch": batch,
            "image_size": 640,
        }

    def build_bundle(
        self,
        max_samples_per_source: int = 400,
        grayscale: bool = True,
        reset: bool = True,
    ) -> dict[str, Any]:
        if reset and self.output_dir.exists():
            shutil.rmtree(self.output_dir)
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.images_dir.mkdir(parents=True, exist_ok=True)
            self.labels_dir.mkdir(parents=True, exist_ok=True)

        totals: dict[str, int] = {}
        total_saved = 0
        for spec in _SOURCE_SPECS:
            saved = self._ingest_hf_source(
                repo_id=spec["repo_id"],
                source_name=spec["name"],
                max_samples=max_samples_per_source,
                grayscale=grayscale,
            )
            totals[spec["name"]] = saved
            total_saved += saved

        if total_saved <= 0:
            raise RuntimeError("No training samples were collected for the pretrain bundle.")

        split_train_val(self.output_dir, val_ratio=self.cfg.val_ratio, seed=self.cfg.random_seed)
        self._prune_flat_storage()
        yaml_path = self.prepare_dataset_yaml()
        manifest = {
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_images": total_saved,
            "sources": totals,
            "classes": self.cfg.class_names,
            "description": "Bundled grayscale PCB inspection and PCB component detection data for offline YOLO26x pretraining.",
            "yaml": str(yaml_path),
        }
        (self.output_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return manifest

    def prepare_dataset_yaml(self) -> Path:
        yaml_path = self.output_dir / "pretrain_dataset.yaml"
        train_path = (self.output_dir / "train" / "images").resolve()
        val_path = (self.output_dir / "val" / "images").resolve()
        content = (
            f"path: {self.output_dir.resolve()}\n"
            f"train: {train_path}\n"
            f"val: {val_path}\n"
            f"nc: {len(self.cfg.class_names)}\n"
            f"names: {json.dumps(self.cfg.class_names, ensure_ascii=False)}\n"
        )
        yaml_path.write_text(content, encoding="utf-8")
        return yaml_path

    def train_and_save(
        self,
        epochs: Optional[int] = None,
        batch: Optional[int] = None,
        device: Optional[object] = None,
    ) -> Path:
        from ultralytics import YOLO  # noqa: PLC0415

        yaml_path = self.output_dir / "pretrain_dataset.yaml"
        if not yaml_path.exists():
            if not (self.output_dir / "train" / "images").exists():
                raise RuntimeError(
                    "Pretrain dataset is not prepared. Run the bundle prep step first."
                )
            self.prepare_dataset_yaml()

        model_path = self.cfg.base_model if self.cfg.base_model.exists() else Path("yolo26x.pt")
        if not model_path.exists():
            raise FileNotFoundError(f"Base model not found: {model_path}")

        train_device = device if device is not None else self.cfg.device
        train_epochs = epochs or self.cfg.epochs
        train_batch = batch or self.cfg.batch

        model = YOLO(str(model_path))
        results = model.train(
            data=str(yaml_path),
            epochs=train_epochs,
            imgsz=self.cfg.image_size,
            batch=train_batch,
            device=train_device,
            workers=0,
            exist_ok=True,
            rect=False,
            hsv_h=0.0,
            hsv_s=0.0,
            hsv_v=0.0,
            degrees=0.0,
            translate=0.03,
            scale=0.05,
            shear=0.0,
            perspective=0.0,
            flipud=0.0,
            fliplr=0.0,
            mosaic=0.0,
            mixup=0.0,
            copy_paste=0.0,
            erasing=0.0,
            close_mosaic=0,
            patience=max(10, min(train_epochs // 2, 20)),
            pretrained=True,
            verbose=False,
            plots=False,
        )

        best_pt = self._find_best_weights(results)
        if best_pt is None or not best_pt.exists():
            raise RuntimeError("Training completed but best.pt was not found.")

        self.cfg.output_weights.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(best_pt, self.cfg.output_weights)
        return self.cfg.output_weights

    def _ingest_hf_source(
        self,
        repo_id: str,
        source_name: str,
        max_samples: int,
        grayscale: bool,
    ) -> int:
        from datasets import load_dataset  # noqa: PLC0415

        raw_names = _raw_category_names(repo_id)
        ds = load_dataset(repo_id, split="train", streaming=True, trust_remote_code=False)
        saved = 0
        for sample in ds:
            if saved >= max_samples:
                break
            image = sample.get("image")
            if image is None:
                continue

            img_bgr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            if grayscale:
                img_bgr = _grayscale_profile(img_bgr)

            objects = sample.get("objects") or {}
            categories = objects.get("category") or []
            bboxes = objects.get("bbox") or []
            annotations: list[dict[str, Any]] = []

            for cat_id, coco_box in zip(categories, bboxes):
                try:
                    raw_label = raw_names[int(cat_id)]
                except Exception:
                    continue
                target = _target_label(raw_label)
                if target is None:
                    continue
                if target not in self.cfg.class_names:
                    continue
                x, y, w, h = [float(v) for v in coco_box[:4]]
                if w <= 0 or h <= 0:
                    continue
                annotations.append(
                    {
                        "label": target,
                        "bbox": [x, y, x + w, y + h],
                    }
                )

            if not annotations:
                continue

            stem = f"{source_name}_{saved:05d}"
            self._save_sample(stem, img_bgr, annotations)
            saved += 1

        return saved

    def _save_sample(self, stem: str, img_bgr: np.ndarray, annotations: list[dict[str, Any]]) -> None:
        img_path = self.images_dir / f"{stem}.png"
        lbl_path = self.labels_dir / f"{stem}.txt"
        cv2.imwrite(str(img_path), img_bgr)
        h, w = img_bgr.shape[:2]
        lines: list[str] = []
        for ann in annotations:
            label = ann.get("label", "")
            if label not in self.cfg.class_names:
                continue
            class_id = self.cfg.class_names.index(label)
            x1, y1, x2, y2 = [float(v) for v in ann["bbox"][:4]]
            cx = (x1 + x2) / 2.0 / w
            cy = (y1 + y2) / 2.0 / h
            bw = abs(x2 - x1) / w
            bh = abs(y2 - y1) / h
            lines.append(f"{class_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
        lbl_path.write_text("\n".join(lines), encoding="utf-8")

    def _prune_flat_storage(self) -> None:
        for folder in (self.images_dir, self.labels_dir):
            if folder.exists():
                shutil.rmtree(folder)

    @staticmethod
    def _find_best_weights(results: object) -> Optional[Path]:
        save_dir = getattr(results, "save_dir", None)
        if save_dir is not None:
            candidate = Path(save_dir) / "weights" / "best.pt"
            if candidate.exists():
                return candidate
        for candidate in Path("runs").rglob("best.pt"):
            return candidate
        return None
