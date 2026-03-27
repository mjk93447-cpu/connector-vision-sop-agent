"""
LLM Granite 체인 통합 테스트 (v3.10.1)

검증 범위:
  1. assets/config.json — Granite 모델/엔드포인트 값 확인
  2. on_llm_send() → LLMStreamWorker / LLMWorker → stream_chat/chat 경로에서
     image_b64가 올바르게 전달되는지 소스 레벨 확인
  3. OfflineLLM.chat() / stream_chat() 에서 image_b64가 HTTP 페이로드에 포함되는지
     mock HTTP 검증
  4. 수정 전 TypeError 재현 방어 — on_llm_send() 호출 서명 회귀 방지
"""

from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_config_json() -> dict:
    """assets/config.json을 직접 파싱."""
    cfg_path = Path(__file__).parents[2] / "assets" / "config.json"
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def _ndjson_lines(tokens: list[str]) -> list[bytes]:
    """Ollama /api/chat NDJSON 스트리밍 포맷 시뮬레이션."""
    import json as _j

    lines = [
        _j.dumps(
            {"message": {"role": "assistant", "content": t}, "done": False}
        ).encode()
        for t in tokens
    ]
    lines.append(
        _j.dumps(
            {"message": {"role": "assistant", "content": ""}, "done": True}
        ).encode()
    )
    return lines


def _mock_ollama_response(content: str) -> MagicMock:
    """Ollama /api/chat non-streaming 응답 모의."""
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "model": "granite3.2-vision:2b",
        "message": {"role": "assistant", "content": content},
        "done": True,
    }
    return resp


def _mock_streaming_response(tokens: list[str]) -> MagicMock:
    resp = MagicMock()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    resp.raise_for_status.return_value = None
    resp.iter_lines.return_value = _ndjson_lines(tokens)
    return resp


# ---------------------------------------------------------------------------
# 1. Config 검증
# ---------------------------------------------------------------------------


class TestGraniteConfig:
    """assets/config.json이 Granite 모델/엔드포인트로 설정돼 있는지 확인."""

    def test_model_path_is_granite(self) -> None:
        """model_path가 granite 계열 모델 태그여야 한다."""
        cfg = _load_config_json()
        model = cfg["llm"]["model_path"]
        assert "granite" in model.lower(), (
            f"config.json model_path should be granite — got: {model!r}. "
            "Run: update llm.model_path to 'granite3.2-vision:2b'"
        )

    def test_http_url_is_ollama_api_chat(self) -> None:
        """http_url이 Ollama 네이티브 /api/chat 엔드포인트여야 한다."""
        cfg = _load_config_json()
        url = cfg["llm"]["http_url"]
        assert "/api/chat" in url, (
            f"config.json http_url must use /api/chat — got: {url!r}. "
            "Granite Vision uses Ollama native NDJSON format, not /v1/chat/completions"
        )

    def test_llm_backend_is_ollama(self) -> None:
        """backend 값이 'ollama'여야 한다."""
        cfg = _load_config_json()
        assert cfg["llm"]["backend"] == "ollama"

    def test_llm_enabled(self) -> None:
        """LLM이 활성화돼 있어야 한다."""
        cfg = _load_config_json()
        assert cfg["llm"]["enabled"] is True

    def test_offline_llm_from_config_uses_granite(self) -> None:
        """OfflineLLM.from_config(config.json llm 블록)이 granite 모델로 초기화된다."""
        from src.llm_offline import OfflineLLM

        cfg = _load_config_json()
        llm = OfflineLLM.from_config(cfg["llm"])
        assert llm.cfg.backend == "ollama"
        assert "granite" in (llm.cfg.model_path or "").lower()
        assert "/api/chat" in (llm.cfg.http_url or "")


# ---------------------------------------------------------------------------
# 2. image_b64 전달 경로 소스 레벨 검증
# ---------------------------------------------------------------------------


