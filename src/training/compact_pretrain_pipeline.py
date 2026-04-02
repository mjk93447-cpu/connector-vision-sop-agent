"""Compact local pretrain pipeline for PCB / electronics line data."""

from __future__ import annotations

import json
import re
import shutil
import time
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np

from src.config_loader import get_base_dir
from src.pretrain_runtime import detect_pretrain_hardware, suggest_pretrain_profile
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

_SOURCE_SPECS: list[dict[str, Any]] = [
    {
        "name": "pcb_inspection",
        "repo_id": "Francesco/printed-circuit-board",
        "kind": "objects",
        "splits": ("train", "validation", "test"),
    },
    {
        "name": "pcb_component_detection",
        "repo_id": "Francesco/circuit-elements",
        "kind": "objects",
        "splits": ("train",),
    },
    {
        "name": "pcb_defect_detection",
        "repo_id": "itsyoboieltr/pcb",
        "kind": "pcb_defects",
        "splits": ("train", "validation", "test"),
    },
    {
        "name": "rf100_smd_components",
        "repo_id": "gatilin/rf100-vl-datasets",
        "kind": "roboflow_folder",
        "folder": "smd-components",
        "splits": ("train", "valid", "validation", "test"),
    },
    {
        "name": "rf100_deeppcb",
        "repo_id": "gatilin/rf100-vl-datasets",
        "kind": "roboflow_folder",
        "folder": "deeppcb",
        "splits": ("train", "valid", "validation", "test"),
    },
]

_PCB_DEFECT_NAME_TO_TARGET: dict[str, str] = {
    "missing_hole": "pin_hole",
    "pin_hole": "pin_hole",
    "mouse_bite": "mousebite",
    "mousebite": "mousebite",
    "open_circuit": "open",
    "open": "open",
    "short": "short",
    "spur": "spur",
    "spurious_copper": "copper",
    "spurious copper": "copper",
    "copper": "copper",
}


def _normalize_label(label: str) -> str:
    key = re.sub(r"[\s_\-]+", " ", label.strip().lower())
    return re.sub(r"\s+", " ", key)


def _target_label(raw_label: str) -> Optional[str]:
    normalized = _normalize_label(raw_label)
    return _RAW_TO_TARGET.get(normalized)


def _smd_component_target_from_name(raw_label: str) -> Optional[str]:
    normalized = _normalize_label(raw_label)
    if not normalized:
        return None
    if "footprint" in normalized:
        return "pads"
    if "bottom" in normalized or "top" in normalized:
        normalized = normalized.replace("bottom", "").replace("top", "")
        normalized = re.sub(r"\s+", " ", normalized).strip()
    return _target_label(normalized)


