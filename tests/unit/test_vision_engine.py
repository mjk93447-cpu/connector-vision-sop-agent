"""
vision_engine 단위 테스트 — CP-3.

VisionEngine 단일 클래스 (VisionAgent 병합), YOLO26x 기본 모델.
CP-3: Tesseract 완전 제거 반영 — ocr_psm 필드, similarity, OCR 메서드 테스트 삭제.

mock 전략:
- VisionEngine._load_model → None (실제 가중치 로드 없음)
- engine.detect_objects  → MagicMock 반환 (YOLO inference 우회)
- engine.extract_pin_centers → MagicMock (blob 개수 제어)
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.model_artifacts import LOCAL_PRETRAIN_MODEL_NAME
from src.vision_engine import (
    DEFAULT_MOLD_ROI,
    DEFAULT_TARGET_LABELS,
    DetectionConfig,
    UiDetection,
    VisionEngine,
)


# ---------------------------------------------------------------------------
# 공통 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def engine() -> VisionEngine:
    """YOLO 로드 없이 생성된 VisionEngine (헤드리스)."""
    with patch.object(VisionEngine, "_load_model", return_value=None):
        e = VisionEngine()
    return e


@pytest.fixture
def blank_small() -> np.ndarray:
    return np.zeros((100, 100, 3), dtype=np.uint8)


@pytest.fixture
def blank_with_blobs() -> np.ndarray:
    """밝은 사각형 블롭 5개를 가진 합성 이미지 (핀 시뮬레이션)."""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    for i in range(5):
        x, y = 50 + i * 60, 100
        img[y : y + 10, x : x + 10] = 255
    return img


@pytest.fixture
def mock_model_with_detection() -> MagicMock:
    """login_button 하나를 반환하는 YOLO 모델 Mock."""
    mock_box = MagicMock()
    mock_box.xyxy = [MagicMock()]
    mock_box.xyxy[
        0
    ].cpu.return_value.numpy.return_value.astype.return_value.tolist.return_value = [
        10,
        20,
        50,
        60,
    ]
    mock_box.cls = [MagicMock()]
    mock_box.cls[0].item.return_value = 0
    mock_box.conf = [MagicMock()]
    mock_box.conf[0].item.return_value = 0.85

    mock_result = MagicMock()
    mock_result.names = {0: "login_button"}
    mock_result.boxes = [mock_box]

    mock_model = MagicMock()
    mock_model.predict.return_value = [mock_result]
    return mock_model


# ---------------------------------------------------------------------------
# DetectionConfig
# ---------------------------------------------------------------------------


class TestDetectionConfig:
    def test_default_model_path_is_yolo26x(self) -> None:
        """CP-2: 기본 모델이 yolo26x로 변경되었는지 확인."""
        cfg = DetectionConfig()
        assert cfg.model_path.endswith(f"assets/models/{LOCAL_PRETRAIN_MODEL_NAME}")

    def test_default_confidence_threshold(self) -> None:
        cfg = DetectionConfig()
        assert cfg.confidence_threshold == 0.6

    def test_custom_model_path(self) -> None:
        cfg = DetectionConfig(model_path="assets/models/custom.pt")
        assert cfg.model_path == "assets/models/custom.pt"

    def test_custom_confidence_threshold(self) -> None:
        cfg = DetectionConfig(confidence_threshold=0.8)
        assert cfg.confidence_threshold == 0.8


# ---------------------------------------------------------------------------
# VisionEngine 생성 / 경로 해석
# ---------------------------------------------------------------------------


class TestVisionEngineConstruction:
    def test_creates_instance_with_default_config(self) -> None:
        with patch.object(VisionEngine, "_load_model", return_value=None):
            e = VisionEngine()
        assert isinstance(e, VisionEngine)

    def test_default_config_has_yolo26x_model(self) -> None:
        with patch.object(VisionEngine, "_load_model", return_value=None):
            e = VisionEngine()
        assert e.config.model_path.endswith(f"assets/models/{LOCAL_PRETRAIN_MODEL_NAME}")

    def test_custom_config_stored(self) -> None:
        cfg = DetectionConfig(confidence_threshold=0.9)
        with patch.object(VisionEngine, "_load_model", return_value=None):
            e = VisionEngine(config=cfg)
        assert e.config.confidence_threshold == 0.9

    def test_model_is_none_when_path_missing(self, engine: VisionEngine) -> None:
        assert engine.model is None

    def test_model_path_resolved_to_absolute(self, engine: VisionEngine) -> None:
        assert os.path.isabs(engine.model_path)

    def test_absolute_path_not_modified(self) -> None:
        cfg = DetectionConfig(model_path="/absolute/path/model.pt")
        with patch.object(VisionEngine, "_load_model", return_value=None):
            e = VisionEngine(config=cfg)
        assert e.model_path == "/absolute/path/model.pt"

    def test_no_config_uses_defaults(self, engine: VisionEngine) -> None:
        assert engine.config is not None
        assert engine.config.confidence_threshold == 0.6

    def test_reload_model_updates_path_and_config(self) -> None:
        cfg = DetectionConfig(model_path="assets/models/original.pt")
        original_model = object()
        reloaded_model = object()

        with patch.object(VisionEngine, "_load_model", return_value=original_model):
            engine = VisionEngine(config=cfg)

        with patch.object(VisionEngine, "_load_model", return_value=reloaded_model):
            ok = engine.reload_model("assets/models/fine_tuned.pt")

        assert ok is True
        assert engine.model is reloaded_model
        assert engine.model_path.replace("\\", "/").endswith("assets/models/fine_tuned.pt")
        assert cfg.model_path.replace("\\", "/").endswith("assets/models/fine_tuned.pt")

    def test_reload_model_preserves_existing_model_on_failure(self) -> None:
        original_model = object()

        with patch.object(VisionEngine, "_load_model", return_value=original_model):
            engine = VisionEngine()

        original_path = engine.model_path

        with patch.object(VisionEngine, "_load_model", return_value=None):
            ok = engine.reload_model("assets/models/missing.pt")

        assert ok is False
        assert engine.model is original_model
        assert engine.model_path == original_path


# ---------------------------------------------------------------------------
# _to_gray
# ---------------------------------------------------------------------------


class TestToGray:
    def test_grayscale_image_returned_as_copy(self) -> None:
        gray = np.zeros((10, 10), dtype=np.uint8)
        result = VisionEngine._to_gray(gray)
        assert result.shape == (10, 10)
        assert result.ndim == 2

    def test_bgr_converted_to_grayscale(self) -> None:
        bgr = np.zeros((10, 10, 3), dtype=np.uint8)
        result = VisionEngine._to_gray(bgr)
        assert result.ndim == 2
        assert result.shape == (10, 10)

    def test_does_not_modify_original(self) -> None:
        original = np.full((5, 5), 128, dtype=np.uint8)
        VisionEngine._to_gray(original)
        assert original[0, 0] == 128


# ---------------------------------------------------------------------------
# detect_objects
# ---------------------------------------------------------------------------


class TestDetectObjects:
    def test_returns_empty_when_model_none(
        self, engine: VisionEngine, blank_small: np.ndarray
    ) -> None:
        assert engine.model is None
        result = engine.detect_objects(blank_small)
        assert result == []

    def test_returns_detections_from_mock_model(
        self, blank_small: np.ndarray, mock_model_with_detection: MagicMock
    ) -> None:
        with patch.object(
            VisionEngine, "_load_model", return_value=mock_model_with_detection
        ):
            e = VisionEngine()
        detections = e.detect_objects(blank_small)
        assert len(detections) == 1
        assert detections[0].label == "login_button"
        assert detections[0].confidence == pytest.approx(0.85)
        assert detections[0].bbox == (10, 20, 50, 60)

    def test_conf_threshold_from_config_used_by_default(
        self, blank_small: np.ndarray, mock_model_with_detection: MagicMock
    ) -> None:
        cfg = DetectionConfig(confidence_threshold=0.75)
        with patch.object(
            VisionEngine, "_load_model", return_value=mock_model_with_detection
        ):
            e = VisionEngine(config=cfg)
        e.detect_objects(blank_small)
        call_kwargs = mock_model_with_detection.predict.call_args[1]
        assert call_kwargs["conf"] == pytest.approx(0.75)

    def test_custom_conf_threshold_overrides_config(
        self, blank_small: np.ndarray, mock_model_with_detection: MagicMock
    ) -> None:
        with patch.object(
            VisionEngine, "_load_model", return_value=mock_model_with_detection
        ):
            e = VisionEngine()
        e.detect_objects(blank_small, conf_threshold=0.5)
        call_kwargs = mock_model_with_detection.predict.call_args[1]
        assert call_kwargs["conf"] == pytest.approx(0.5)

    def test_result_with_no_boxes_skipped(self, blank_small: np.ndarray) -> None:
        mock_result = MagicMock()
        mock_result.names = {0: "x"}
        mock_result.boxes = None  # no boxes attribute

        mock_model = MagicMock()
        mock_model.predict.return_value = [mock_result]

        with patch.object(VisionEngine, "_load_model", return_value=mock_model):
            e = VisionEngine()
        detections = e.detect_objects(blank_small)
        assert detections == []


# ---------------------------------------------------------------------------
# find_detection
# ---------------------------------------------------------------------------


class TestFindDetection:
    def test_returns_none_when_model_none(
        self, engine: VisionEngine, blank_small: np.ndarray
    ) -> None:
        assert engine.find_detection(blank_small, "login_button") is None

    def test_returns_highest_confidence_match(
        self, engine: VisionEngine, blank_small: np.ndarray
    ) -> None:
        detections = [
            UiDetection(label="login_button", confidence=0.7, bbox=(0, 0, 10, 10)),
            UiDetection(label="login_button", confidence=0.9, bbox=(20, 20, 30, 30)),
        ]
        with patch.object(engine, "detect_objects", return_value=detections):
            result = engine.find_detection(blank_small, "login_button")
        assert result is not None
        assert result.confidence == pytest.approx(0.9)

    def test_returns_none_for_missing_label(
        self, engine: VisionEngine, blank_small: np.ndarray
    ) -> None:
        detections = [
            UiDetection(label="recipe_button", confidence=0.8, bbox=(0, 0, 10, 10))
        ]
        with patch.object(engine, "detect_objects", return_value=detections):
            result = engine.find_detection(blank_small, "login_button")
        assert result is None

    def test_uses_config_confidence_as_threshold(self, blank_small: np.ndarray) -> None:
        cfg = DetectionConfig(confidence_threshold=0.8)
        with patch.object(VisionEngine, "_load_model", return_value=None):
            e = VisionEngine(config=cfg)
        with patch.object(e, "detect_objects", return_value=[]) as mock_detect:
            e.find_detection(blank_small, "login_button")
        call_kwargs = mock_detect.call_args[1]
        assert call_kwargs.get("conf_threshold") == pytest.approx(0.8)

    def test_find_detection_without_roi_uses_detect_objects(
        self, engine: VisionEngine, blank_small: np.ndarray
    ) -> None:
        """roi=None → detect_objects called, detect_roi NOT called."""
        with patch.object(
            engine, "detect_objects", return_value=[]
        ) as mock_do, patch.object(engine, "detect_roi") as mock_dr:
            engine.find_detection(blank_small, "login_button")
        mock_do.assert_called_once()
        mock_dr.assert_not_called()

    def test_find_detection_with_roi_uses_detect_roi(
        self, engine: VisionEngine, blank_small: np.ndarray
    ) -> None:
        """roi given → detect_roi called, detect_objects NOT called."""
        roi = (10, 10, 50, 50)
        with patch.object(
            engine, "detect_roi", return_value=[]
        ) as mock_dr, patch.object(engine, "detect_objects") as mock_do:
            engine.find_detection(blank_small, "login_button", roi=roi)
        mock_dr.assert_called_once()
        mock_do.assert_not_called()

    def test_find_detection_with_roi_filters_label(
        self, engine: VisionEngine, blank_small: np.ndarray
    ) -> None:
        """When roi given, only detections matching the requested label returned."""
        roi = (0, 0, 100, 100)
        detections = [
            UiDetection(label="login_button", confidence=0.9, bbox=(5, 5, 40, 40)),
            UiDetection(label="recipe_button", confidence=0.8, bbox=(50, 50, 90, 90)),
        ]
        with patch.object(engine, "detect_roi", return_value=detections):
            result = engine.find_detection(blank_small, "login_button", roi=roi)
        assert result is not None
        assert result.label == "login_button"
        assert result.confidence == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# normalize_roi
# ---------------------------------------------------------------------------


class TestNormalizeRoi:
    def test_normalizes_reversed_corners(self) -> None:
        start, end = VisionEngine.normalize_roi((800, 350), (100, 200))
        assert start == (100, 200)
        assert end == (800, 350)

    def test_already_normalized_unchanged(self) -> None:
        start, end = VisionEngine.normalize_roi((100, 200), (800, 350))
        assert start == (100, 200)
        assert end == (800, 350)

    def test_default_is_default_mold_roi(self) -> None:
        start, end = VisionEngine.normalize_roi()
        assert start == DEFAULT_MOLD_ROI[0]
        assert end == DEFAULT_MOLD_ROI[1]

    def test_x_normalized_independently_of_y(self) -> None:
        start, end = VisionEngine.normalize_roi((900, 50), (100, 400))
        assert start == (100, 50)
        assert end == (900, 400)


# ---------------------------------------------------------------------------
# extract_pin_centers / validate_pin_count
# ---------------------------------------------------------------------------


class TestExtractPinCenters:
    def test_blank_image_returns_list(
        self, engine: VisionEngine, blank_small: np.ndarray
    ) -> None:
        centers = engine.extract_pin_centers(blank_small)
        assert isinstance(centers, list)

    def test_returns_list_of_two_tuples(
        self, engine: VisionEngine, blank_with_blobs: np.ndarray
    ) -> None:
        centers = engine.extract_pin_centers(blank_with_blobs)
        assert all(isinstance(c, tuple) and len(c) == 2 for c in centers)

    def test_blobs_detected_in_blob_image(
        self, engine: VisionEngine, blank_with_blobs: np.ndarray
    ) -> None:
        centers = engine.extract_pin_centers(blank_with_blobs)
        assert len(centers) >= 1

    def test_sorted_by_row_then_col(
        self, engine: VisionEngine, blank_with_blobs: np.ndarray
    ) -> None:
        centers = engine.extract_pin_centers(blank_with_blobs)
        for a, b in zip(centers, centers[1:]):
            assert (a[1], a[0]) <= (b[1], b[0])

    def test_grayscale_input_handled(self, engine: VisionEngine) -> None:
        gray = np.zeros((100, 100), dtype=np.uint8)
        centers = engine.extract_pin_centers(gray)
        assert isinstance(centers, list)


class TestValidatePinCount:
    def test_result_has_required_keys(
        self, engine: VisionEngine, blank_small: np.ndarray
    ) -> None:
        result = engine.validate_pin_count(blank_small)
        assert {"count", "pin_count_min", "valid", "centers"}.issubset(result.keys())

    def test_valid_when_count_meets_minimum(self, engine: VisionEngine) -> None:
        pins = [(i, 0) for i in range(20)]
        with patch.object(engine, "extract_pin_centers", return_value=pins):
            result = engine.validate_pin_count(
                np.zeros((10, 10, 3), dtype=np.uint8), pin_count_min=20
            )
        assert result["valid"] is True
        assert result["count"] == 20

    def test_invalid_when_count_below_minimum(self, engine: VisionEngine) -> None:
        pins = [(0, 0)] * 5
        with patch.object(engine, "extract_pin_centers", return_value=pins):
            result = engine.validate_pin_count(
                np.zeros((10, 10, 3), dtype=np.uint8), pin_count_min=20
            )
        assert result["valid"] is False

    def test_pin_count_min_stored_in_result(self, engine: VisionEngine) -> None:
        with patch.object(engine, "extract_pin_centers", return_value=[]):
            result = engine.validate_pin_count(
                np.zeros((10, 10, 3), dtype=np.uint8), pin_count_min=40
            )
        assert result["pin_count_min"] == 40


# ---------------------------------------------------------------------------
# detect_ui_targets
# ---------------------------------------------------------------------------


class TestDetectUiTargets:
    def test_returns_defaults_when_image_none(self, engine: VisionEngine) -> None:
        result = engine.detect_ui_targets(None)
        assert result == DEFAULT_TARGET_LABELS

    def test_returns_defaults_when_no_detections(
        self, engine: VisionEngine, blank_small: np.ndarray
    ) -> None:
        # engine.model is None → detect_objects returns []
        result = engine.detect_ui_targets(blank_small)
        assert result == DEFAULT_TARGET_LABELS

    def test_returns_detected_labels_in_order(
        self, engine: VisionEngine, blank_small: np.ndarray
    ) -> None:
        detections = [
            UiDetection(label="login_button", confidence=0.9, bbox=(0, 0, 10, 10)),
            UiDetection(label="recipe_button", confidence=0.8, bbox=(10, 10, 20, 20)),
        ]
        with patch.object(engine, "detect_objects", return_value=detections):
            result = engine.detect_ui_targets(blank_small)
        assert result[0] == "login_button"
        assert result[1] == "recipe_button"

    def test_no_duplicate_labels_in_result(
        self, engine: VisionEngine, blank_small: np.ndarray
    ) -> None:
        detections = [
            UiDetection(label="login_button", confidence=0.9, bbox=(0, 0, 10, 10)),
            UiDetection(label="login_button", confidence=0.7, bbox=(10, 10, 20, 20)),
        ]
        with patch.object(engine, "detect_objects", return_value=detections):
            result = engine.detect_ui_targets(blank_small)
        assert result.count("login_button") == 1

    def test_returns_copy_not_original(self, engine: VisionEngine) -> None:
        result = engine.detect_ui_targets(None)
        result.append("extra")
        assert "extra" not in engine.detect_ui_targets(None)