class TestImageB64PropagationSource:
    """run() 소스 코드에서 image_b64=self._image_b64 가 실제로 호출되는지 확인.

    QThread를 직접 실행하지 않고도 코드 경로를 보장하는 정적 검증.
    """

    def test_llm_stream_worker_run_passes_image_b64(self) -> None:
        """LLMStreamWorker.run() 내부 _stream_fn이 image_b64=self._image_b64를 전달."""
        workers_mod = importlib.import_module("src.gui.workers")
        source = inspect.getsource(workers_mod.LLMStreamWorker.run)
        assert "image_b64=self._image_b64" in source, (
            "LLMStreamWorker.run()의 _stream_fn이 stream_chat()에 "
            "image_b64=self._image_b64를 전달하지 않음 — Granite 멀티모달 경로 단절"
        )

    def test_llm_worker_run_passes_image_b64(self) -> None:
        """LLMWorker.run()이 chat()에 image_b64=self._image_b64를 전달."""
        workers_mod = importlib.import_module("src.gui.workers")
        source = inspect.getsource(workers_mod.LLMWorker.run)
        assert (
            "image_b64=self._image_b64" in source
        ), "LLMWorker.run()이 chat()에 image_b64=self._image_b64를 전달하지 않음"

    def test_stream_worker_stores_image_b64_in_init(self) -> None:
        """LLMStreamWorker.__init__이 self._image_b64 = image_b64 할당을 포함."""
        workers_mod = importlib.import_module("src.gui.workers")
        source = inspect.getsource(workers_mod.LLMStreamWorker.__init__)
        assert "self._image_b64" in source

    def test_llm_worker_stores_image_b64_in_init(self) -> None:
        """LLMWorker.__init__이 self._image_b64 = image_b64 할당을 포함."""
        workers_mod = importlib.import_module("src.gui.workers")
        source = inspect.getsource(workers_mod.LLMWorker.__init__)
        assert "self._image_b64" in source

    def test_on_llm_send_passes_image_b64_to_workers(self) -> None:
        """main_window.on_llm_send()가 LLMStreamWorker/LLMWorker 생성 시 image_b64를 전달."""
        mw_mod = importlib.import_module("src.gui.main_window")
        source = inspect.getsource(mw_mod.MainWindow.on_llm_send)
        assert (
            "image_b64=image_b64" in source
        ), "on_llm_send()가 Worker 생성 시 image_b64=image_b64를 전달하지 않음"


# ---------------------------------------------------------------------------
# 3. OfflineLLM HTTP 레벨 mock 검증
# ---------------------------------------------------------------------------