def _roboflow_defect_target_from_name(raw_label: str) -> Optional[str]:
    normalized = _normalize_label(raw_label)
    if not normalized:
        return None
    return _pcb_defect_target_from_name(normalized)


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
        profile = suggest_pretrain_profile(image_count=image_count)
        return {
            "device": profile.device,
            "epochs": profile.epochs,
            "batch": profile.batch,
            "image_size": profile.image_size,
            "workers": profile.workers,
        }

    def build_bundle(
        self,
        max_samples_per_source: int = 10000,
        grayscale: bool = True,
        reset: bool = True,
        source_names: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        if reset and self.output_dir.exists():
            shutil.rmtree(self.output_dir)
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.images_dir.mkdir(parents=True, exist_ok=True)
            self.labels_dir.mkdir(parents=True, exist_ok=True)

        totals: dict[str, int] = {}
        total_saved = 0
        selected_sources = set(source_names) if source_names else None
        for spec in _SOURCE_SPECS:
            if selected_sources is not None and spec["name"] not in selected_sources:
                continue
            kind = spec.get("kind", "objects")
            splits = tuple(spec.get("splits", ("train",)))
            if kind == "pcb_defects":
                saved = self._ingest_pcb_defect_source(
                    repo_id=spec["repo_id"],
                    source_name=spec["name"],
                    max_samples=max_samples_per_source,
                    grayscale=grayscale,
                    splits=splits,
                )
            elif kind == "roboflow_folder":
                saved = self._ingest_roboflow_folder_source(
                    repo_id=spec["repo_id"],
                    folder_name=spec["folder"],
                    source_name=spec["name"],
                    max_samples=max_samples_per_source,
                    grayscale=grayscale,
                    splits=splits,
                )
            else:
                saved = self._ingest_hf_source(
                    repo_id=spec["repo_id"],
                    source_name=spec["name"],
                    max_samples=max_samples_per_source,
                    grayscale=grayscale,
                    splits=splits,
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
            "description": "Bundled grayscale PCB inspection, PCB component detection, and PCB defect data from line-relevant PCB datasets for offline YOLO26x pretraining.",
            "yaml": str(yaml_path),
        }
        (self.output_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return manifest

    def prepare_dataset_yaml(self) -> Path:
        yaml_path = self.output_dir / "pretrain_dataset.yaml"
        root_path = self.output_dir.resolve()
        content = (
            f"path: {root_path}\n"
            f"train: train/images\n"
            f"val: val/images\n"
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
        imgsz: Optional[int] = None,
        workers: Optional[int] = None,
    ) -> Path:
        from ultralytics import YOLO  # noqa: PLC0415

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
        train_imgsz = imgsz or self.cfg.image_size
        if workers is None:
            hw = detect_pretrain_hardware()
            workers = max(2, min(int(hw["physical_cores"] or 2), 8))

        model = YOLO(str(model_path))
        results = model.train(
            data=str(yaml_path),
            epochs=train_epochs,
            imgsz=train_imgsz,
            batch=train_batch,
            device=train_device,
            workers=workers,
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
        splits: tuple[str, ...] = ("train",),
    ) -> int:
        from datasets import load_dataset  # noqa: PLC0415

        raw_names = _raw_category_names(repo_id)
        saved = 0
        for split_name in splits:
            if saved >= max_samples:
                break
            ds = load_dataset(repo_id, split=split_name, streaming=True, trust_remote_code=False)
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

    def _ingest_pcb_defect_source(
        self,
        repo_id: str,
        source_name: str,
        max_samples: int,
        grayscale: bool,
        splits: tuple[str, ...] = ("train",),
    ) -> int:
        from datasets import load_dataset  # noqa: PLC0415

        saved = 0
        for split_name in splits:
            if saved >= max_samples:
                break
            ds = load_dataset(repo_id, split=split_name, streaming=True, trust_remote_code=False)
            for sample in ds:
                if saved >= max_samples:
                    break

                image = sample.get("image")
                label = sample.get("label") or {}
                if image is None or not isinstance(label, dict):
                    continue

                label_name = str(label.get("name", ""))
                target = _pcb_defect_target_from_name(label_name)
                if target is None or target not in self.cfg.class_names:
                    continue

                img_bgr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                if grayscale:
                    img_bgr = _grayscale_profile(img_bgr)

                bboxes = label.get("bboxes") or []
                annotations: list[dict[str, Any]] = []
                for bbox_info in bboxes:
                    bbox = bbox_info.get("bbox") if isinstance(bbox_info, dict) else None
                    if not bbox or len(bbox) < 4:
                        continue
                    cx, cy, bw, bh = [float(v) for v in bbox[:4]]
                    if bw <= 0 or bh <= 0:
                        continue
                    x1 = (cx - bw / 2.0) * img_bgr.shape[1]
                    y1 = (cy - bh / 2.0) * img_bgr.shape[0]
                    x2 = (cx + bw / 2.0) * img_bgr.shape[1]
                    y2 = (cy + bh / 2.0) * img_bgr.shape[0]
                    annotations.append(
                        {
                            "label": target,
                            "bbox": [x1, y1, x2, y2],
                        }
                    )

                if not annotations:
                    continue

                stem = f"{source_name}_{saved:05d}"
                self._save_sample(stem, img_bgr, annotations)
                saved += 1

        return saved

    def _ingest_roboflow_folder_source(
        self,
        repo_id: str,
        folder_name: str,
        source_name: str,
        max_samples: int,
        grayscale: bool,
        splits: tuple[str, ...] = ("train",),
    ) -> int:
        from huggingface_hub import snapshot_download  # noqa: PLC0415

        with tempfile.TemporaryDirectory(prefix="rf100_bundle_") as tmpdir:
            local_root = Path(
                snapshot_download(
                    repo_id=repo_id,
                    repo_type="dataset",
                    allow_patterns=[f"{folder_name}/**"],
                    local_dir=tmpdir,
                    local_dir_use_symlinks=False,
                )
            )
            source_root = local_root / folder_name
            if not source_root.exists():
                candidate = next((path for path in local_root.rglob(folder_name) if path.is_dir()), None)
                if candidate is None:
                    raise FileNotFoundError(f"Roboflow source folder not found: {folder_name}")
                source_root = candidate
            return self._ingest_roboflow_coco_folder(
                source_root=source_root,
                source_name=source_name,
                max_samples=max_samples,
                grayscale=grayscale,
                splits=splits,
            )

    def _ingest_roboflow_coco_folder(
        self,
        source_root: Path,
        source_name: str,
        max_samples: int,
        grayscale: bool,
        splits: tuple[str, ...] = ("train",),
    ) -> int:
        saved = 0
        for split_name in splits:
            if saved >= max_samples:
                break
            split_dir = self._resolve_roboflow_split_dir(source_root, split_name)
            if split_dir is None:
                continue
            annotation_file = self._find_roboflow_annotation_file(split_dir)
            if annotation_file is None:
                continue

            annotations = json.loads(annotation_file.read_text(encoding="utf-8"))
            category_map = {
                category["id"]: category["name"]
                for category in annotations.get("categories", [])
                if "id" in category and "name" in category
            }
            image_map = {
                image["id"]: image
                for image in annotations.get("images", [])
                if "id" in image and "file_name" in image
            }
            grouped: dict[Any, list[dict[str, Any]]] = defaultdict(list)
            for annot in annotations.get("annotations", []):
                image_id = annot.get("image_id")
                if image_id is not None:
                    grouped[image_id].append(annot)

            for image_id, image in image_map.items():
                if saved >= max_samples:
                    break
                image_path = split_dir / image["file_name"]
                if not image_path.exists():
                    image_path = next((path for path in split_dir.rglob(image["file_name"]) if path.is_file()), None)
                    if image_path is None:
                        continue

                img_bgr = cv2.imread(str(image_path))
                if img_bgr is None:
                    continue
                if grayscale:
                    img_bgr = _grayscale_profile(img_bgr)

                annotations_out: list[dict[str, Any]] = []
                for annot in grouped.get(image_id, []):
                    category_name = category_map.get(annot.get("category_id"))
                    if category_name is None:
                        continue
                    target = _roboflow_folder_target(source_name, category_name)
                    if target is None or target not in self.cfg.class_names:
                        continue
                    bbox = annot.get("bbox") or []
                    if len(bbox) < 4:
                        continue
                    x, y, w, h = [float(v) for v in bbox[:4]]
                    if w <= 0 or h <= 0:
                        continue
                    annotations_out.append(
                        {
                            "label": target,
                            "bbox": [x, y, x + w, y + h],
                        }
                    )

                if not annotations_out:
                    continue

                stem = f"{source_name}_{saved:05d}"
                self._save_sample(stem, img_bgr, annotations_out)
                saved += 1

        return saved

    @staticmethod
    def _resolve_roboflow_split_dir(source_root: Path, split_name: str) -> Optional[Path]:
        candidates = [split_name]
        if split_name == "validation":
            candidates.append("valid")
        if split_name == "valid":
            candidates.append("validation")
        for candidate in candidates:
            split_dir = source_root / candidate
            if split_dir.exists():
                return split_dir
        return None

    @staticmethod
    def _find_roboflow_annotation_file(split_dir: Path) -> Optional[Path]:
        candidates = list(split_dir.rglob("*_annotations.coco.json"))
        if candidates:
            return candidates[0]
        candidates = list(split_dir.rglob("*.json"))
        return candidates[0] if candidates else None

    def _save_sample(self, stem: str, img_bgr: np.ndarray, annotations: list[dict[str, Any]]) -> None:
        img_path = self.images_dir / f"{stem}.jpg"
        lbl_path = self.labels_dir / f"{stem}.txt"
        cv2.imwrite(str(img_path), img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
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

    def _find_best_weights(results: object) -> Optional[Path]:
        save_dir = getattr(results, "save_dir", None)
        if save_dir is not None:
            candidate = Path(save_dir) / "weights" / "best.pt"
            if candidate.exists():
                return candidate
        for candidate in Path("runs").rglob("best.pt"):
            return candidate
        return None


def _pcb_defect_target_from_name(name: str) -> Optional[str]:
    normalized = _normalize_label(name)
    for token, target in sorted(
        _PCB_DEFECT_NAME_TO_TARGET.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if _normalize_label(token) in normalized:
            return target
    return None


def _roboflow_folder_target(source_name: str, raw_label: str) -> Optional[str]:
    normalized_source = _normalize_label(source_name)
    if "smd" in normalized_source or "component" in normalized_source:
        target = _smd_component_target_from_name(raw_label)
        if target is not None:
            return target
    if "deeppcb" in normalized_source:
        target = _roboflow_defect_target_from_name(raw_label)
        if target is not None:
            return target
    target = _target_label(raw_label)
    if target is not None:
        return target
    target = _pcb_defect_target_from_name(raw_label)
    if target is not None:
        return target
    return None
