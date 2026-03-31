"""tests/unit/test_train_config.py — OLED 학습 설정 및 OLEDConnectorGenerator 테스트."""

from __future__ import annotations


class TestOledTrainParams:
    """OLED_TRAIN_PARAMS / OLED_PRETRAIN_PARAMS 내용 검증."""

    def test_grayscale_params(self) -> None:
        """흑백 이미지 특성 — hsv_h, hsv_s 반드시 0.0."""
        from src.training.train_config import OLED_TRAIN_PARAMS

        assert OLED_TRAIN_PARAMS["hsv_h"] == 0.0, "hsv_h must be 0 for grayscale"
        assert OLED_TRAIN_PARAMS["hsv_s"] == 0.0, "hsv_s must be 0 for grayscale"

    def test_no_flip(self) -> None:
        """핀 방향 고정 — fliplr 반드시 0.0."""
        from src.training.train_config import OLED_TRAIN_PARAMS

        assert (
            OLED_TRAIN_PARAMS["fliplr"] == 0.0
        ), "fliplr must be 0 (pin direction fixed)"

    def test_pretrain_params_extends_base(self) -> None:
        """OLED_PRETRAIN_PARAMS 는 OLED_TRAIN_PARAMS 의 모든 키를 포함해야 한다."""
        from src.training.train_config import OLED_PRETRAIN_PARAMS, OLED_TRAIN_PARAMS

        for key in OLED_TRAIN_PARAMS:
            assert (
                key in OLED_PRETRAIN_PARAMS
            ), f"OLED_PRETRAIN_PARAMS missing key: {key!r}"

    def test_no_seg_params(self) -> None:
        """detection 전용 — overlap_mask / mask_ratio 없어야 한다."""
        from src.training.train_config import OLED_PRETRAIN_PARAMS, OLED_TRAIN_PARAMS

        for params, name in [
            (OLED_TRAIN_PARAMS, "OLED_TRAIN_PARAMS"),
            (OLED_PRETRAIN_PARAMS, "OLED_PRETRAIN_PARAMS"),
        ]:
            assert (
                "overlap_mask" not in params
            ), f"{name} must not have overlap_mask (seg-only)"
            assert (
                "mask_ratio" not in params
            ), f"{name} must not have mask_ratio (seg-only)"


class TestOLEDConnectorGenerator:
    """OLEDConnectorGenerator 합성 이미지 생성 테스트."""

    def test_generate_returns_image_and_labels(self) -> None:
        """generate() 는 (ndarray, list) 를 반환해야 한다."""
        import numpy as np

        from src.training.dataset_converter import OLEDConnectorGenerator

        gen = OLEDConnectorGenerator()
        img, labels = gen.generate(width=320, height=240)
        assert isinstance(img, np.ndarray)
        assert img.shape == (240, 320, 3)
        assert isinstance(labels, list)

    def test_image_is_grayscale_range(self) -> None:
        """생성 이미지는 3채널이지만 R==G==B (그레이스케일)여야 한다."""
        from src.training.dataset_converter import OLEDConnectorGenerator

        gen = OLEDConnectorGenerator()
        img, _ = gen.generate(width=320, height=240)
        assert (img[:, :, 0] == img[:, :, 1]).all(), "R != G (not grayscale)"
        assert (img[:, :, 1] == img[:, :, 2]).all(), "G != B (not grayscale)"

    def test_pin_labels_within_image(self) -> None:
        """모든 bbox 좌표는 [0, 1] 범위 내에 있어야 한다."""
        from src.training.dataset_converter import OLEDConnectorGenerator

        gen = OLEDConnectorGenerator()
        for _ in range(10):
            _, labels = gen.generate(width=640, height=480)
            for ann in labels:
                _cls, cx, cy, w, h = ann
                assert 0.0 <= cx <= 1.0, f"cx={cx} out of range"
                assert 0.0 <= cy <= 1.0, f"cy={cy} out of range"
                assert 0.0 < w <= 1.0, f"w={w} out of range"
                assert 0.0 < h <= 1.0, f"h={h} out of range"

    def test_batch_generates_n_images(self) -> None:
        """generate_batch(n) 는 정확히 n 개의 (img, labels) 를 반환해야 한다."""
        from src.training.dataset_converter import OLEDConnectorGenerator

        gen = OLEDConnectorGenerator()
        batch = gen.generate_batch(n_images=5, width=320, height=240)
        assert len(batch) == 5
        for img, labels in batch:
            assert img is not None
            assert isinstance(labels, list)


class TestOledTrainParamsV4Geometric:
    """v4.1.1: OLED_TRAIN_PARAMS 기하학 증강 키 검증."""

    def test_degrees_present_and_nonzero(self) -> None:
        from src.training.train_config import OLED_TRAIN_PARAMS

        assert "degrees" in OLED_TRAIN_PARAMS, "degrees 키 누락"
        assert OLED_TRAIN_PARAMS["degrees"] > 0, "degrees 는 양수여야 한다"

    def test_erasing_present(self) -> None:
        from src.training.train_config import OLED_TRAIN_PARAMS

        assert "erasing" in OLED_TRAIN_PARAMS, "erasing 키 누락"

    def test_pretrain_gentler_degrees(self) -> None:
        """OLED_PRETRAIN_PARAMS 의 degrees ≤ OLED_TRAIN_PARAMS 의 degrees."""
        from src.training.train_config import OLED_PRETRAIN_PARAMS, OLED_TRAIN_PARAMS

        assert (
            OLED_PRETRAIN_PARAMS["degrees"] <= OLED_TRAIN_PARAMS["degrees"]
        ), "pretrain degrees 가 train degrees 보다 크면 안 된다"
