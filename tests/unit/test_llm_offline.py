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
        # Ollama /api/chat native response format
        resp.json.return_value = {
            "model": "ibm/granite3.3-vision:2b",
            "message": {"role": "assistant", "content": content},
            "done": True,
        }
        return resp

    def test_chat_returns_response_content(self) -> None:
        llm = OfflineLLM.from_config({})  # ollama 기본값
        with patch("requests.post", return_value=self._mock_response("안녕하세요!")):
            result = llm.chat("system", [{"role": "user", "content": "hi"}])
        assert result == "안녕하세요!"

    def test_chat_passes_proxy_bypass_kwargs(self) -> None:
        llm = OfflineLLM.from_config({})
        with patch("requests.post", return_value=self._mock_response("ok")) as mock_post:
            llm.chat("system", [{"role": "user", "content": "hi"}])
        assert mock_post.call_args[1]["proxies"] == {"http": None, "https": None}

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
        # model_path is deployment-specific (set in config.json or config.proposed.json)
        assert llm.cfg.model_path is not None


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
    """Helper: Ollama /api/chat NDJSON streaming format (was SSE, now NDJSON)."""
    import json as _json

    lines = []
    for t in tokens:
        chunk = {"message": {"role": "assistant", "content": t}, "done": False}
        lines.append(_json.dumps(chunk).encode())
    lines.append(
        _json.dumps(
            {"message": {"role": "assistant", "content": ""}, "done": True}
        ).encode()
    )
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
            with patch(
                "src.llm_offline.detect_local_accelerator",
                return_value={
                    "device": 0,
                    "name": "NVIDIA RTX 4000 Ada Generation",
                    "memory_gb": 20.0,
                    "gpu_present": True,
                    "cuda_usable": True,
                },
            ):
                result = llm.check_health()
        assert result is not None
        assert "GPU" in result

    def test_health_ok_cpu_only_returns_info_message(self) -> None:
        llm = OfflineLLM.from_config({})
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_get.return_value = mock_resp
            with patch(
                "src.llm_offline.detect_local_accelerator",
                return_value={
                    "device": "cpu",
                    "name": None,
                    "memory_gb": None,
                    "gpu_present": False,
                    "cuda_usable": False,
                },
            ):
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
            with patch(
                "src.llm_offline.detect_local_accelerator",
                return_value={
                    "device": 0,
                    "name": "NVIDIA RTX 4000 Ada Generation",
                    "memory_gb": 20.0,
                    "gpu_present": True,
                    "cuda_usable": True,
                },
            ):
                llm.check_health()
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs.get("timeout") == _HEALTH_TIMEOUT

    def test_health_timeout_is_at_least_30_seconds(self) -> None:
        """_HEALTH_TIMEOUT must be >= 30s.

        Line PCs run Ollama from a mapped network drive (Z:\\) with limited RAM.
        The model may still be loading into memory 5-10s after the process starts.
        A value of 30s gives Ollama enough headroom to respond on slow hardware.
        """
        from src.llm_offline import _HEALTH_TIMEOUT

        assert _HEALTH_TIMEOUT >= 30, (
            f"_HEALTH_TIMEOUT is {_HEALTH_TIMEOUT}s — too short for slow startup envs. "
            "Must be >= 30s."
        )

    def test_health_check_bypasses_system_proxy(self) -> None:
        """check_health() must NOT route requests through the system HTTP proxy.

        Line PCs are on a corporate network with an HTTP proxy (e.g. 107.100.72.56).
        Python's requests library respects HTTP_PROXY / Windows proxy settings by
        default and routes ALL HTTP calls — including http://127.0.0.1:11434 — through
        the corporate proxy.  The proxy cannot reach the client's own loopback adapter,
        so it returns 503 / connection-refused.

        Fix: pass proxies={'http': None, 'https': None} to bypass proxy for localhost.
        """
        llm = OfflineLLM.from_config({})
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_get.return_value = mock_resp
            with patch(
                "src.llm_offline.detect_local_accelerator",
                return_value={
                    "device": 0,
                    "name": "NVIDIA RTX 4000 Ada Generation",
                    "memory_gb": 20.0,
                    "gpu_present": True,
                    "cuda_usable": True,
                },
            ):
                llm.check_health()
        call_kwargs = mock_get.call_args[1]
        # Must explicitly pass proxies= dict with None values to override system proxy.
        # An absent proxies kwarg means requests still uses system/env proxy — that is wrong.
        assert (
            "proxies" in call_kwargs
        ), "check_health() did not pass proxies= kwarg — system proxy will intercept Ollama requests"
        proxies = call_kwargs["proxies"]
        assert (
            proxies.get("http") is None
        ), "check_health() did not disable http proxy — corporate proxy will intercept"
        assert (
            proxies.get("https") is None
        ), "check_health() did not disable https proxy — corporate proxy will intercept"

    def test_get_session_trust_env_false(self) -> None:
        """_get_session() must set trust_env=False to bypass system proxy for streaming.

        requests.Session() with default trust_env=True picks up HTTP_PROXY /
        HTTPS_PROXY environment variables and Windows WinINet proxy settings.
        On a line PC with a corporate proxy (e.g. 107.100.72.56), all Ollama
        streaming requests would be routed through the proxy → 503 error.

        Setting session.trust_env = False bypasses all environment-based proxies.
        """
        llm = OfflineLLM.from_config({})
        session = llm._get_session()
        assert session.trust_env is False, (
            "requests.Session has trust_env=True — corporate proxy will intercept "
            "all Ollama requests including http://127.0.0.1:11434"
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
    def test_detected_gpu_uses_ollama_offload_even_without_torch_cuda(self) -> None:
        llm = OfflineLLM.from_config({})
        with patch(
            "src.llm_offline.detect_local_accelerator",
            return_value={
                "device": "cpu",
                "name": "NVIDIA RTX 4000 Ada Generation",
                "memory_gb": 20.0,
                "gpu_present": True,
                "cuda_usable": False,
            },
        ):
            opts = llm._get_optimized_options()
        assert opts["num_gpu"] == 99

    def test_gpu_mode_sets_num_gpu_99(self) -> None:
        """CUDA 감지 시 num_gpu=99 설정 확인."""
        llm = OfflineLLM.from_config({})
        with patch(
            "src.llm_offline.detect_local_accelerator",
            return_value={
                "device": 0,
                "name": "NVIDIA RTX 4000 Ada Generation",
                "memory_gb": 20.0,
                "gpu_present": True,
                "cuda_usable": True,
            },
        ):
            opts = llm._get_optimized_options()
        assert opts["num_gpu"] == 99

    def test_cpu_mode_sets_num_thread_and_num_gpu_0(self) -> None:
        """CPU-only 환경에서 num_gpu=0, num_thread>=1 설정 확인."""
        llm = OfflineLLM.from_config({})
        with patch(
            "src.llm_offline.detect_local_accelerator",
            return_value={
                "device": "cpu",
                "name": None,
                "memory_gb": None,
                "gpu_present": False,
                "cuda_usable": False,
            },
        ):
            opts = llm._get_optimized_options()
        assert opts["num_gpu"] == 0
        assert opts["num_thread"] >= 1

    def test_brief_mode_no_think_in_options(self) -> None:
        """brief=True 시 options{}에 think 키 없음 확인.

        think=False는 payload 최상위에 위치해야 하므로 options{}에는 포함되지 않아야 함.
        options{} 안에 think를 넣으면 Ollama가 llama.cpp 파라미터로 오인해 무시한다.
        """
        llm = OfflineLLM.from_config({})
        with patch(
            "src.llm_offline.detect_local_accelerator",
            return_value={
                "device": "cpu",
                "name": None,
                "memory_gb": None,
                "gpu_present": False,
                "cuda_usable": False,
            },
        ):
            opts = llm._get_optimized_options(brief=True)
        assert (
            "think" not in opts
        ), "think must NOT be inside options{} — it must be at payload top level"

    def test_brief_mode_num_ctx_4096(self) -> None:
        """brief=True 시 num_ctx=4096 (컨텍스트 단축) 확인."""
        llm = OfflineLLM.from_config({"ctx_size": 8192})
        with patch(
            "src.llm_offline.detect_local_accelerator",
            return_value={
                "device": "cpu",
                "name": None,
                "memory_gb": None,
                "gpu_present": False,
                "cuda_usable": False,
            },
        ):
            opts = llm._get_optimized_options(brief=True)
        assert opts["num_ctx"] == 4096

    def test_non_brief_mode_no_think_key(self) -> None:
        """brief=False 시 options에 think 키 없음 확인."""
        llm = OfflineLLM.from_config({})
        with patch(
            "src.llm_offline.detect_local_accelerator",
            return_value={
                "device": "cpu",
                "name": None,
                "memory_gb": None,
                "gpu_present": False,
                "cuda_usable": False,
            },
        ):
            opts = llm._get_optimized_options(brief=False)
        assert "think" not in opts


# ---------------------------------------------------------------------------
# Bug2 v2 fixes — think=False at payload top level (not inside options)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# _BRIEF_MAX_TOKENS 값 검증 (빈 응답 방지)
# ---------------------------------------------------------------------------


class TestBriefMaxTokens:
    def test_brief_max_tokens_is_at_least_1024(self) -> None:
        """Granite Vision 3.3-2b는 <think> 없으므로 512로 충분."""
        from src.llm_offline import _BRIEF_MAX_TOKENS

        assert _BRIEF_MAX_TOKENS >= 512, (
            f"_BRIEF_MAX_TOKENS={_BRIEF_MAX_TOKENS} is too small — "
            "Granite Vision 3.3-2b needs at least 512 tokens for a useful brief response."
        )

    def test_brief_mode_uses_brief_max_tokens(self) -> None:
        """brief=True 시 payload['options']['num_predict'] == _BRIEF_MAX_TOKENS."""
        from src.llm_offline import _BRIEF_MAX_TOKENS

        llm = OfflineLLM.from_config({})
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "model": "ibm/granite3.3-vision:2b",
            "message": {"role": "assistant", "content": "hi"},
            "done": True,
        }

        with patch("requests.post", return_value=mock_resp) as mock_post:
            llm.chat("sys", [{"role": "user", "content": "hi"}], brief=True)

        payload = mock_post.call_args[1]["json"]
        assert payload["options"]["num_predict"] == _BRIEF_MAX_TOKENS


