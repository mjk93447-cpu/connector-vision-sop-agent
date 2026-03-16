"""
config_loader 단위 테스트.

실제 assets/config.json 로딩과 임시 파일 기반 경계값 테스트를 포함한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.config_loader import load_config


class TestLoadConfigValid:
    def test_returns_dict(self, config_file: Path) -> None:
        result = load_config(config_file)
        assert isinstance(result, dict)

    def test_reads_version(self, config_file: Path) -> None:
        result = load_config(config_file)
        assert result["version"] == "1.0.0"

    def test_reads_llm_block(self, config_file: Path) -> None:
        result = load_config(config_file)
        assert "llm" in result
        assert result["llm"]["backend"] == "llama_cpp"

    def test_unicode_password(self, tmp_path: Path) -> None:
        """한국어 비밀번호가 UTF-8로 정상 로딩되는지 확인."""
        cfg = {"version": "1.0.0", "password": "라인비번"}
        p = tmp_path / "config.json"
        p.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        result = load_config(p)
        assert result["password"] == "라인비번"

    def test_accepts_pathlib_path(self, config_file: Path) -> None:
        result = load_config(config_file)
        assert result is not None

    def test_accepts_string_path(self, config_file: Path) -> None:
        result = load_config(str(config_file))
        assert result is not None


class TestLoadConfigErrors:
    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.json")

    def test_invalid_json_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.json"
        p.write_text("{ invalid json }", encoding="utf-8")
        with pytest.raises(Exception):
            load_config(p)

    def test_empty_file_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.json"
        p.write_text("", encoding="utf-8")
        with pytest.raises(Exception):
            load_config(p)


class TestLoadConfigDefaultPath:
    def test_default_assets_config_exists(self) -> None:
        """assets/config.json이 존재하고 로딩되는지 확인."""
        result = load_config()
        assert isinstance(result, dict)
        assert "version" in result
        assert "llm" in result

    def test_default_config_has_required_keys(self) -> None:
        result = load_config()
        required_keys = {"version", "password", "llm"}
        assert required_keys.issubset(result.keys())
