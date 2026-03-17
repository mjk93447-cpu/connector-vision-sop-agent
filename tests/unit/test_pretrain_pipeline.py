"""단위 테스트: PretrainPipeline + DatasetConverter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import numpy as np

from src.training.dataset_converter import (
    PRETRAIN_CLASSES,
    SyntheticGUIGenerator,
    convert_rico_sample,
    map_android_class,
    split_train_val,
)
from src.training.pretrain_pipeline import PretrainConfig, PretrainPipeline


# ---------------------------------------------------------------------------
# PRETRAIN_CLASSES
# ---------------------------------------------------------------------------


class TestPretrainClasses:
    def test_class_count(self) -> None:
        assert len(PRETRAIN_CLASSES) == 7

    def test_required_classes_present(self) -> None:
        required = {
            "button",
            "icon",
            "label",
            "connector",
            "input_field",
            "checkbox",
            "dropdown",
        }
        assert required == set(PRETRAIN_CLASSES)

    def test_button_is_index_0(self) -> None:
        assert PRETRAIN_CLASSES[0] == "button"

    def test_connector_is_index_3(self) -> None:
        assert PRETRAIN_CLASSES[3] == "connector"


# ---------------------------------------------------------------------------
# map_android_class
# ---------------------------------------------------------------------------


class TestMapAndroidClass:
    def test_button_maps_to_0(self) -> None:
        assert map_android_class("android.widget.Button") == 0
        assert map_android_class("Button") == 0

    def test_image_view_maps_to_icon(self) -> None:
        assert map_android_class("ImageView") == 1

    def test_text_view_maps_to_label(self) -> None:
        assert map_android_class("android.widget.TextView") == 2

    def test_edit_text_maps_to_input_field(self) -> None:
        assert map_android_class("EditText") == 4

    def test_checkbox_maps_to_5(self) -> None:
        assert map_android_class("CheckBox") == 5
        assert map_android_class("Switch") == 5

    def test_spinner_maps_to_dropdown(self) -> None:
        assert map_android_class("Spinner") == 6

    def test_unknown_class_returns_none(self) -> None:
        assert map_android_class("android.view.ViewGroup") is None
        assert map_android_class("UnknownWidget") is None

    def test_material_variants_mapped(self) -> None:
        assert map_android_class("MaterialButton") == 0
        assert map_android_class("MaterialTextView") == 2


# ---------------------------------------------------------------------------
# SyntheticGUIGenerator
# ---------------------------------------------------------------------------


class TestSyntheticGUIGenerator:
    def test_generate_returns_image_and_annotations(self) -> None:
        gen = SyntheticGUIGenerator(seed=0)
        img, ann = gen.generate(width=640, height=480, n_elements=4)
        assert img.shape == (480, 640, 3)
        assert isinstance(ann, list)
        assert len(ann) == 4

    def test_annotation_keys(self) -> None:
        gen = SyntheticGUIGenerator(seed=0)
        _, ann = gen.generate(n_elements=6)
        for a in ann:
            assert "label" in a
            assert "bbox" in a
            assert a["label"] in PRETRAIN_CLASSES
            x1, y1, x2, y2 = a["bbox"]
            assert x2 > x1 and y2 > y1

    def test_bbox_within_image_bounds(self) -> None:
        gen = SyntheticGUIGenerator(seed=1)
        img, ann = gen.generate(width=800, height=600, n_elements=8)
        h, w = img.shape[:2]
        for a in ann:
            x1, y1, x2, y2 = a["bbox"]
            assert 0 <= x1 < x2 <= w
            assert 0 <= y1 < y2 <= h

    def test_generate_batch_count(self) -> None:
        gen = SyntheticGUIGenerator(seed=2)
        batch = gen.generate_batch(n_images=10)
        assert len(batch) == 10

    def test_different_seeds_produce_different_results(self) -> None:
        gen_a = SyntheticGUIGenerator(seed=10)
        gen_b = SyntheticGUIGenerator(seed=99)
        _, ann_a = gen_a.generate(n_elements=4)
        _, ann_b = gen_b.generate(n_elements=4)
        bboxes_a = [a["bbox"] for a in ann_a]
        bboxes_b = [a["bbox"] for a in ann_b]
        assert bboxes_a != bboxes_b


# ---------------------------------------------------------------------------
# convert_rico_sample
# ---------------------------------------------------------------------------


class TestConvertRicoSample:
    def _make_sample(self, nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """테스트용 Rico 샘플 mock 생성."""
        from PIL import Image

        pil_img = Image.fromarray(np.zeros((960, 540, 3), dtype=np.uint8))
        ann_tree = {
            "class": "android.widget.FrameLayout",
            "bounds": [0, 0, 540, 960],
            "children": nodes,
        }
        return {
            "image": pil_img,
            "semantic_annotations": json.dumps(ann_tree),
        }

    def test_extracts_button_bbox(self) -> None:
        sample = self._make_sample(
            [
                {
                    "class": "android.widget.Button",
                    "bounds": [10, 20, 200, 80],
                    "children": [],
                }
            ]
        )
        img, ann = convert_rico_sample(sample)
        assert img is not None
        assert len(ann) == 1
        assert ann[0]["label"] == "button"
        assert ann[0]["bbox"] == [10, 20, 200, 80]

    def test_skips_unknown_class(self) -> None:
        sample = self._make_sample(
            [
                {
                    "class": "com.custom.UnknownWidget",
                    "bounds": [10, 20, 200, 80],
                    "children": [],
                }
            ]
        )
        _, ann = convert_rico_sample(sample)
        assert len(ann) == 0

    def test_skips_tiny_elements(self) -> None:
        sample = self._make_sample(
            [
                {
                    "class": "android.widget.Button",
                    "bounds": [10, 20, 25, 35],
                    "children": [],
                }
            ]
        )
        _, ann = convert_rico_sample(sample, min_box_size=20)
        assert len(ann) == 0

    def test_no_image_returns_empty(self) -> None:
        img, ann = convert_rico_sample({"image": None, "semantic_annotations": "{}"})
        assert img is None
        assert ann == []

    def test_invalid_json_returns_empty_annotations(self) -> None:
        from PIL import Image

        pil = Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8))
        img, ann = convert_rico_sample(
            {"image": pil, "semantic_annotations": "not-json"}
        )
        assert img is not None
        assert ann == []

    def test_multiple_classes(self) -> None:
        sample = self._make_sample(
            [
                {
                    "class": "android.widget.Button",
                    "bounds": [10, 20, 200, 80],
                    "children": [],
                },
                {
                    "class": "android.widget.TextView",
                    "bounds": [10, 100, 300, 140],
                    "children": [],
                },
                {
                    "class": "android.widget.ImageView",
                    "bounds": [10, 160, 100, 260],
                    "children": [],
                },
            ]
        )
        _, ann = convert_rico_sample(sample)
        labels = {a["label"] for a in ann}
        assert labels == {"button", "label", "icon"}


# ---------------------------------------------------------------------------
# split_train_val
# ---------------------------------------------------------------------------


class TestSplitTrainVal:
    def _make_dataset(self, tmp_path: Path, n: int) -> Path:
        """임시 데이터셋 디렉터리 생성."""
        from src.training.dataset_manager import DatasetManager

        dm = DatasetManager(data_root=tmp_path)
        gen = SyntheticGUIGenerator(seed=0)
        for i in range(n):
            img, ann = gen.generate(n_elements=4)
            dm.add_image_with_annotations(f"img_{i:03d}.png", img, ann)
        return tmp_path

    def test_split_creates_train_val_dirs(self, tmp_path: Path) -> None:
        ds = self._make_dataset(tmp_path, 10)
        train, val = split_train_val(ds, val_ratio=0.2)
        assert (train / "images").exists()
        assert (val / "images").exists()

    def test_split_ratio_approximate(self, tmp_path: Path) -> None:
        ds = self._make_dataset(tmp_path, 20)
        train, val = split_train_val(ds, val_ratio=0.2)
        n_train = len(list((train / "images").glob("*.png")))
        n_val = len(list((val / "images").glob("*.png")))
        assert n_train + n_val == 20
        assert n_val >= 2  # 최소 1개 이상

    def test_labels_copied_with_images(self, tmp_path: Path) -> None:
        ds = self._make_dataset(tmp_path, 10)
        train, val = split_train_val(ds)
        for split in (train, val):
            imgs = list((split / "images").glob("*.png"))
            for img_path in imgs:
                lbl = split / "labels" / f"{img_path.stem}.txt"
                assert lbl.exists()


# ---------------------------------------------------------------------------
# PretrainConfig
# ---------------------------------------------------------------------------


class TestPretrainConfig:
    def test_defaults(self) -> None:
        cfg = PretrainConfig()
        assert cfg.base_model == "yolo26x.pt"
        assert cfg.epochs == 20
        assert cfg.batch == 4
        assert cfg.val_ratio == 0.20
        assert cfg.device == "cpu"

    def test_custom_values(self) -> None:
        cfg = PretrainConfig(epochs=50, batch=8, device="cuda")
        assert cfg.epochs == 50
        assert cfg.batch == 8
        assert cfg.device == "cuda"


# ---------------------------------------------------------------------------
# PretrainPipeline (경량 목 테스트)
# ---------------------------------------------------------------------------


class TestPretrainPipelineSynthetic:
    def test_build_synthetic_creates_images(self, tmp_path: Path) -> None:
        pipeline = PretrainPipeline(output_dir=tmp_path)
        n = pipeline.build_synthetic_dataset(n_images=10)
        assert n == 10
        imgs = list((tmp_path / "images").glob("*.png"))
        assert len(imgs) == 10

    def test_prepare_dataset_yaml(self, tmp_path: Path) -> None:
        pipeline = PretrainPipeline(output_dir=tmp_path)
        pipeline.build_synthetic_dataset(n_images=10)
        yaml_path = pipeline.prepare_dataset_yaml()
        assert yaml_path.exists()
        content = yaml_path.read_text(encoding="utf-8")
        assert "nc: 7" in content
        assert "button" in content

    def test_save_report_creates_file(self, tmp_path: Path) -> None:
        pipeline = PretrainPipeline(output_dir=tmp_path)
        metrics = {
            "map50": 0.512,
            "map50_95": 0.321,
            "precision": 0.75,
            "recall": 0.68,
            "classes": {"button": 0.60, "icon": 0.52},
            "weights": "assets/models/yolo26x_pretrained.pt",
            "epochs": 20,
            "n_train": 160,
            "n_val": 40,
            "elapsed_sec": 300.0,
        }
        report = pipeline.save_report(metrics, path=tmp_path / "test_report.md")
        assert report.exists()
        text = report.read_text(encoding="utf-8")
        assert "mAP50" in text
        assert "0.5120" in text
        assert "button" in text

    def test_train_and_evaluate_with_mock(self, tmp_path: Path) -> None:
        """YOLO.train() / YOLO.val() 을 mock하여 전체 파이프라인 통과 검증."""
        # pretrained_weights를 tmp_path 안으로 격리 (실제 assets/ 오염 방지)
        cfg = PretrainConfig(
            output_dir=tmp_path,
            pretrained_weights=tmp_path / "yolo26x_pretrained.pt",
        )
        pipeline = PretrainPipeline(output_dir=tmp_path, config=cfg)
        pipeline.build_synthetic_dataset(n_images=10)

        # Mock ultralytics YOLO
        mock_train_result = MagicMock()
        mock_train_result.save_dir = tmp_path
        # best.pt 생성 (weights 서브디렉터리)
        weights_dir = tmp_path / "weights"
        weights_dir.mkdir(exist_ok=True)
        best_pt = weights_dir / "best.pt"
        best_pt.write_bytes(b"fake_weights")

        mock_val_result = MagicMock()
        mock_val_result.names = {
            i: PRETRAIN_CLASSES[i] for i in range(len(PRETRAIN_CLASSES))
        }
        mock_box = MagicMock()
        mock_box.map50 = 0.55
        mock_box.map = 0.35
        mock_box.mp = 0.72
        mock_box.mr = 0.65
        mock_box.ap50 = [0.60, 0.52, 0.58, 0.48, 0.50, 0.44, 0.46]
        mock_val_result.box = mock_box

        mock_yolo = MagicMock()
        mock_yolo.train.return_value = mock_train_result
        mock_yolo.val.return_value = mock_val_result

        with patch("ultralytics.YOLO", return_value=mock_yolo):
            metrics = pipeline.train_and_evaluate(epochs=2, batch=2)

        assert "map50" in metrics
        assert "precision" in metrics
        assert "recall" in metrics
        assert metrics["epochs"] == 2

    def test_extract_metrics_handles_missing_box(self, tmp_path: Path) -> None:
        """val() 결과에 box 속성이 없는 경우 기본값 반환."""
        pipeline = PretrainPipeline(output_dir=tmp_path)
        val_result = MagicMock()
        val_result.box = None

        metrics = pipeline._extract_metrics(
            val_result, elapsed=10.0, n_train=80, n_val=20, epochs=5
        )
        assert metrics["map50"] == 0.0
        assert metrics["precision"] == 0.0
        assert metrics["n_train"] == 80
        assert metrics["n_val"] == 20


# ---------------------------------------------------------------------------
# dataset.yaml 내용 검증
# ---------------------------------------------------------------------------


class TestDatasetYamlContent:
    def test_yaml_contains_all_pretrain_classes(self, tmp_path: Path) -> None:
        pipeline = PretrainPipeline(output_dir=tmp_path)
        pipeline.build_synthetic_dataset(n_images=5)
        yaml_path = pipeline.prepare_dataset_yaml()
        content = yaml_path.read_text(encoding="utf-8")
        for cls in PRETRAIN_CLASSES:
            assert cls in content

    def test_yaml_train_val_paths_exist(self, tmp_path: Path) -> None:
        pipeline = PretrainPipeline(output_dir=tmp_path)
        pipeline.build_synthetic_dataset(n_images=5)
        pipeline.prepare_dataset_yaml()
        assert (tmp_path / "train" / "images").exists()
        assert (tmp_path / "val" / "images").exists()
