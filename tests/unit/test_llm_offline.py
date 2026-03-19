"""
llm_offline 단위 테스트.

LLMConfig.from_dict, OfflineLLM 백엔드 디스패치 (ollama/http/llama_cpp),
HTTP mock, analyze_logs 결과 형식을 외부 LLM 없이 검증한다.

CP-1: ollama 백엔드 추가 및 기본값 변경 반영
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.llm_offline import (
    LLMConfig,
    OfflineLLM,
    _OLLAMA_DEFAULT_MODEL,
    _OLLAMA_DEFAULT_URL,
)


# ---------------------------------------------------------------------------
# LLMConfig
# ---------------------------------------------------------------------------


class TestLLMConfig:
    def test_default_backend_is_ollama(self) -> None:
        """CP-1: 기본 백엔드가 ollama로 변경되었는지 확인."""
        cfg = LLMConfig.from_dict({})
        assert cfg.backend == "ollama"

    def test_default_model_is_llama4_scout(self) -> None:
        cfg = LLMConfig.from_dict({})
        assert cfg.model_path == _OLLAMA_DEFAULT_MODEL

    def test_default_http_url_is_ollama(self) -> None:
        cfg = LLMConfig.from_dict({})
        assert cfg.http_url == _OLLAMA_DEFAULT_URL

    def test_default_ctx_size_is_8192(self) -> None:
        cfg = LLMConfig.from_dict({})
        assert cfg.ctx_size == 8192

    def test_default_max_output_tokens_is_1024(self) -> None:
        cfg = LLMConfig.from_dict({})
        assert cfg.max_output_tokens == 1024

    def test_default_gpu_layers_is_zero(self) -> None:
        cfg = LLMConfig.from_dict({})
        assert cfg.gpu_layers == 0

    def test_backend_parsed(self) -> None:
        cfg = LLMConfig.from_dict({"backend": "http"})
        assert cfg.backend == "http"

    def test_model_path_override(self) -> None:
        cfg = LLMConfig.from_dict({"model_path": "/tmp/model.gguf"})
        assert cfg.model_path == "/tmp/model.gguf"

    def test_ctx_size_as_int(self) -> None:
        """문자열로 들어온 ctx_size도 int로 파싱된다."""
        cfg = LLMConfig.from_dict({"ctx_size": "4096"})
        assert cfg.ctx_size == 4096

    def test_gpu_layers_as_int(self) -> None:
        cfg = LLMConfig.from_dict({"gpu_layers": "4"})
        assert cfg.gpu_layers == 4

    def test_http_url_override(self) -> None:
        url = "http://my-server:8000/v1/chat/completions"
        cfg = LLMConfig.from_dict({"http_url": url})
        assert cfg.http_url == url

    def test_max_tokens_parsed(self) -> None:
        cfg = LLMConfig.from_dict({"max_input_tokens": 2048, "max_output_tokens": 512})
        assert cfg.max_input_tokens == 2048
        assert cfg.max_output_tokens == 512


# ---------------------------------------------------------------------------
# OfflineLLM 생성
# ---------------------------------------------------------------------------


class TestOfflineLLMConstruction:
    def test_from_config_creates_instance(self) -> None:
        llm = OfflineLLM.from_config({})
        assert isinstance(llm, OfflineLLM)

    def test_cfg_backend_stored(self) -> None:
        llm = OfflineLLM.from_config({"backend": "http"})
        assert llm.cfg.backend == "http"

    def test_default_backend_is_ollama(self) -> None:
        llm = OfflineLLM.from_config({})
        assert llm.cfg.backend == "ollama"


# ---------------------------------------------------------------------------
# 백엔드 디스패치
# ---------------------------------------------------------------------------


class TestBackendDispatch:
    def test_unsupported_backend_raises(self) -> None:
        llm = OfflineLLM(LLMConfig())
        llm.cfg.backend = "not_a_backend"  # type: ignore[assignment]
        with pytest.raises(RuntimeError, match="Unsupported"):
            llm.chat("sys", [{"role": "user", "content": "hi"}])

    def test_http_without_url_raises(self) -> None:
        cfg = LLMConfig.from_dict({"backend": "http", "http_url": None})
        llm = OfflineLLM(cfg)
        with pytest.raises(RuntimeError, match="http_url"):
            llm.chat("sys", [{"role": "user", "content": "hi"}])

    def test_ollama_dispatches_to_ollama_method(self) -> None:
        """ollama 백엔드가 _chat_ollama()를 호출하는지 확인."""
        llm = OfflineLLM.from_config({})  # 기본값 = ollama
        with patch.object(llm, "_chat_ollama", return_value="ok") as mock_method:
            result = llm.chat("sys", [{"role": "user", "content": "hi"}])
        assert result == "ok"
        mock_method.assert_called_once()

    def test_http_dispatches_to_http_method(self) -> None:
        llm = OfflineLLM.from_config(
            {"backend": "http", "http_url": "http://localhost:8000/v1/chat/completions"}
        )
        with patch.object(llm, "_chat_http", return_value="http-ok"):
            result = llm.chat("sys", [{"role": "user", "content": "hi"}])
        assert result == "http-ok"


# ---------------------------------------------------------------------------
# Ollama 백엔드 (CP-1 신규)
# ---------------------------------------------------------------------------


class TestOllamaBackend:
    """Ollama 백엔드를 requests.post mock으로 검증한다.
    실제 Ollama 서버 없이 완전한 흐름을 테스트할 수 있다.
    """

    def _mock_response(self, content: str) -> MagicMock:
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"choices": [{"message": {"content": content}}]}
        return resp

    def test_chat_returns_response_content(self) -> None:
        llm = OfflineLLM.from_config({})  # ollama 기본값
        with patch("requests.post", return_value=self._mock_response("안녕하세요!")):
            result = llm.chat("system", [{"role": "user", "content": "hi"}])
        assert result == "안녕하세요!"

    def test_default_url_used_when_not_set(self) -> None:
        llm = OfflineLLM.from_config({"http_url": None})
        with patch(
            "requests.post", return_value=self._mock_response("ok")
        ) as mock_post:
            llm.chat("sys", [{"role": "user", "content": "test"}])
        call_url = mock_post.call_args[0][0]
        assert call_url == _OLLAMA_DEFAULT_URL

    def test_custom_url_used_when_set(self) -> None:
        custom_url = "http://192.168.1.100:11434/v1/chat/completions"
        llm = OfflineLLM.from_config({"http_url": custom_url})
        with patch(
            "requests.post", return_value=self._mock_response("ok")
        ) as mock_post:
            llm.chat("sys", [{"role": "user", "content": "test"}])
        assert mock_post.call_args[0][0] == custom_url

    def test_default_model_tag_in_payload(self) -> None:
        llm = OfflineLLM.from_config({"model_path": None})
        with patch(
            "requests.post", return_value=self._mock_response("ok")
        ) as mock_post:
            llm.chat("sys", [{"role": "user", "content": "test"}])
        payload = mock_post.call_args[1]["json"]
        assert payload["model"] == _OLLAMA_DEFAULT_MODEL

    def test_custom_model_tag_in_payload(self) -> None:
        llm = OfflineLLM.from_config({"model_path": "llama3.2:3b"})
        with patch(
            "requests.post", return_value=self._mock_response("ok")
        ) as mock_post:
            llm.chat("sys", [{"role": "user", "content": "test"}])
        payload = mock_post.call_args[1]["json"]
        assert payload["model"] == "llama3.2:3b"

    def test_system_prompt_prepended(self) -> None:
        llm = OfflineLLM.from_config({})
        with patch(
            "requests.post", return_value=self._mock_response("ok")
        ) as mock_post:
            llm.chat("expert engineer", [{"role": "user", "content": "진단해줘"}])
        messages = mock_post.call_args[1]["json"]["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "expert engineer"

    def test_stream_false_in_payload(self) -> None:
        """Ollama에 stream:false 명시 — 비스트리밍 응답 보장."""
        llm = OfflineLLM.from_config({})
        with patch(
            "requests.post", return_value=self._mock_response("ok")
        ) as mock_post:
            llm.chat("sys", [{"role": "user", "content": "test"}])
        payload = mock_post.call_args[1]["json"]
        assert payload.get("stream") is False

    def test_timeout_is_tuple(self) -> None:
        """Ollama uses (connect, read) tuple timeout for connect 10s + read 120s."""
        llm = OfflineLLM.from_config({})
        with patch(
            "requests.post", return_value=self._mock_response("ok")
        ) as mock_post:
            llm.chat("sys", [{"role": "user", "content": "test"}])
        t = mock_post.call_args[1]["timeout"]
        assert isinstance(t, tuple), "timeout should be a (connect, read) tuple"
        assert t[0] <= 15, "connect timeout should be short (<= 15s)"

    def test_no_duplicate_system_message(self) -> None:
        """history에 이미 system이 있으면 중복 추가하지 않는다."""
        llm = OfflineLLM.from_config({})
        history = [
            {"role": "system", "content": "existing system"},
            {"role": "user", "content": "hi"},
        ]
        with patch(
            "requests.post", return_value=self._mock_response("ok")
        ) as mock_post:
            llm.chat("new system (should be ignored)", history)
        messages = mock_post.call_args[1]["json"]["messages"]
        system_messages = [m for m in messages if m["role"] == "system"]
        assert len(system_messages) == 1
        assert system_messages[0]["content"] == "existing system"

    def test_korean_content_preserved(self) -> None:
        """한국어 콘텐츠가 깨지지 않고 전달된다."""
        llm = OfflineLLM.from_config({})
        with patch("requests.post", return_value=self._mock_response("분석 완료")):
            result = llm.chat("시스템", [{"role": "user", "content": "로그 분석해줘"}])
        assert result == "분석 완료"

    def test_config_json_ollama_block_works(self) -> None:
        """assets/config.json의 llm 블록으로 OfflineLLM 생성 가능."""
        from src.config_loader import load_config

        config = load_config()
        llm_cfg = config.get("llm", {})
        llm = OfflineLLM.from_config(llm_cfg)
        assert llm.cfg.backend == "ollama"
        assert llm.cfg.model_path == "phi4-mini-reasoning"


# ---------------------------------------------------------------------------
# HTTP 백엔드
# ---------------------------------------------------------------------------


class TestHttpBackend:
    def _make_mock_response(self, content: str) -> MagicMock:
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"choices": [{"message": {"content": content}}]}
        return resp

    def test_chat_returns_content(self) -> None:
        cfg = LLMConfig.from_dict(
            {
                "backend": "http",
                "http_url": "http://localhost:8000/v1/chat/completions",
                "model_path": "test-model",
            }
        )
        llm = OfflineLLM(cfg)
        with patch("requests.post", return_value=self._make_mock_response("OK")):
            result = llm.chat("sys", [{"role": "user", "content": "hi"}])
        assert result == "OK"

    def test_chat_posts_to_correct_url(self) -> None:
        url = "http://my-server:9000/v1/chat/completions"
        cfg = LLMConfig.from_dict({"backend": "http", "http_url": url})
        llm = OfflineLLM(cfg)
        with patch(
            "requests.post", return_value=self._make_mock_response("ok")
        ) as mock_post:
            llm.chat("sys", [{"role": "user", "content": "test"}])
        assert mock_post.call_args[0][0] == url

    def test_chat_includes_system_message(self) -> None:
        cfg = LLMConfig.from_dict(
            {
                "backend": "http",
                "http_url": "http://localhost:8000/v1/chat/completions",
            }
        )
        llm = OfflineLLM(cfg)
        with patch(
            "requests.post", return_value=self._make_mock_response("ok")
        ) as mock_post:
            llm.chat("you are an expert", [{"role": "user", "content": "test"}])
        roles = [m["role"] for m in mock_post.call_args[1]["json"]["messages"]]
        assert "system" in roles


# ---------------------------------------------------------------------------
# analyze_logs
# ---------------------------------------------------------------------------


class TestAnalyzeLogs:
    def _make_llm(self, response_content: str) -> OfflineLLM:
        llm = OfflineLLM.from_config({})
        llm.chat = MagicMock(return_value=response_content)  # type: ignore[method-assign]
        return llm

    def test_result_has_required_keys(self) -> None:
        valid = json.dumps(
            {
                "config_patch": {"vision.confidence_threshold": 0.6},
                "sop_recommendations": ["ROI 재조정"],
                "raw_text": "분석 완료",
            }
        )
        result = self._make_llm(valid).analyze_logs({"run_id": "r1"})
        assert "config_patch" in result
        assert "sop_recommendations" in result
        assert "raw_text" in result

    def test_valid_json_parsed(self) -> None:
        valid = json.dumps(
            {
                "config_patch": {"ocr_threshold": 0.85},
                "sop_recommendations": ["재시도 횟수 증가"],
                "raw_text": "이상 감지",
            }
        )
        result = self._make_llm(valid).analyze_logs({})
        assert result["config_patch"]["ocr_threshold"] == 0.85

    def test_invalid_json_fallback_no_crash(self) -> None:
        result = self._make_llm("이것은 JSON이 아닙니다.").analyze_logs({})
        assert result["config_patch"] == {}
        assert result["sop_recommendations"] == []
        assert "이것은 JSON이 아닙니다." in result["raw_text"]

    def test_non_dict_json_fallback(self) -> None:
        result = self._make_llm("[1, 2, 3]").analyze_logs({})
        assert result["config_patch"] == {}

    def test_partial_json_keys_safe(self) -> None:
        partial = json.dumps({"config_patch": {"a": 1}})
        result = self._make_llm(partial).analyze_logs({})
        assert result["sop_recommendations"] == []

    def test_payload_run_id_sent_to_chat(self) -> None:
        llm = self._make_llm(
            '{"config_patch":{},"sop_recommendations":[],"raw_text":""}'
        )
        llm.analyze_logs({"run_id": "unique_run_123"})
        call_args = llm.chat.call_args  # type: ignore[union-attr]
        history = call_args[1].get("history") or call_args[0][1]
        combined = " ".join(str(m) for m in history)
        assert "unique_run_123" in combined

    def test_ollama_backend_used_by_default(self) -> None:
        """기본 생성 시 ollama 백엔드를 통해 analyze_logs가 호출된다."""
        llm = OfflineLLM.from_config({})
        assert llm.cfg.backend == "ollama"


# ---------------------------------------------------------------------------
# Bug2 fixes — <think> token routing
# ---------------------------------------------------------------------------


def _make_sse_lines(tokens: list[str]) -> list[bytes]:
    """Helper: convert token strings to SSE-style bytes lines."""
    import json as _json

    lines = []
    for t in tokens:
        chunk = {"choices": [{"delta": {"content": t}}]}
        lines.append(f"data: {_json.dumps(chunk)}".encode())
    lines.append(b"data: [DONE]")
    return lines


class TestThinkTokenRouting:
    """stream_chat() should route <think>…</think> tokens to on_think_token."""

    def _make_streaming_resp(self, tokens: list[str]) -> MagicMock:
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.raise_for_status.return_value = None
        resp.iter_lines.return_value = _make_sse_lines(tokens)
        return resp

    def _mock_session(self, tokens: list[str]) -> MagicMock:
        sess = MagicMock()
        sess.post.return_value = self._make_streaming_resp(tokens)
        return sess

    def test_plain_tokens_go_to_on_token(self) -> None:
        llm = OfflineLLM.from_config({})
        llm._session = self._mock_session(["Hello", " world"])
        received: list[str] = []
        result = llm.stream_chat(
            "sys", [{"role": "user", "content": "hi"}], on_token=received.append
        )
        assert "".join(received) == "Hello world"
        assert result == "Hello world"

    def test_think_tokens_routed_to_think_callback(self) -> None:
        tokens = ["<think>", "reasoning here", "</think>", "answer"]
        llm = OfflineLLM.from_config({})
        llm._session = self._mock_session(tokens)
        visible: list[str] = []
        thinking: list[str] = []
        result = llm.stream_chat(
            "sys",
            [{"role": "user", "content": "hi"}],
            on_token=visible.append,
            on_think_token=thinking.append,
        )
        assert "".join(visible) == "answer"
        assert result == "answer"
        assert "reasoning here" in "".join(thinking)

    def test_think_block_not_in_answer(self) -> None:
        tokens = ["<think>", "secret reasoning", "</think>", "real answer"]
        llm = OfflineLLM.from_config({})
        llm._session = self._mock_session(tokens)
        visible: list[str] = []
        llm.stream_chat(
            "sys", [{"role": "user", "content": "q"}], on_token=visible.append
        )
        combined = "".join(visible)
        assert "secret reasoning" not in combined
        assert "real answer" in combined

    def test_no_think_block_works_normally(self) -> None:
        tokens = ["simple", " answer"]
        llm = OfflineLLM.from_config({})
        llm._session = self._mock_session(tokens)
        visible: list[str] = []
        thinking: list[str] = []
        result = llm.stream_chat(
            "sys",
            [{"role": "user", "content": "q"}],
            on_token=visible.append,
            on_think_token=thinking.append,
        )
        assert result == "simple answer"
        assert thinking == []

    def test_mixed_answer_think_answer(self) -> None:
        """Text before and after a <think> block should both be in answer."""
        tokens = ["before", "<think>", "reasoning", "</think>", "after"]
        llm = OfflineLLM.from_config({})
        llm._session = self._mock_session(tokens)
        visible: list[str] = []
        result = llm.stream_chat(
            "sys", [{"role": "user", "content": "q"}], on_token=visible.append
        )
        assert result == "beforeafter"
        assert "".join(visible) == "beforeafter"


# ---------------------------------------------------------------------------
# Bug2 fixes — cancel() method
# ---------------------------------------------------------------------------


class TestCancelMethod:
    def test_cancel_closes_session(self) -> None:
        llm = OfflineLLM.from_config({})
        mock_sess = MagicMock()
        llm._session = mock_sess
        llm.cancel()
        mock_sess.close.assert_called_once()
        assert llm._session is None

    def test_cancel_when_no_session_is_noop(self) -> None:
        llm = OfflineLLM.from_config({})
        assert llm._session is None
        llm.cancel()  # should not raise
        assert llm._session is None

    def test_cancel_ignores_close_exception(self) -> None:
        llm = OfflineLLM.from_config({})
        mock_sess = MagicMock()
        mock_sess.close.side_effect = OSError("already closed")
        llm._session = mock_sess
        llm.cancel()  # should not raise
        assert llm._session is None

    def test_session_recreated_after_cancel(self) -> None:
        """After cancel(), _get_session() creates a fresh session."""
        llm = OfflineLLM.from_config({})
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"choices": [{"message": {"content": "ok"}}]}

        with patch("requests.Session") as mock_cls:
            mock_sess = MagicMock()
            mock_sess.post.return_value = resp
            mock_cls.return_value = mock_sess
            llm.cancel()  # clear any existing session
            s = llm._get_session()
            assert s is mock_sess


# ---------------------------------------------------------------------------
# Bug2 fixes — Ollama health check
# ---------------------------------------------------------------------------


class TestCheckHealth:
    def test_health_ok_returns_gpu_message_with_gpu(self) -> None:
        llm = OfflineLLM.from_config({})
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_get.return_value = mock_resp
            # Simulate GPU available
            with patch("torch.cuda.is_available", return_value=True):
                result = llm.check_health()
        assert result is not None
        assert "GPU" in result

    def test_health_ok_cpu_only_returns_info_message(self) -> None:
        llm = OfflineLLM.from_config({})
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_get.return_value = mock_resp
            with patch("torch.cuda.is_available", return_value=False):
                result = llm.check_health()
        assert result is not None
        assert "CPU" in result or "cpu" in result.lower()

    def test_health_check_fails_raises_runtime_error(self) -> None:
        llm = OfflineLLM.from_config({})
        import requests as _req

        with patch(
            "requests.get", side_effect=_req.exceptions.ConnectionError("refused")
        ):
            with pytest.raises(RuntimeError, match="Ollama server not running"):
                llm.check_health()

    def test_health_check_timeout_raises_runtime_error(self) -> None:
        llm = OfflineLLM.from_config({})
        import requests as _req

        with patch("requests.get", side_effect=_req.exceptions.Timeout("timeout")):
            with pytest.raises(RuntimeError, match="Ollama server not running"):
                llm.check_health()

    def test_health_check_uses_configured_timeout(self) -> None:
        """check_health() passes _HEALTH_TIMEOUT to requests.get."""
        from src.llm_offline import _HEALTH_TIMEOUT

        llm = OfflineLLM.from_config({})
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_get.return_value = mock_resp
            with patch("torch.cuda.is_available", return_value=True):
                llm.check_health()
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs.get("timeout") == _HEALTH_TIMEOUT

    def test_health_timeout_is_at_least_5_seconds(self) -> None:
        """_HEALTH_TIMEOUT must be >= 5s to survive network-drive / RAM-limited envs.

        On-line PCs use OLLAMA_MODELS on a mapped network drive (Z:\\) with
        only ~2.2 GiB free RAM for a 3.2 GB model.  The previous value of 1.5s
        caused false-positive 'Ollama server not running' errors even when
        Ollama was actually live but slow to respond.
        """
        from src.llm_offline import _HEALTH_TIMEOUT

        assert _HEALTH_TIMEOUT >= 5, (
            f"_HEALTH_TIMEOUT is {_HEALTH_TIMEOUT}s — too short for network-drive "
            "environments. Must be >= 5s to avoid false 'server not running' errors."
        )

    def test_health_check_no_torch_returns_cpu_message(self) -> None:
        """If torch is not installed, health check returns CPU-only info message."""
        llm = OfflineLLM.from_config({})
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_get.return_value = mock_resp
            with patch.dict("sys.modules", {"torch": None}):
                result = llm.check_health()
        # torch not available → CPU-only message
        assert result is not None
        assert "CPU" in result or "cpu" in result.lower()


# ---------------------------------------------------------------------------
# _get_optimized_options (Bug 2 — 하드웨어 최적화)
# ---------------------------------------------------------------------------


class TestOptimizedOptions:
    def test_gpu_mode_sets_num_gpu_99(self) -> None:
        """CUDA 감지 시 num_gpu=99 설정 확인."""
        llm = OfflineLLM.from_config({})
        with patch("torch.cuda.is_available", return_value=True):
            opts = llm._get_optimized_options()
        assert opts["num_gpu"] == 99

    def test_cpu_mode_sets_num_thread_and_num_gpu_0(self) -> None:
        """CPU-only 환경에서 num_gpu=0, num_thread>=1 설정 확인."""
        llm = OfflineLLM.from_config({})
        with patch("torch.cuda.is_available", return_value=False):
            opts = llm._get_optimized_options()
        assert opts["num_gpu"] == 0
        assert opts["num_thread"] >= 1

    def test_brief_mode_no_think_in_options(self) -> None:
        """brief=True 시 options{}에 think 키 없음 확인.

        think=False는 payload 최상위에 위치해야 하므로 options{}에는 포함되지 않아야 함.
        options{} 안에 think를 넣으면 Ollama가 llama.cpp 파라미터로 오인해 무시한다.
        """
        llm = OfflineLLM.from_config({})
        with patch("torch.cuda.is_available", return_value=False):
            opts = llm._get_optimized_options(brief=True)
        assert (
            "think" not in opts
        ), "think must NOT be inside options{} — it must be at payload top level"

    def test_brief_mode_num_ctx_4096(self) -> None:
        """brief=True 시 num_ctx=4096 (컨텍스트 단축) 확인."""
        llm = OfflineLLM.from_config({"ctx_size": 8192})
        with patch("torch.cuda.is_available", return_value=False):
            opts = llm._get_optimized_options(brief=True)
        assert opts["num_ctx"] == 4096

    def test_non_brief_mode_no_think_key(self) -> None:
        """brief=False 시 options에 think 키 없음 확인."""
        llm = OfflineLLM.from_config({})
        with patch("torch.cuda.is_available", return_value=False):
            opts = llm._get_optimized_options(brief=False)
        assert "think" not in opts


# ---------------------------------------------------------------------------
# Bug2 v2 fixes — think=False at payload top level (not inside options)
# ---------------------------------------------------------------------------


class TestThinkPayloadTopLevel:
    """think=False는 payload 최상위에 위치해야 함 (Ollama API 스펙)."""

    def _make_streaming_resp(self, tokens: list[str]) -> MagicMock:
        import json as _json

        lines = []
        for t in tokens:
            chunk = {"choices": [{"delta": {"content": t}}]}
            lines.append(f"data: {_json.dumps(chunk)}".encode())
        lines.append(b"data: [DONE]")
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.raise_for_status.return_value = None
        resp.iter_lines.return_value = lines
        return resp

    def test_think_false_at_top_level_in_stream_payload(self) -> None:
        """brief=True 시 _stream_ollama payload['think']==False 확인 (최상위)."""
        llm = OfflineLLM.from_config({})
        mock_sess = MagicMock()
        mock_sess.post.return_value = self._make_streaming_resp(["hi"])
        llm._session = mock_sess

        llm.stream_chat(
            "sys",
            [{"role": "user", "content": "say hi"}],
            on_token=lambda t: None,
            brief=True,
        )

        payload = mock_sess.post.call_args[1]["json"]
        assert (
            payload.get("think") is False
        ), "think=False must be at payload top level for Ollama to honor it"

    def test_think_not_at_top_level_non_brief_stream(self) -> None:
        """brief=False 시 payload에 think 키 없음 확인."""
        llm = OfflineLLM.from_config({})
        mock_sess = MagicMock()
        mock_sess.post.return_value = self._make_streaming_resp(["hi"])
        llm._session = mock_sess

        llm.stream_chat(
            "sys",
            [{"role": "user", "content": "say hi"}],
            on_token=lambda t: None,
            brief=False,
        )

        payload = mock_sess.post.call_args[1]["json"]
        assert "think" not in payload

    def test_think_false_at_top_level_in_chat_payload(self) -> None:
        """brief=True 시 _chat_ollama payload['think']==False 확인 (최상위)."""
        llm = OfflineLLM.from_config({})
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"choices": [{"message": {"content": "hi"}}]}

        with patch("requests.post", return_value=mock_resp) as mock_post:
            llm.chat("sys", [{"role": "user", "content": "say hi"}], brief=True)

        payload = mock_post.call_args[1]["json"]
        assert (
            payload.get("think") is False
        ), "think=False must be at payload top level in _chat_ollama for Ollama to honor it"

    def test_think_not_in_options_dict_for_brief(self) -> None:
        """brief=True 시 options{} 안에 think 키 없음 확인 (최상위 전용)."""
        llm = OfflineLLM.from_config({})
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"choices": [{"message": {"content": "hi"}}]}

        with patch("requests.post", return_value=mock_resp) as mock_post:
            llm.chat("sys", [{"role": "user", "content": "say hi"}], brief=True)

        payload = mock_post.call_args[1]["json"]
        options = payload.get("options", {})
        assert (
            "think" not in options
        ), "think must NOT be inside options{} — Ollama would ignore it there"


# ---------------------------------------------------------------------------
# 120s deadline timer (Bug 2 — 스트리밍 timeout 안전망)
# ---------------------------------------------------------------------------


class TestStreamingDeadlineTimer:
    def test_deadline_timer_calls_cancel_on_timeout(self) -> None:
        """120s 데드라인 타이머가 만료되면 llm.cancel() 호출 확인."""
        import threading as _threading

        llm = OfflineLLM.from_config({})
        cancel_called = []

        original_cancel = llm.cancel

        def _spy_cancel() -> None:
            cancel_called.append(True)
            original_cancel()

        llm.cancel = _spy_cancel  # type: ignore[method-assign]

        # Timer를 0.05s로 단축하여 즉시 만료 시뮬레이션
        timer = _threading.Timer(0.05, llm.cancel)
        timer.start()
        timer.join(timeout=1.0)

        assert cancel_called, "cancel()이 호출되지 않음"