# ---------------------------------------------------------------------------
# 스트리밍 엣지케이스 — <think> 블록만 있고 answer 없음
# ---------------------------------------------------------------------------


class TestStreamingEdgeCases:
    def _make_streaming_resp(self, tokens: list) -> MagicMock:
        import json as _json

        lines = []
        for t in tokens:
            chunk = {"message": {"role": "assistant", "content": t}, "done": False}
            lines.append(_json.dumps(chunk).encode())
        lines.append(
            _json.dumps(
                {"message": {"role": "assistant", "content": ""}, "done": True}
            ).encode()
        )
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.raise_for_status.return_value = None
        resp.iter_lines.return_value = lines
        return resp

    def test_empty_answer_when_all_tokens_in_think_block(self) -> None:
        """<think> 블록만 있고 answer 없으면 answer_text='' 로 on_done 호출."""
        llm = OfflineLLM.from_config({})
        mock_sess = MagicMock()
        mock_sess.post.return_value = self._make_streaming_resp(
            ["<think>", "some reasoning", "</think>"]
        )
        llm._session = mock_sess

        done_args: list = []
        think_tokens: list = []

        llm.stream_chat(
            "sys",
            [{"role": "user", "content": "hi"}],
            on_token=lambda t: None,
            on_done=lambda text, elapsed: done_args.append(text),
            on_think_token=lambda t: think_tokens.append(t),
        )

        assert done_args == [
            ""
        ], "answer_text should be empty when all tokens are inside <think> block"
        assert "some reasoning" in "".join(think_tokens)

    def test_answer_tokens_after_think_block_are_captured(self) -> None:
        """</think> 이후 answer 토큰이 정상 수집됨."""
        llm = OfflineLLM.from_config({})
        mock_sess = MagicMock()
        mock_sess.post.return_value = self._make_streaming_resp(
            ["<think>", "reasoning", "</think>", "Hello", " world"]
        )
        llm._session = mock_sess

        answer_tokens: list = []
        done_args: list = []

        llm.stream_chat(
            "sys",
            [{"role": "user", "content": "hi"}],
            on_token=lambda t: answer_tokens.append(t),
            on_done=lambda text, elapsed: done_args.append(text),
        )

        assert "".join(answer_tokens) == "Hello world"
        assert done_args == ["Hello world"]


