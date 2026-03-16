"""
Offline LLM integration for Connector Vision SOP Agent.

지원 백엔드:
- ``ollama``   : Ollama 로컬 서버 (권장). OpenAI 호환 HTTP API.
                 설치: https://ollama.com  /  ollama pull llama4:scout
- ``http``     : LM Studio / Ollama 등 기존 OpenAI 호환 HTTP 서버 (직접 URL 지정).
- ``llama_cpp``: llama-cpp-python으로 GGUF 파일 직접 로드 (레거시, 무겁다).

모듈 import 시 무거운 의존성을 로드하지 않는다.
백엔드가 없거나 설정이 잘못된 경우 친절한 RuntimeError만 발생하며 EXE가 종료되지 않는다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Type

# CP-1: "ollama" 백엔드 추가 (Llama4 Scout 기본 타깃)
BackendType = Literal["llama_cpp", "http", "ollama"]

_OLLAMA_DEFAULT_URL = "http://localhost:11434/v1/chat/completions"
_OLLAMA_DEFAULT_MODEL = "llama4:scout"


@dataclass
class LLMConfig:
    # CP-1: 기본값을 Ollama + Llama4 Scout 기준으로 변경
    backend: BackendType = "ollama"
    model_path: str | None = _OLLAMA_DEFAULT_MODEL  # Ollama 모델 태그 또는 GGUF 경로
    ctx_size: int = 8192  # Llama4 Scout 기준 확장
    gpu_layers: int = 0
    http_url: str | None = _OLLAMA_DEFAULT_URL  # Ollama 기본 URL
    max_input_tokens: int = 6144
    max_output_tokens: int = 1024

    @classmethod
    def from_dict(cls: Type["LLMConfig"], data: Dict[str, Any]) -> "LLMConfig":
        return cls(
            backend=data.get("backend", "ollama"),
            model_path=data.get("model_path", _OLLAMA_DEFAULT_MODEL),
            ctx_size=int(data.get("ctx_size", 8192)),
            gpu_layers=int(data.get("gpu_layers", 0)),
            http_url=data.get("http_url", _OLLAMA_DEFAULT_URL),
            max_input_tokens=int(data.get("max_input_tokens", 6144)),
            max_output_tokens=int(data.get("max_output_tokens", 1024)),
        )


class OfflineLLM:
    """로컬 LLM 백엔드 래퍼.

    모듈 로딩 시 무거운 패키지를 import하지 않아 EXE가 LLM 없이도 정상 기동된다.
    """

    def __init__(self, cfg: LLMConfig) -> None:
        self.cfg = cfg

    # ------------------------------------------------------------------ #
    # 생성자
    # ------------------------------------------------------------------ #

    @classmethod
    def from_config(cls, cfg_dict: Dict[str, Any]) -> "OfflineLLM":
        cfg = LLMConfig.from_dict(cfg_dict)
        return cls(cfg)

    # ------------------------------------------------------------------ #
    # 핵심 채팅 인터페이스
    # ------------------------------------------------------------------ #

    def chat(self, system: str, history: List[Dict[str, str]]) -> str:
        """단일 턴 채팅 완성. 백엔드에 따라 적절한 메서드로 라우팅한다."""

        if self.cfg.backend == "ollama":
            return self._chat_ollama(system, history)
        if self.cfg.backend == "http":
            return self._chat_http(system, history)
        if self.cfg.backend == "llama_cpp":
            return self._chat_llama_cpp(system, history)
        raise RuntimeError(f"Unsupported LLM backend: {self.cfg.backend!r}")

    # ------------------------------------------------------------------ #
    # Ollama 백엔드 (CP-1 신규, 권장)
    # ------------------------------------------------------------------ #

    def _chat_ollama(self, system: str, history: List[Dict[str, str]]) -> str:
        """Ollama 로컬 서버에 OpenAI 호환 API로 요청한다.

        Ollama URL과 모델 태그에 합리적인 기본값을 적용하므로
        config.json의 llm 블록에서 http_url / model_path를 생략해도 동작한다.

        설치 및 모델 준비:
            winget install Ollama.Ollama
            ollama pull llama4:scout
            ollama serve
        """

        try:
            import requests  # type: ignore[import]
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "The 'requests' package is required for 'ollama' backend. "
                "pip install requests"
            ) from exc

        url = self.cfg.http_url or _OLLAMA_DEFAULT_URL
        model = self.cfg.model_path or _OLLAMA_DEFAULT_MODEL

        messages: List[Dict[str, str]] = []
        if not history or history[0].get("role") != "system":
            messages.append({"role": "system", "content": system})
        messages.extend(history)

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": self.cfg.max_output_tokens,
            "stream": False,
        }

        # Ollama는 모델 첫 로드 시 시간이 걸릴 수 있으므로 타임아웃을 길게 설정
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        try:
            return data["choices"][0]["message"]["content"]
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"Unexpected Ollama response format: {data!r}") from exc

    # ------------------------------------------------------------------ #
    # HTTP 백엔드 (LM Studio / 커스텀 서버 등)
    # ------------------------------------------------------------------ #

    def _chat_http(self, system: str, history: List[Dict[str, str]]) -> str:
        """OpenAI 호환 HTTP 서버에 요청한다. http_url이 반드시 필요하다."""

        try:
            import requests  # type: ignore[import]
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "The 'requests' package is required for 'http' LLM backend."
            ) from exc

        if not self.cfg.http_url:
            raise RuntimeError("LLMConfig.http_url is required for 'http' backend.")

        messages: List[Dict[str, str]] = []
        if not history or history[0].get("role") != "system":
            messages.append({"role": "system", "content": system})
        messages.extend(history)

        payload = {
            "model": self.cfg.model_path or "llama4:scout",
            "messages": messages,
            "max_tokens": self.cfg.max_output_tokens,
        }

        resp = requests.post(self.cfg.http_url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        try:
            return data["choices"][0]["message"]["content"]
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                f"Unexpected HTTP LLM response format: {data!r}"
            ) from exc

    # ------------------------------------------------------------------ #
    # llama_cpp 백엔드 (레거시 — 향후 deprecated 예정)
    # ------------------------------------------------------------------ #

    def _chat_llama_cpp(self, system: str, history: List[Dict[str, str]]) -> str:
        """llama-cpp-python으로 GGUF 파일을 직접 로드한다. (레거시)

        .. deprecated::
            CP-2 이후 ollama 백엔드를 사용할 것을 권장한다.
            GGUF 파일 관리가 복잡하고 llama-cpp-python 빌드 의존성이 무겁다.
        """

        try:
            from llama_cpp import Llama  # type: ignore[import]
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "llama-cpp-python is not installed; cannot use 'llama_cpp' backend. "
                "권장: config.json의 backend를 'ollama'로 변경하세요."
            ) from exc

        if not self.cfg.model_path:
            raise RuntimeError(
                "LLMConfig.model_path is required for 'llama_cpp' backend."
            )

        messages: List[Dict[str, str]] = []
        if not history or history[0].get("role") != "system":
            messages.append({"role": "system", "content": system})
        messages.extend(history)

        llm = Llama(
            model_path=self.cfg.model_path,
            n_ctx=self.cfg.ctx_size,
            n_gpu_layers=self.cfg.gpu_layers,
        )

        result = llm.create_chat_completion(
            messages=messages,
            max_tokens=self.cfg.max_output_tokens,
        )
        try:
            return result["choices"][0]["message"]["content"]
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                f"Unexpected Llama chat response format: {result!r}"
            ) from exc

    # ------------------------------------------------------------------ #
    # 로그 분석 헬퍼
    # ------------------------------------------------------------------ #

    def analyze_logs(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """SOP 실행 페이로드를 LLM으로 분석하고 개선 제안을 반환한다.

        반환 형식:
            {
                "config_patch": {"key": value, ...},
                "sop_recommendations": ["권장사항1", ...],
                "raw_text": "LLM 전체 응답 텍스트"
            }
        """

        system = (
            "You are an expert Samsung OLED connector SOP and machine vision "
            "engineer. You receive structured logs, a summary, and configuration "
            "for an automation run. Diagnose issues and propose safe, minimal "
            "changes to improve robustness. Return ONLY a JSON object with keys:\n"
            "- config_patch: dict of config.json keys to update\n"
            "- sop_recommendations: list of human-readable Korean suggestions\n"
            "- raw_text: your full reasoning in Korean"
        )

        user_content = json.dumps(payload, ensure_ascii=False)
        history = [
            {
                "role": "user",
                "content": f"Here is the latest SOP run payload:\n{user_content}",
            }
        ]

        raw = self.chat(system=system, history=history)

        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("Parsed LLM output is not a dict.")
            config_patch = parsed.get("config_patch", {})
            sop_recs = parsed.get("sop_recommendations", [])
            raw_text = parsed.get("raw_text", raw)
        except Exception:
            config_patch = {}
            sop_recs = []
            raw_text = raw

        return {
            "config_patch": config_patch,
            "sop_recommendations": sop_recs,
            "raw_text": raw_text,
        }
