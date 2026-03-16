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

    def test_llama_cpp_backend_parsed(self) -> None:
        cfg = LLMConfig.from_dict({"backend": "llama_cpp"})
        assert cfg.backend == "llama_cpp"

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

    def test_llama_cpp_raises_without_setup(self) -> None:
        """llama_cpp 백엔드 설정 미완료 시 RuntimeError 발생."""
        cfg = LLMConfig.from_dict({"backend": "llama_cpp", "model_path": None})
        llm = OfflineLLM(cfg)
        with pytest.raises(RuntimeError):
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

    def test_timeout_is_120s(self) -> None:
        """Ollama는 모델 로딩 지연을 위해 더 긴 타임아웃 사용."""
        llm = OfflineLLM.from_config({})
        with patch(
            "requests.post", return_value=self._mock_response("ok")
        ) as mock_post:
            llm.chat("sys", [{"role": "user", "content": "test"}])
        assert mock_post.call_args[1]["timeout"] == 120

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
