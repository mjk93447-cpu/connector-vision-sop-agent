"""
MainWindow._build_log_context_for_llm / _load_recent_log_events 단위 테스트.

테스트 대상:
  - 로그 없을 때 빈 문자열 반환
  - in-memory events 주입
  - 파일시스템 폴백 (events.jsonl 파싱)
  - 예외 발생 시 빈 문자열 반환 (방어 로직)
"""

from __future__ import annotations

import json
import types
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Helpers: Minimal MainWindow stub (no Qt required)
# ---------------------------------------------------------------------------


def _make_window(log_manager=None):
    """MainWindow를 Qt 없이 인스턴스화하기 위한 최소 스텁."""
    import importlib

    mw_mod = importlib.import_module("src.gui.main_window")
    mw = object.__new__(mw_mod.MainWindow)
    mw._log_manager = log_manager
    return mw


def _make_log_event(level: str, step: str, message: str):
    """LogEvent dataclass 대용 SimpleNamespace."""
    return types.SimpleNamespace(level=level, step=step, message=message)


# ---------------------------------------------------------------------------
# Test: _build_log_context_for_llm
# ---------------------------------------------------------------------------


class TestBuildLogContextForLlm:
    def test_no_log_manager_returns_empty(self, tmp_path, monkeypatch):
        """_log_manager=None + logs/ 없는 환경 → 빈 문자열 반환."""
        monkeypatch.chdir(tmp_path)  # 실제 logs/ 디렉터리 폴백 차단
        mw = _make_window(log_manager=None)
        result = mw._build_log_context_for_llm()
        assert result == ""

    def test_empty_events_returns_empty(self, tmp_path, monkeypatch):
        """events 빈 리스트 + logs/ 없는 환경 → 빈 문자열 반환."""
        monkeypatch.chdir(tmp_path)  # 실제 logs/ 디렉터리 폴백 차단
        log_mgr = MagicMock()
        log_mgr.events = []
        mw = _make_window(log_manager=log_mgr)
        result = mw._build_log_context_for_llm()
        assert result == ""

    def test_inmemory_events_injected(self):
        """in-memory LogEvent 목록이 RECENT ISSUES 형태로 포함된다."""
        log_mgr = MagicMock()
        log_mgr.events = [
            _make_log_event("ERROR", "login", "login_button not found"),
            _make_log_event("INFO", "image_source", "click OK"),
            _make_log_event("WARNING", "in_pin_up", "pin count 18 < expected 20"),
        ]
        # run_dir / summary.json 없는 경우 처리
        run_dir_mock = MagicMock()
        summary_path_mock = MagicMock()
        summary_path_mock.exists.return_value = False
        run_dir_mock.__truediv__ = lambda self, other: summary_path_mock
        log_mgr.run_dir = run_dir_mock

        mw = _make_window(log_manager=log_mgr)
        result = mw._build_log_context_for_llm()

        assert result.startswith("RECENT ISSUES:")
        assert "login_button not found" in result
        assert "⚠[in_pin_up]" in result  # WARNING → ⚠ prefix
        assert "·[image_source]" in result  # INFO → · prefix

    def test_exception_in_build_returns_empty(self):
        """내부 예외가 발생해도 빈 문자열 반환 (절대 raise 하지 않음)."""
        log_mgr = MagicMock()
        # events 프로퍼티 접근 시 예외 발생 시뮬레이션
        type(log_mgr).events = property(
            lambda s: (_ for _ in ()).throw(RuntimeError("boom"))
        )
        mw = _make_window(log_manager=log_mgr)
        result = mw._build_log_context_for_llm()
        assert result == ""


# ---------------------------------------------------------------------------
# Test: _load_recent_log_events
# ---------------------------------------------------------------------------


class TestLoadRecentLogEvents:
    def test_returns_empty_when_logs_dir_missing(self, tmp_path, monkeypatch):
        """logs/ 디렉터리 없으면 빈 리스트 반환."""
        monkeypatch.chdir(tmp_path)
        mw = _make_window()
        result = mw._load_recent_log_events()
        assert result == []

    def test_parses_events_jsonl(self, tmp_path, monkeypatch):
        """events.jsonl 을 올바르게 파싱해 level/step/message 반환."""
        monkeypatch.chdir(tmp_path)
        run_dir = tmp_path / "logs" / "20260324T120000Z_run-1"
        run_dir.mkdir(parents=True)
        events_file = run_dir / "events.jsonl"
        lines = [
            json.dumps({"ts": "t1", "level": "INFO", "step": "login", "message": "OK"}),
            json.dumps(
                {"ts": "t2", "level": "ERROR", "step": "save", "message": "fail"}
            ),
            json.dumps(
                {
                    "ts": "t3",
                    "level": "WARNING",
                    "step": "in_pin_up",
                    "message": "low count",
                }
            ),
        ]
        events_file.write_text("\n".join(lines), encoding="utf-8")

        mw = _make_window()
        result = mw._load_recent_log_events(max_events=10)

        assert len(result) == 3
        assert result[0].level == "INFO"
        assert result[0].step == "login"
        assert result[1].level == "ERROR"
        assert result[2].message == "low count"