# ---------------------------------------------------------------------------
# Granite Vision 3.3-2b — /api/chat NDJSON + image support
# ---------------------------------------------------------------------------


def _make_ndjson_lines(tokens: list[str]) -> list[bytes]:
    """Helper: Ollama /api/chat native NDJSON streaming format."""
    import json as _json

    lines = []
    for t in tokens:
        chunk = {"message": {"role": "assistant", "content": t}, "done": False}
        lines.append(_json.dumps(chunk).encode())
    lines.append(
        _json.dumps(
            {"message": {"role": "assistant", "content": ""}, "done": True}
        ).encode()
    )
    return lines


class TestGraniteVisionAPI:
    """Granite Vision 3.3-2b: /api/chat NDJSON 포맷 + 이미지 첨부 검증."""

    def _mock_response(self, content: str) -> MagicMock:
        """Ollama /api/chat non-streaming response format."""
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            "model": "ibm/granite3.3-vision:2b",
            "message": {"role": "assistant", "content": content},
            "done": True,
        }
        return resp

    def _make_streaming_resp(self, tokens: list[str]) -> MagicMock:
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.raise_for_status.return_value = None
        resp.iter_lines.return_value = _make_ndjson_lines(tokens)
        return resp

    def _mock_session(self, tokens: list[str]) -> MagicMock:
        sess = MagicMock()
        sess.post.return_value = self._make_streaming_resp(tokens)
        return sess

    def test_default_url_is_api_chat(self) -> None:
        """기본 URL이 Ollama /api/chat 이어야 한다."""
        from src.llm_offline import _OLLAMA_DEFAULT_URL

        assert "/api/chat" in _OLLAMA_DEFAULT_URL

    def test_default_model_is_granite_vision(self) -> None:
        """기본 모델이 IBM Granite Vision 이어야 한다."""
        from src.llm_offline import _OLLAMA_DEFAULT_MODEL

        assert "granite" in _OLLAMA_DEFAULT_MODEL.lower()

    def test_chat_returns_native_message_content(self) -> None:
        """_chat_ollama()가 Ollama /api/chat 응답 포맷에서 content를 추출한다."""
        llm = OfflineLLM.from_config({})
        with patch("requests.post", return_value=self._mock_response("Granite답변")):
            result = llm.chat("sys", [{"role": "user", "content": "hi"}])
        assert result == "Granite답변"

    def test_chat_payload_uses_num_predict_not_max_tokens(self) -> None:
        """Ollama /api/chat는 options.num_predict을 사용한다."""
        llm = OfflineLLM.from_config({})
        with patch(
            "requests.post", return_value=self._mock_response("ok")
        ) as mock_post:
            llm.chat("sys", [{"role": "user", "content": "test"}])
        payload = mock_post.call_args[1]["json"]
        # num_predict should be inside options, not top-level max_tokens
        assert "num_predict" in payload.get("options", {})

    def test_stream_chat_ndjson_parses_tokens(self) -> None:
        """스트리밍이 NDJSON 포맷 (Ollama /api/chat)으로 파싱된다."""
        llm = OfflineLLM.from_config({})
        llm._session = self._mock_session(["Hello", " Granite"])
        received: list[str] = []
        result = llm.stream_chat(
            "sys", [{"role": "user", "content": "hi"}], on_token=received.append
        )
        assert "".join(received) == "Hello Granite"
        assert result == "Hello Granite"

    def test_chat_with_image_attaches_base64(self) -> None:
        """이미지 b64가 있으면 마지막 user 메시지의 images 필드에 첨부된다."""
        llm = OfflineLLM.from_config({})
        b64 = "aGVsbG8="  # base64("hello")
        with patch(
            "requests.post", return_value=self._mock_response("ok")
        ) as mock_post:
            llm.chat("sys", [{"role": "user", "content": "describe"}], image_b64=b64)
        messages = mock_post.call_args[1]["json"]["messages"]
        user_msgs = [m for m in messages if m["role"] == "user"]
        assert user_msgs, "user message must exist"
        assert user_msgs[-1].get("images") == [b64]

    def test_stream_with_image_attaches_base64(self) -> None:
        """stream_chat()에 image_b64 전달 시 페이로드에 images 필드가 포함된다."""
        llm = OfflineLLM.from_config({})
        llm._session = self._mock_session(["caption"])
        b64 = "aW1hZ2U="  # base64("image")
        received: list[str] = []
        llm.stream_chat(
            "sys",
            [{"role": "user", "content": "describe this"}],
            on_token=received.append,
            image_b64=b64,
        )
        call_args = llm._session.post.call_args
        messages = call_args[1]["json"]["messages"]
        user_msgs = [m for m in messages if m["role"] == "user"]
        assert user_msgs[-1].get("images") == [b64]

    def test_health_check_handles_api_chat_url(self) -> None:
        """check_health()가 /api/chat URL에서 base URL을 올바르게 추출한다."""
        llm = OfflineLLM.from_config({})
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        with patch("requests.get", return_value=mock_resp) as mock_get:
            llm.check_health()
        called_url = mock_get.call_args[0][0]
        # Base URL should not contain /api/chat
        assert "/api/chat" not in called_url
        assert "localhost:11434" in called_url
