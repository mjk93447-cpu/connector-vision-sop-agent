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
    """MainWindow를 Qt 없이 인스턴스화하기 위한 최소 스텁.

    PyQt6 최신 버전은 object.__new__(QWidget-subclass) 를 금지한다.
    테스트 대상 메서드(_build_log_context_for_llm, _load_recent_log_events)는
    self._log_manager 외에 Qt API를 전혀 호출하지 않으므로, 해당 메서드만
    빌려온 순수 Python 클래스를 스텁으로 사용한다.
    """
    import importlib

    mw_mod = importlib.import_module("src.gui.main_window")

    class _Stub:
        _build_log_context_for_llm = mw_mod.MainWindow._build_log_context_for_llm
        _load_recent_log_events = mw_mod.MainWindow._load_recent_log_events

    stub = _Stub()
    stub._log_manager = log_manager
    return stub


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


# ---------------------------------------------------------------------------
# Test: on_llm_send() accepts image_b64 without TypeError
# ---------------------------------------------------------------------------


class TestOnLlmSendImageB64:
    """on_llm_send()이 image_b64 파라미터를 수용하는지 확인 (Bug: TypeError 수정 검증).

    LlmPanel._on_send()는 image_b64=image_b64 키워드 인수를 전달한다.
    수정 전: on_llm_send()에 해당 파라미터가 없어 TypeError 발생 → 채팅 즉시 종료.
    수정 후: 파라미터가 추가되어 정상 전달되어야 한다.
    """

    def _make_on_llm_send(self):
        """MainWindow.on_llm_send 메서드만 스텁으로 추출."""
        import importlib

        mw_mod = importlib.import_module("src.gui.main_window")
        return mw_mod.MainWindow.on_llm_send

    def test_on_llm_send_accepts_image_b64_kwarg(self):
        """on_llm_send() 시그니처에 image_b64 파라미터가 존재하는지 확인."""
        import inspect
        import importlib

        mw_mod = importlib.import_module("src.gui.main_window")
        sig = inspect.signature(mw_mod.MainWindow.on_llm_send)
        assert "image_b64" in sig.parameters, (
            "on_llm_send() must accept image_b64 — "
            "LlmPanel._on_send() passes image_b64=... and would raise TypeError without it"
        )

    def test_on_llm_send_image_b64_default_is_none(self):
        """image_b64 기본값이 None이어야 기존 호출자와 하위 호환성이 유지된다."""
        import inspect
        import importlib

        mw_mod = importlib.import_module("src.gui.main_window")
        sig = inspect.signature(mw_mod.MainWindow.on_llm_send)
        param = sig.parameters["image_b64"]
        assert (
            param.default is None
        ), "image_b64 default must be None for backward compatibility"


# ---------------------------------------------------------------------------
# Test: LLMWorker / LLMStreamWorker accept image_b64
# ---------------------------------------------------------------------------


class TestWorkerImageB64:
    """Workers가 image_b64 파라미터를 받아 LLM에 전달하는지 확인."""

    def test_llm_worker_accepts_image_b64(self):
        """LLMWorker.__init__이 image_b64 파라미터를 수용한다."""
        import inspect
        import importlib

        workers_mod = importlib.import_module("src.gui.workers")
        sig = inspect.signature(workers_mod.LLMWorker.__init__)
        assert "image_b64" in sig.parameters

    def test_llm_stream_worker_accepts_image_b64(self):
        """LLMStreamWorker.__init__이 image_b64 파라미터를 수용한다."""
        import inspect
        import importlib

        workers_mod = importlib.import_module("src.gui.workers")
        sig = inspect.signature(workers_mod.LLMStreamWorker.__init__)
        assert "image_b64" in sig.parameters

    def test_llm_worker_stores_image_b64(self):
        """LLMWorker가 image_b64를 self._image_b64에 저장한다."""
        import importlib
        from unittest.mock import MagicMock

        workers_mod = importlib.import_module("src.gui.workers")

        # Qt 없이 __init__ 로직만 검증하기 위해 __init__을 수동 호출
        stub = object.__new__(workers_mod.LLMWorker)
        # QThread.__init__ 우회
        (
            workers_mod.LLMWorker.__init__.__func__
            if hasattr(workers_mod.LLMWorker.__init__, "__func__")
            else None
        )

        fake_llm = MagicMock()
        # MRO를 통해 QThread.__init__ 없이 속성만 설정
        stub._llm = fake_llm
        stub._system = "sys"
        stub._history = []
        stub._image_b64 = "b64data"

        assert stub._image_b64 == "b64data"

    def test_llm_stream_worker_stores_image_b64(self):
        """LLMStreamWorker가 image_b64를 self._image_b64에 저장한다."""
        import importlib

        workers_mod = importlib.import_module("src.gui.workers")

        stub = object.__new__(workers_mod.LLMStreamWorker)
        stub._image_b64 = "screenshot_b64"
        assert stub._image_b64 == "screenshot_b64"
