"""
공통 pytest 픽스처 — 모든 테스트에서 사용하는 합성 데이터와 헬퍼.

실제 디스플레이, YOLO 가중치, LLM 없이도 동작한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# 이미지 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def dummy_screen_small() -> np.ndarray:
    """480×640 합성 BGR 이미지 (빠른 단위 테스트용)."""
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def dummy_screen_full() -> np.ndarray:
    """1080×1920 합성 BGR 이미지 (Full HD 라인 PC 기준)."""
    return np.zeros((1080, 1920, 3), dtype=np.uint8)


# ---------------------------------------------------------------------------
# 설정 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_config() -> dict[str, Any]:
    """최소 유효 config.json 딕셔너리."""
    return {
        "version": "1.0.0",
        "password": "test_password",
        "ocr_threshold": 0.75,
        "pin_count_min": None,
        "llm": {
            "enabled": False,
            "backend": "llama_cpp",
            "model_path": None,
            "ctx_size": 4096,
            "gpu_layers": 0,
            "http_url": None,
            "max_input_tokens": 4096,
            "max_output_tokens": 512,
        },
    }


@pytest.fixture
def config_file(tmp_path: Path, sample_config: dict[str, Any]) -> Path:
    """임시 config.json 파일 경로."""
    p = tmp_path / "config.json"
    p.write_text(json.dumps(sample_config), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# 이벤트 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_events() -> list[dict[str, Any]]:
    """테스트용 구조화 이벤트 리스트 (INFO 2개 + ERROR 2개)."""
    return [
        {
            "ts": "2026-01-01T00:00:00.000000Z",
            "level": "INFO",
            "step": "login",
            "message": "clicked login_button",
            "data": {},
        },
        {
            "ts": "2026-01-01T00:00:01.000000Z",
            "level": "ERROR",
            "step": "login",
            "message": "target not found",
            "data": {},
        },
        {
            "ts": "2026-01-01T00:00:02.000000Z",
            "level": "ERROR",
            "step": "mold_left_roi",
            "message": "drag timeout",
            "data": {},
        },
        {
            "ts": "2026-01-01T00:00:03.000000Z",
            "level": "INFO",
            "step": "save",
            "message": "saved",
            "data": {},
        },
    ]


# ---------------------------------------------------------------------------
# LLM 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm_response() -> dict[str, Any]:
    """LLM analyze_logs() 반환값 형태의 더미 딕셔너리."""
    return {
        "config_patch": {"ocr_threshold": 0.8, "vision.confidence_threshold": 0.6},
        "sop_recommendations": ["ROI 좌표 재조정 권장", "재시도 횟수를 3 → 5로 늘리세요"],
        "raw_text": "Analysis complete. Two issues detected.",
    }
