"""Tests for the compact PCB pretrain pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from PIL import Image

from src.training.compact_pretrain_pipeline import (
    CompactPretrainPipeline,
    LINE_PRETRAIN_CLASSES,
    _pcb_defect_target_from_name,
    _roboflow_folder_target,
    _smd_component_target_from_name,
)


def _fake_sample() -> dict:
    image = Image.fromarray(np.zeros((64, 64, 3), dtype=np.uint8))
    return {
        "image": image,
        "objects": {
            "category": [7, 13, 15, 1],  # Connector, Flex Cable, IC, Button
            "bbox": [
                [10.0, 10.0, 12.0, 12.0],
                [20.0, 20.0, 10.0, 10.0],
                [30.0, 30.0, 8.0, 8.0],
                [40.0, 40.0, 8.0, 8.0],
            ],
        },
    }


class TestCompactPretrainPipeline:
    def test_class_list_excludes_buttons(self) -> None:
        assert "button" not in LINE_PRETRAIN_CLASSES
        assert "connector" in LINE_PRETRAIN_CLASSES
        assert "flex_cable" in LINE_PRETRAIN_CLASSES

    def test_prepare_dataset_yaml_uses_line_classes(self, tmp_path: Path) -> None:
        pipeline = CompactPretrainPipeline(output_dir=tmp_path)
        for split in ("train", "val"):
            (tmp_path / split / "images").mkdir(parents=True, exist_ok=True)
        yaml_path = pipeline.prepare_dataset_yaml()
        content = yaml_path.read_text(encoding="utf-8")
        assert "connector" in content
        assert "button" not in content
        assert "train: train/images" in content
        assert "val: val/images" in content

    def test_build_bundle_creates_split_dataset(self, tmp_path: Path) -> None:
        pipeline = CompactPretrainPipeline(output_dir=tmp_path)

        fake_raw_names = [
            "circuit",
            "Button",
            "Buzzer",
            "Capacitor",
            "Capacitor Jumper",
            "Capacitor Network",
            "Clock",
            "Connector",
            "Diode",
            "EM",
            "Electrolytic Capacitor",
            "Electrolytic capacitor",
            "Ferrite Bead",
            "Flex Cable",
            "Fuse",
            "IC",
            "Inductor",
            "Jumper",
            "Led",
            "Pads",
            "Pins",
            "Potentiometer",
            "RP",
            "Resistor",
            "Resistor Jumper",
            "Resistor Network",
            "Switch",
            "Test Point",
            "Transducer",
            "Transformer",
            "Transistor",
            "Unknown Unlabeled",
        ]

        def fake_dataset() -> object:
            return iter([_fake_sample(), _fake_sample()])

        with patch(
            "src.training.compact_pretrain_pipeline._raw_category_names",
            return_value=fake_raw_names,
        ), patch(
            "datasets.load_dataset",
            side_effect=lambda *args, **kwargs: fake_dataset(),
        ), patch(
            "src.training.compact_pretrain_pipeline.CompactPretrainPipeline._ingest_pcb_defect_source",
            return_value=1,
        ), patch(
            "src.training.compact_pretrain_pipeline.CompactPretrainPipeline._ingest_roboflow_folder_source",
            return_value=1,
        ):
            manifest = pipeline.build_bundle(max_samples_per_source=1, grayscale=True, reset=True)

        assert manifest["total_images"] >= 3
        assert "pcb_inspection" in manifest["sources"]
        assert "pcb_component_detection" in manifest["sources"]
        assert "pcb_defect_detection" in manifest["sources"]
        assert "rf100_smd_components" in manifest["sources"]
        assert "rf100_deeppcb" in manifest["sources"]
        assert (tmp_path / "pretrain_dataset.yaml").exists()
        assert (tmp_path / "train" / "images").exists()
        assert (tmp_path / "val" / "images").exists()
        assert any((tmp_path / "train" / "images").iterdir())
        assert any((tmp_path / "train" / "labels").iterdir())
        assert not any((tmp_path / "images").glob("*"))

    def test_build_bundle_can_filter_sources(self, tmp_path: Path) -> None:
        pipeline = CompactPretrainPipeline(output_dir=tmp_path)

        fake_raw_names = [
            "circuit",
            "Button",
            "Buzzer",
            "Capacitor",
            "Capacitor Jumper",
            "Capacitor Network",
            "Clock",
            "Connector",
            "Diode",
            "EM",
            "Electrolytic Capacitor",
            "Electrolytic capacitor",
            "Ferrite Bead",
            "Flex Cable",
            "Fuse",
            "IC",
            "Inductor",
            "Jumper",
            "Led",
            "Pads",
            "Pins",
            "Potentiometer",
            "RP",
            "Resistor",
            "Resistor Jumper",
            "Resistor Network",
            "Switch",
            "Test Point",
            "Transducer",
            "Transformer",
            "Transistor",
            "Unknown Unlabeled",
        ]

        with patch(
            "src.training.compact_pretrain_pipeline._raw_category_names",
            return_value=fake_raw_names,
        ), patch(
            "datasets.load_dataset",
            side_effect=lambda *args, **kwargs: iter([_fake_sample()]),
        ), patch(
            "src.training.compact_pretrain_pipeline.CompactPretrainPipeline._ingest_pcb_defect_source",
            return_value=1,
        ), patch(
            "src.training.compact_pretrain_pipeline.CompactPretrainPipeline._ingest_roboflow_folder_source",
            return_value=1,
        ):
            manifest = pipeline.build_bundle(
                max_samples_per_source=1,
                grayscale=True,
                reset=True,
                source_names=["pcb_inspection", "pcb_component_detection"],
            )

        assert "pcb_inspection" in manifest["sources"]
        assert "pcb_component_detection" in manifest["sources"]
        assert "pcb_defect_detection" not in manifest["sources"]
        assert "rf100_smd_components" not in manifest["sources"]
        assert "rf100_deeppcb" not in manifest["sources"]

    def test_save_sample_writes_yolo_label(self, tmp_path: Path) -> None:
        pipeline = CompactPretrainPipeline(output_dir=tmp_path)
        img = np.zeros((64, 64, 3), dtype=np.uint8)
        pipeline._save_sample(
            "sample_00001",
            img,
            [{"label": "connector", "bbox": [10.0, 10.0, 30.0, 30.0]}],
        )
        lbl = (tmp_path / "labels" / "sample_00001.txt").read_text(encoding="utf-8").strip()
        assert lbl.startswith(f"{LINE_PRETRAIN_CLASSES.index('connector')} ")

    def test_pcb_defect_name_mapping(self) -> None:
        assert _pcb_defect_target_from_name("l_light_01_missing_hole_01_1_600.jpg") == "pin_hole"
        assert _pcb_defect_target_from_name("pcb_spurious_copper.jpg") == "copper"

    def test_roboflow_component_and_defect_mapping(self) -> None:
        assert _smd_component_target_from_name("IC Footprint") == "pads"
        assert _smd_component_target_from_name("Resistor Top") == "resistor"
        assert _roboflow_folder_target("rf100_deeppcb", "missing hole") == "pin_hole"
        assert _roboflow_folder_target("rf100_deeppcb", "short circuit") == "short"

    def test_ingest_roboflow_coco_folder_reads_annotations(self, tmp_path: Path) -> None:
        pipeline = CompactPretrainPipeline(output_dir=tmp_path)
        source_root = tmp_path / "source" / "smd-components"
        split_dir = source_root / "train"
        split_dir.mkdir(parents=True, exist_ok=True)

        image = np.zeros((32, 32, 3), dtype=np.uint8)
        Image.fromarray(image).save(split_dir / "sample_001.jpg")

        annotation = {
            "images": [
                {"id": 1, "file_name": "sample_001.jpg", "width": 32, "height": 32}
            ],
            "categories": [
                {"id": 1, "name": "Resistor Top"},
            ],
            "annotations": [
                {"id": 1, "image_id": 1, "category_id": 1, "bbox": [4, 5, 10, 11]},
            ],
        }
        (split_dir / "_annotations.coco.json").write_text(
            json.dumps(annotation),
            encoding="utf-8",
        )

        saved = pipeline._ingest_roboflow_coco_folder(
            source_root=source_root,
            source_name="rf100_smd_components",
            max_samples=10,
            grayscale=False,
            splits=("train",),
        )

        assert saved == 1
        assert any((tmp_path / "images").iterdir())
        label_text = next((tmp_path / "labels").glob("*.txt")).read_text(encoding="utf-8").strip()
        assert label_text.startswith(f"{LINE_PRETRAIN_CLASSES.index('resistor')} ")
