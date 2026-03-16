"""
llm_offline 단위 테스트.

LLMConfig.from_dict, OfflineLLM 백엔드 디스패치, HTTP mock, analyze_logs
결과 형식을 외부 LLM 없이 검증한다.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.llm_offline import LLMConfig, OfflineLLM


# ---------------------------------------------------------------------------
# LLMConfig
# ---------------------------------------------------------------------------


class TestLLMConfig:
    def test_default_values(self) -> None:
        cfg = LLMConfig.from_dict({})
        assert cfg.backend == "llama_cpp"
        assert cfg.ctx_size == 4096
        assert cfg.gpu_layers == 0
        assert cfg.max_input_tokens == 4096
        assert cfg.max_output_tokens == 512

    def test_backend_parsed(self) -> None:
        cfg = LLMConfig.from_dict({"backend": "http"})
        assert cfg.backend == "http"

    def test_model_path_parsed(self) -> None:
        cfg = LLMConfig.from_dict({"model_path": "/tmp/model.gguf"})
        assert cfg.model_path == "/tmp/model.gguf"

    def test_ctx_size_as_int(self) -> None:
        cfg = LLMConfig.from_dict({"ctx_size": "8192"})  # 문자열 → int 변환
        assert cfg.ctx_size == 8192

    def test_gpu_layers_as_int(self) -> None:
        cfg = LLMConfig.from_dict({"gpu_layers": "4"})
        assert cfg.gpu_layers == 4

    def test_http_url_parsed(self) -> None:
        url = "http://localhost:11434/v1/chat/completions"
        cfg = LLMConfig.from_dict({"http_url": url})
        assert cfg.http_url == url

    def test_none_model_path(self) -> None:
        cfg = LLMConfig.from_dict({"model_path": None})
        assert cfg.model_path is None

    def test_max_tokens_parsed(self) -> None:
        cfg = LLMConfig.from_dict({"max_input_tokens": 6144, "max_output_tokens": 1024})
        assert cfg.max_input_tokens == 6144
        assert cfg.max_output_tokens == 1024


# ---------------------------------------------------------------------------
# OfflineLLM 생성
# ---------------------------------------------------------------------------


class TestOfflineLLMConstruction:
    def test_from_config_creates_instance(self) -> None:
        llm = OfflineLLM.from_config({})
        assert isinstance(llm, OfflineLLM)

    def test_cfg_stored(self) -> None:
        llm = OfflineLLM.from_config({"backend": "http"})
        assert llm.cfg.backend == "http"


# ---------------------------------------------------------------------------
# 백엔드 디스패치
# ---------------------------------------------------------------------------


class TestBackendDispatch:
    def test_unsupported_backend_raises(self) -> None:
        llm = OfflineLLM(LLMConfig())
        llm.cfg.backend = "not_a_backend"  # type: ignore[assignment]
        with pytest.raises(RuntimeError, match="Unsupported"):
            llm.chat("sys", [{"role": "user", "content": "hi"}])

    def test_llama_cpp_without_model_path_raises(self) -> None:
        """llama_cpp 백엔드에서 model_path 없으면 RuntimeError 발생."""
        cfg = LLMConfig.from_dict({"backend": "llama_cpp", "model_path": None})
        llm = OfflineLLM(cfg)
        # llama-cpp-python 미설치 or model_path None — 둘 다 RuntimeError 여야 함
        with pytest.raises(RuntimeError):
            llm.chat("sys", [{"role": "user", "content": "hi"}])

    def test_http_without_url_raises(self) -> None:
        cfg = LLMConfig.from_dict({"backend": "http", "http_url": None})
        llm = OfflineLLM(cfg)
        with pytest.raises(RuntimeError, match="http_url"):
            llm.chat("sys", [{"role": "user", "content": "hi"}])


# ---------------------------------------------------------------------------
# HTTP 백엔드 (mock)
# ---------------------------------------------------------------------------


class TestHttpBackend:
    def _make_mock_response(self, content: str) -> MagicMock:
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            "choices": [{"message": {"content": content}}]
        }
        return resp

    def test_chat_returns_content(self) -> None:
        cfg = LLMConfig.from_dict({
            "backend": "http",
            "http_url": "http://localhost:11434/v1/chat/completions",
            "model_path": "llama4:scout",
            "max_output_tokens": 100,
        })
        llm = OfflineLLM(cfg)
        mock_resp = self._make_mock_response("안녕하세요!")

        with patch("requests.post", return_value=mock_resp) as mock_post:
            result = llm.chat("system prompt", [{"role": "user", "content": "hi"}])

        assert result == "안녕하세요!"
        assert mock_post.called

    def test_chat_posts_to_correct_url(self) -> None:
        url = "http://localhost:11434/v1/chat/completions"
        cfg = LLMConfig.from_dict({"backend": "http", "http_url": url, "model_path": "llama4:scout"})
        llm = OfflineLLM(cfg)

        with patch("requests.post", return_value=self._make_mock_response("ok")) as mock_post:
            llm.chat("sys", [{"role": "user", "content": "test"}])

        call_url = mock_post.call_args[0][0]
        assert call_url == url

    def test_chat_includes_system_message(self) -> None:
        cfg = LLMConfig.from_dict({
            "backend": "http",
            "http_url": "http://localhost:8000/v1/chat/completions",
            "model_path": "test-model",
        })
        llm = OfflineLLM(cfg)

        with patch("requests.post", return_value=self._make_mock_response("ok")) as mock_post:
            llm.chat("you are an expert", [{"role": "user", "content": "test"}])

        payload = mock_post.call_args[1]["json"]
        roles = [m["role"] for m in payload["messages"]]
        assert "system" in roles

    def test_chat_includes_user_history(self) -> None:
        cfg = LLMConfig.from_dict({
            "backend": "http",
            "http_url": "http://localhost:8000/v1/chat/completions",
            "model_path": "test-model",
        })
        llm = OfflineLLM(cfg)

        with patch("requests.post", return_value=self._make_mock_response("reply")) as mock_post:
            llm.chat("sys", [{"role": "user", "content": "my question"}])

        payload = mock_post.call_args[1]["json"]
        user_msgs = [m for m in payload["messages"] if m["role"] == "user"]
        assert any("my question" in m["content"] for m in user_msgs)

    def test_http_timeout_set(self) -> None:
        cfg = LLMConfig.from_dict({
            "backend": "http",
            "http_url": "http://localhost:8000/v1/chat/completions",
        })
        llm = OfflineLLM(cfg)

        with patch("requests.post", return_value=self._make_mock_response("ok")) as mock_post:
            llm.chat("sys", [{"role": "user", "content": "hi"}])

        assert mock_post.call_args[1].get("timeout") is not None


# ---------------------------------------------------------------------------
# analyze_logs
# ---------------------------------------------------------------------------


class TestAnalyzeLogs:
    def _make_llm_with_mock_chat(self, response_content: str) -> OfflineLLM:
        cfg = LLMConfig.from_dict({"backend": "llama_cpp", "model_path": "/fake/model.gguf"})
        llm = OfflineLLM(cfg)
        llm.chat = MagicMock(return_value=response_content)  # type: ignore[method-assign]
        return llm

    def test_result_has_required_keys(self) -> None:
        valid_json = json.dumps({
            "config_patch": {"ocr_threshold": 0.8},
            "sop_recommendations": ["step 1"],
            "raw_text": "all good",
        })
        llm = self._make_llm_with_mock_chat(valid_json)
        result = llm.analyze_logs({"run_id": "r1", "summary": {}})
        assert "config_patch" in result
        assert "sop_recommendations" in result
        assert "raw_text" in result

    def test_valid_json_parsed(self) -> None:
        valid_json = json.dumps({
            "config_patch": {"ocr_threshold": 0.85},
            "sop_recommendations": ["권장 사항"],
            "raw_text": "분석 완료",
        })
        llm = self._make_llm_with_mock_chat(valid_json)
        result = llm.analyze_logs({})
        assert result["config_patch"]["ocr_threshold"] == 0.85
        assert result["sop_recommendations"] == ["권장 사항"]

    def test_invalid_json_fallback(self) -> None:
        """LLM이 JSON이 아닌 텍스트를 반환해도 크래시하지 않는다."""
        llm = self._make_llm_with_mock_chat("이것은 JSON이 아닙니다.")
        result = llm.analyze_logs({})
        assert result["config_patch"] == {}
        assert result["sop_recommendations"] == []
        assert "이것은 JSON이 아닙니다." in result["raw_text"]

    def test_non_dict_json_fallback(self) -> None:
        """LLM이 JSON 배열 등 dict가 아닌 값을 반환하면 폴백."""
        llm = self._make_llm_with_mock_chat("[1, 2, 3]")
        result = llm.analyze_logs({})
        assert result["config_patch"] == {}

    def test_partial_json_keys(self) -> None:
        """일부 키만 있는 JSON도 안전하게 처리."""
        partial = json.dumps({"config_patch": {"a": 1}})
        llm = self._make_llm_with_mock_chat(partial)
        result = llm.analyze_logs({})
        assert result["sop_recommendations"] == []  # 없는 키는 기본값

    def test_payload_sent_to_chat(self) -> None:
        """payload 내용이 chat() 호출에 포함되는지 확인."""
        llm = self._make_llm_with_mock_chat('{"config_patch":{}, "sop_recommendations":[], "raw_text":""}')
        payload = {"run_id": "test_run", "summary": {"success": True}}
        llm.analyze_logs(payload)
        call_args = llm.chat.call_args  # type: ignore[union-attr]
        # history의 첫 번째 user 메시지에 run_id가 포함되어야 함
        history = call_args[1]["history"] if "history" in call_args[1] else call_args[0][1]
        combined = " ".join(str(m) for m in history)
        assert "test_run" in combined