class TestGraniteHTTPChain:
    """OfflineLLM이 image_b64를 HTTP 페이로드에 포함시키는지 검증."""

    def test_chat_with_image_b64_includes_images_field(self) -> None:
        """chat(image_b64=...) 호출 시 HTTP 페이로드 마지막 user 메시지에 images 포함."""
        from src.llm_offline import OfflineLLM

        cfg = _load_config_json()
        llm = OfflineLLM.from_config(cfg["llm"])
        b64 = "aGVsbG8="  # base64("hello")

        with patch(
            "requests.post", return_value=_mock_ollama_response("ok")
        ) as mock_post:
            llm.chat(
                system="test sys",
                history=[{"role": "user", "content": "describe screen"}],
                image_b64=b64,
            )

        payload = mock_post.call_args[1]["json"]
        messages = payload["messages"]
        user_msgs = [m for m in messages if m.get("role") == "user"]
        assert user_msgs, "user 메시지가 없음"
        assert "images" in user_msgs[-1], "image_b64가 HTTP 페이로드에 포함되지 않음"
        assert b64 in user_msgs[-1]["images"]

    def test_stream_chat_with_image_b64_includes_images_field(self) -> None:
        """stream_chat(image_b64=...) 호출 시 HTTP 페이로드에 images 포함."""
        from src.llm_offline import OfflineLLM

        cfg = _load_config_json()
        llm = OfflineLLM.from_config(cfg["llm"])
        b64 = "c2NyZWVuU2hvdA=="

        mock_sess = MagicMock()
        mock_sess.post.return_value = _mock_streaming_response(["Response"])
        llm._session = mock_sess

        llm.stream_chat(
            system="sys",
            history=[{"role": "user", "content": "analyze"}],
            on_token=lambda _: None,
            image_b64=b64,
        )

        payload = mock_sess.post.call_args[1]["json"]
        messages = payload["messages"]
        user_msgs = [m for m in messages if m.get("role") == "user"]
        assert user_msgs and "images" in user_msgs[-1]
        assert b64 in user_msgs[-1]["images"]

    def test_chat_without_image_b64_no_images_field(self) -> None:
        """image_b64 없이 chat() 호출 시 images 필드가 포함되지 않는다."""
        from src.llm_offline import OfflineLLM

        cfg = _load_config_json()
        llm = OfflineLLM.from_config(cfg["llm"])

        with patch(
            "requests.post", return_value=_mock_ollama_response("ok")
        ) as mock_post:
            llm.chat(
                system="sys",
                history=[{"role": "user", "content": "hello"}],
            )

        payload = mock_post.call_args[1]["json"]
        messages = payload["messages"]
        for msg in messages:
            assert "images" not in msg, "image_b64 없을 때 images 필드가 삽입됨"

    def test_http_request_goes_to_api_chat_endpoint(self) -> None:
        """HTTP 요청이 /api/chat 엔드포인트로 전송된다 (not /v1/chat/completions)."""
        from src.llm_offline import OfflineLLM

        cfg = _load_config_json()
        llm = OfflineLLM.from_config(cfg["llm"])

        with patch(
            "requests.post", return_value=_mock_ollama_response("ok")
        ) as mock_post:
            llm.chat("sys", [{"role": "user", "content": "hi"}])

        called_url: Any = mock_post.call_args[0][0]
        assert "/api/chat" in called_url, (
            f"요청 URL이 /api/chat이 아님: {called_url!r}. "
            "Granite Vision은 Ollama 네이티브 포맷 필요"
        )


# ---------------------------------------------------------------------------
# 4. 회귀 방지 — 수정 전 TypeError 재현 방어
# ---------------------------------------------------------------------------


class TestTypeErrorRegression:
    """image_b64 파라미터 누락으로 발생하던 TypeError 회귀 방지."""

    def test_on_llm_send_signature_has_image_b64(self) -> None:
        """on_llm_send()에 image_b64 파라미터가 반드시 존재해야 한다."""
        mw_mod = importlib.import_module("src.gui.main_window")
        sig = inspect.signature(mw_mod.MainWindow.on_llm_send)
        assert "image_b64" in sig.parameters, (
            "on_llm_send()에 image_b64 파라미터 없음 — "
            "LlmPanel._on_send()가 TypeError를 발생시킬 것"
        )

    def test_image_b64_default_is_none(self) -> None:
        """image_b64 기본값 None — 스크린샷 없는 일반 채팅은 기존대로 동작."""
        mw_mod = importlib.import_module("src.gui.main_window")
        sig = inspect.signature(mw_mod.MainWindow.on_llm_send)
        assert sig.parameters["image_b64"].default is None

    def test_llm_stream_worker_accepts_image_b64(self) -> None:
        """LLMStreamWorker가 image_b64 파라미터를 수용해야 한다."""
        workers_mod = importlib.import_module("src.gui.workers")
        sig = inspect.signature(workers_mod.LLMStreamWorker.__init__)
        assert "image_b64" in sig.parameters

    def test_llm_worker_accepts_image_b64(self) -> None:
        """LLMWorker가 image_b64 파라미터를 수용해야 한다."""
        workers_mod = importlib.import_module("src.gui.workers")
        sig = inspect.signature(workers_mod.LLMWorker.__init__)
        assert "image_b64" in sig.parameters
