from __future__ import annotations

from pathlib import Path


def test_requirements_common_excludes_pretrain_only_packages() -> None:
    text = Path("requirements-common.txt").read_text(encoding="utf-8")
    assert "datasets>=" not in text
    assert "huggingface_hub>=" not in text


def test_requirements_pretrain_contains_pretrain_only_packages() -> None:
    text = Path("requirements-pretrain.txt").read_text(encoding="utf-8")
    assert "datasets>=" in text
    assert "huggingface_hub>=" in text
