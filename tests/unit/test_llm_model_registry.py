from __future__ import annotations

import pytest

from src.llm_model_registry import (
    get_capability,
    is_local_offline_model,
    recommend_sop_generation_tag,
    validate_sop_generation_model,
)


def test_qwen37_not_local_offline() -> None:
    cap = get_capability("qwen3.7")
    assert cap is not None
    assert cap.local_offline is False


def test_kimi_cloud_not_local_offline() -> None:
    assert is_local_offline_model("kimi-k2.6:cloud") is False
    with pytest.raises(RuntimeError):
        validate_sop_generation_model("kimi-k2.6:cloud")


def test_recommend_sop_generation_for_16gb() -> None:
    assert recommend_sop_generation_tag(ram_gb=16) == "qwen3:8b"
    assert recommend_sop_generation_tag(ram_gb=8, lite=True) == "qwen3:4b"
