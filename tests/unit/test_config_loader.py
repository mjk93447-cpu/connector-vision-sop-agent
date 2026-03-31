"""
config_loader 단위 테스트.

실제 assets/config.json 로딩과 임시 파일 기반 경계값 테스트,
PyInstaller EXE 환경 경로 해석 테스트를 포함한다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from src.config_loader import (
    _resolve_config_path,
    detect_local_accelerator,
    load_config,
    resolve_app_path,
    resolve_existing_app_path,
    suggest_training_profile,
)


class TestLoadConfigValid:
    def test_returns_dict(self, config_file: Path) -> None:
        result = load_config(config_file)
        assert isinstance(result, dict)

    def test_reads_version(self, config_file: Path) -> None:
        result = load_config(config_file)
        assert "version" in result

    def test_reads_llm_block(self, config_file: Path) -> None:
        result = load_config(config_file)
        assert "llm" in result

    def test_unicode_password(self, tmp_path: Path) -> None:
        """한국어 비밀번호가 UTF-8로 정상 로딩되는지 확인."""
        cfg = {"version": "2.0.0", "password": "라인비번"}
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

    def test_default_config_llm_block(self) -> None:
        """v2.0.0 config: llm 블록에 backend/model_path 존재 확인."""
        result = load_config()
        llm = result.get("llm", {})
        assert "backend" in llm
        assert "model_path" in llm

    def test_default_config_vision_block(self) -> None:
        """v2.0.0 config: vision 블록 존재 확인."""
        result = load_config()
        assert "vision" in result
        assert "model_path" in result["vision"]


class TestResolveConfigPath:
    """_resolve_config_path 경로 해석 로직 단위 테스트."""

    def test_absolute_existing_path_returned_as_is(self, config_file: Path) -> None:
        """절대 경로이고 파일이 존재하면 그대로 반환."""
        result = _resolve_config_path(config_file)
        assert result == config_file

    def test_cwd_relative_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CWD 기준 상대 경로로 찾을 수 있을 때."""
        cfg = tmp_path / "assets" / "config.json"
        cfg.parent.mkdir(parents=True)
        cfg.write_text('{"version":"2.0.0"}', encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        result = _resolve_config_path(Path("assets/config.json"))
        assert result.exists()

    def test_frozen_exe_dir_takes_priority(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PyInstaller frozen 환경에서 exe_dir/assets/config.json 가 최우선."""
        exe_dir = tmp_path / "exe_location"
        exe_dir.mkdir()
        cfg_in_exe = exe_dir / "assets" / "config.json"
        cfg_in_exe.parent.mkdir(parents=True)
        cfg_in_exe.write_text('{"version":"portable"}', encoding="utf-8")

        # sys.frozen = True, sys.executable = exe_dir/connector_vision_agent.exe
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(
            sys,
            "executable",
            str(exe_dir / "connector_vision_agent.exe"),
            raising=False,
        )

        result = _resolve_config_path(Path("assets/config.json"))
        assert result == cfg_in_exe

    def test_frozen_meipass_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """exe_dir에 없을 때 _MEIPASS 번들 내 경로로 fallback."""
        meipass_dir = tmp_path / "meipass"
        meipass_dir.mkdir()
        cfg_in_meipass = meipass_dir / "assets" / "config.json"
        cfg_in_meipass.parent.mkdir(parents=True)
        cfg_in_meipass.write_text('{"version":"bundled"}', encoding="utf-8")

        exe_dir = tmp_path / "exe_dir_empty"
        exe_dir.mkdir()

        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(
            sys,
            "executable",
            str(exe_dir / "connector_vision_agent.exe"),
            raising=False,
        )
        monkeypatch.setattr(sys, "_MEIPASS", str(meipass_dir), raising=False)
        # CWD에도 파일 없음 → _MEIPASS 에서 찾아야 함
        monkeypatch.chdir(tmp_path)

        result = _resolve_config_path(Path("assets/config.json"))
        assert result == cfg_in_meipass


class TestRuntimePathHelpers:
    def test_resolve_app_path_prefers_exe_dir_when_frozen(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        exe_dir = tmp_path / "exe"
        exe_dir.mkdir()
        target = exe_dir / "assets" / "config.json"
        target.parent.mkdir(parents=True)
        target.write_text("{}", encoding="utf-8")

        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(
            sys,
            "executable",
            str(exe_dir / "connector_vision_agent.exe"),
            raising=False,
        )
        result = resolve_app_path("assets/config.json")
        assert result == target

    def test_resolve_existing_app_path_returns_first_existing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("src.config_loader.get_base_dir", lambda: tmp_path)
        second = tmp_path / "pretrain_data_test"
        second.mkdir()
        result = resolve_existing_app_path("pretrain_data", "pretrain_data_test")
        assert result == second

    def test_suggest_training_profile_returns_cpu_defaults(self) -> None:
        profile = suggest_training_profile(image_count=120)
        assert profile["epochs"] >= 4
        assert profile["batch"] >= 1
        assert profile["image_size"] in {320, 640}
        assert profile["device"] in {"cpu", 0}


class TestAcceleratorDetection:
    def test_detect_local_accelerator_uses_nvidia_smi_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _Result:
            stdout = "NVIDIA RTX 4000 Ada Generation, 20480\n"

        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **k: _Result(),
        )
        monkeypatch.setitem(sys.modules, "torch", None)

        accel = detect_local_accelerator()
        assert accel["gpu_present"] is True
        assert accel["memory_gb"] == pytest.approx(20.0)
        assert "RTX" in str(accel["name"])
