from __future__ import annotations

from pathlib import Path


def test_start_pretrain_bat_validates_blank_input() -> None:
    content = Path("assets/launchers/start_pretrain.bat").read_text(encoding="utf-8")
    assert "DEFAULT_EPOCHS=40" in content
    assert "DEFAULT_BATCH=16" in content
    assert "findstr /r" in content
    assert "if defined USER_EPOCHS" in content
    assert "if defined USER_BATCH" in content
    assert "PRETRAIN_ARGS" in content
