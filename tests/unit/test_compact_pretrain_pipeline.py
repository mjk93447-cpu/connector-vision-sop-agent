"""Tests for the compact PCB pretrain pipeline."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from PIL import Image

from src.training.compact_pretrain_pipeline import (
    CompactPretrainPipeline,
    LINE_PRETRAIN_CLASSES,
    _pcb_defect_target_from_name,
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
        ):
            manifest = pipeline.build_bundle(max_samples_per_source=1, grayscale=True, reset=True)

        assert manifest["total_images"] >= 3
        assert "pcb_inspection" in manifest["sources"]
        assert "pcb_component_detection" in manifest["sources"]
        assert "pcb_defect_detection" in manifest["sources"]
        assert (tmp_path / "pretrain_dataset.yaml").exists()
        assert (tmp_path / "train" / "images").exists()
        assert (tmp_path / "val" / "images").exists()
        assert any((tmp_path / "train" / "images").iterdir())
        assert any((tmp_path / "train" / "labels").iterdir())
        assert not any((tmp_path / "images").glob("*"))

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
