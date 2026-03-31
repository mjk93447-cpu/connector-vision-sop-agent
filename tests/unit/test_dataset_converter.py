"""tests/unit/test_dataset_converter.py — v4.1.1 OLEDConnectorGenerator 개선 테스트.

Tests:
  TestOLEDConnectorGeneratorV4Enhancements:
    - test_background_noise_produces_variation
    - test_grayscale_invariant_preserved_after_enhancements
    - test_pin_shapes_include_non_rectangle
"""

from __future__ import annotations


class TestOLEDConnectorGeneratorV4Enhancements:
    """v4.1.1 추가 기능: Gaussian noise, blur, 핀 형상 다양화 검증."""

    def test_background_noise_produces_variation(self) -> None:
        """배경 픽셀에 변동이 있어야 한다 (Gaussian noise 적용 확인)."""
        import numpy as np

        from src.training.dataset_converter import OLEDConnectorGenerator

        gen = OLEDConnectorGenerator()
        found_variation = False
        for _ in range(20):
            img, _ = gen.generate(width=320, height=240)
            # 좌상단 20×20 패치 (핀/몰드 없는 배경 영역)
            patch = img[:20, :20, 0].astype(np.int32)
            if patch.max() - patch.min() > 0:
                found_variation = True
                break
        assert found_variation, "배경 픽셀에 변동 없음 — Gaussian noise 미적용"

    def test_grayscale_invariant_preserved_after_enhancements(self) -> None:
        """R==G==B 불변식은 노이즈+블러 추가 후에도 유지되어야 한다."""
        from src.training.dataset_converter import OLEDConnectorGenerator

        gen = OLEDConnectorGenerator()
        for _ in range(15):
            img, _ = gen.generate(width=320, height=240)
            assert (
                img[:, :, 0] == img[:, :, 1]
            ).all(), "R != G (v4.1.1 개선 후 그레이스케일 불변식 깨짐)"
            assert (
                img[:, :, 1] == img[:, :, 2]
            ).all(), "G != B (v4.1.1 개선 후 그레이스케일 불변식 깨짐)"

    def test_pin_shapes_include_non_rectangle(self) -> None:
        """round / narrow 핀 형상 코드 경로가 예외 없이 실행된다.

        random.choice를 mock 으로 고정하여 각 형상 경로를 강제 실행.
        """
        import random
        from unittest.mock import patch

        import numpy as np

        from src.training.dataset_converter import OLEDConnectorGenerator

        gen = OLEDConnectorGenerator()
        for shape in ("round", "narrow"):
            with patch.object(random, "choice", return_value=shape):
                img, labels = gen.generate(width=320, height=240)
            assert isinstance(img, np.ndarray), f"generate() 실패 — shape={shape!r}"
            assert img.shape == (
                240,
                320,
                3,
            ), f"잘못된 이미지 shape — pin shape={shape!r}"
