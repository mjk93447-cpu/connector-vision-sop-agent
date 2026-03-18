"""
Offline LLM integration for Connector Vision SOP Agent.

Supported backends:
- ``ollama`` : Ollama local server (recommended). OpenAI-compatible HTTP API.
               Install: https://ollama.com  /  ollama pull phi4-mini-reasoning
- ``http``   : LM Studio / Ollama or any OpenAI-compatible HTTP server.

Heavy dependencies are NOT loaded at import time.
If backend is missing/misconfigured, a clear RuntimeError is raised
and the EXE continues running without LLM features.

New in v3.0:
- stream_chat()     : streaming token-by-token response (Ollama SSE)
- recovery_action() : SOP exception recovery via JSON response
- propose_sop_improvement() : analyze success patterns → sop_steps.proposed.json
- brief_mode        : shorter max_output_tokens for faster responses
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Literal, Optional, Type

BackendType = Literal["http", "ollama"]

_OLLAMA_DEFAULT_URL = "http://localhost:11434/v1/chat/completions"
_OLLAMA_DEFAULT_MODEL = "llama4:scout"

# Brief mode: shorter token limit for fast responses (used when user requests quick answer)
# 256 → 512: thinking 토큰이 max_tokens에 포함되므로 답변 여유 확보
_BRIEF_MAX_TOKENS = 512


@dataclass
class LLMConfig:
    backend: BackendType = "ollama"
    model_path: str | None = _OLLAMA_DEFAULT_MODEL  # Ollama 모델 태그
    ctx_size: int = 8192
    gpu_layers: int = 0
    http_url: str | None = _OLLAMA_DEFAULT_URL
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


_OLLAMA_BASE_URL = "http://localhost:11434"
_HEALTH_TIMEOUT = 1.5  # seconds for Ollama health check


class OfflineLLM:
    """로컬 LLM 백엔드 래퍼.

    모듈 로딩 시 무거운 패키지를 import하지 않아 EXE가 LLM 없이도 정상 기동된다.
    """

    def __init__(self, cfg: LLMConfig) -> None:
        self.cfg = cfg
        self._session: Any = (
            None  # requests.Session — created lazily, closed on cancel()
        )
        self._session_lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # 생성자
    # ------------------------------------------------------------------ #

    @classmethod
    def from_config(cls, cfg_dict: Dict[str, Any]) -> "OfflineLLM":
        cfg = LLMConfig.from_dict(cfg_dict)
        return cls(cfg)

    # ------------------------------------------------------------------ #
    # Session / cancellation
    # ------------------------------------------------------------------ #

    def _get_session(self) -> Any:
        """Return (or create) a requests.Session for streaming/chat requests."""
        try:
            import requests  # type: ignore[import]
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("requests package required") from exc
        with self._session_lock:
            if self._session is None:
                self._session = requests.Session()
            return self._session

    def cancel(self) -> None:
        """Cancel any in-flight HTTP request by closing the session.

        Called from LLMStreamWorker.stop() to immediately abort streaming.
        A fresh session will be created automatically on the next request.
        """
        with self._session_lock:
            if self._session is not None:
                try:
                    self._session.close()
                except Exception:  # noqa: BLE001
                    pass
                self._session = None

    # ------------------------------------------------------------------ #
    # Hardware-optimized Ollama options
    # ------------------------------------------------------------------ #

    def _get_optimized_options(self, brief: bool = False) -> Dict[str, Any]:
        """하드웨어에 맞는 Ollama llama.cpp 최적화 옵션 반환.

        우선순위: GPU (CUDA) > CPU 멀티코어
        - GPU 있음: num_gpu=99 (전 레이어 GPU 오프로딩), 빠른 추론
        - CPU only: num_thread=cpu_count-1, use_mlock=True로 8코어 이상 최대 활용
        """
        cpu_count = os.cpu_count() or 8

        has_gpu = False
        try:
            import torch  # type: ignore[import]

            has_gpu = torch.cuda.is_available()
        except ImportError:
            pass

        options: Dict[str, Any] = {
            "num_ctx": 4096 if brief else self.cfg.ctx_size,
            "use_mlock": True,  # 모델을 RAM에 고정 — 스왑 방지
            "use_mmap": True,  # 메모리맵 로딩 — 콜드 스타트 단축
        }

        if has_gpu:
            options["num_gpu"] = 99  # 모든 레이어 GPU 오프로딩
            options["num_thread"] = max(1, cpu_count // 4)
        else:
            options["num_gpu"] = 0
            options["num_thread"] = max(1, cpu_count - 1)  # 물리 코어 수 - 1

        if brief:
            # Ollama 0.7+: phi4-mini-reasoning thinking 비활성화
            # think 토큰이 max_tokens를 소진해 답변이 빈 문자열이 되는 문제 방지
            options["think"] = False

        return options

    # ------------------------------------------------------------------ #
    # Ollama health check
    # ------------------------------------------------------------------ #

    def check_health(self) -> Optional[str]:
        """Verify Ollama server is reachable before issuing a chat request.

        Raises RuntimeError with a clear message if:
        - Ollama is not running (connection refused)
        - Server responds but not within _HEALTH_TIMEOUT

        After successful health check, emits an info string if CPU-only
        by returning it as a second value.  Callers that only want the
        error-or-not behaviour can ignore the return value.

        Returns
        -------
        str | None
            None if GPU available, or an info message string if CPU-only.
        """
        try:
            import requests  # type: ignore[import]
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("requests package required") from exc

        # Derive base URL from configured completions URL
        url = self.cfg.http_url or _OLLAMA_DEFAULT_URL
        # Strip "/v1/chat/completions" suffix to reach the root endpoint
        if "/v1/" in url:
            base = url.split("/v1/")[0]
        else:
            base = _OLLAMA_BASE_URL

        try:
            resp = requests.get(base, timeout=_HEALTH_TIMEOUT)
            resp.raise_for_status()
        except Exception as exc:
            raise RuntimeError(
                f"Ollama server not running at {base}. "
                "Run 'ollama serve' first, or start start_agent.bat."
            ) from exc

        # 하드웨어 감지 및 정보 반환
        opts = self._get_optimized_options()
        has_gpu = opts.get("num_gpu", 0) > 0
        num_thread = opts.get("num_thread", 1)

        if has_gpu:
            return "ℹ️ GPU mode detected — fast inference expected"
        else:
            return (
                f"ℹ️ CPU-only mode ({num_thread} threads) — "
                "phi4-mini-reasoning: ~30-90s per response"
            )

    # ------------------------------------------------------------------ #
    # 핵심 채팅 인터페이스
    # ------------------------------------------------------------------ #

    def chat(
        self,
        system: str,
        history: List[Dict[str, str]],
        brief: bool = False,
    ) -> str:
        """Single-turn chat completion routed to the configured backend.

        Parameters
        ----------
        system  : System prompt string.
        history : Conversation history (role/content dicts).
        brief   : If True, use shorter max_output_tokens for faster response.
        """
        # brief 모드: thinking 스킵 유도 힌트를 system prompt 앞에 추가
        if brief:
            system = (
                "BRIEF MODE: Respond directly and concisely. "
                "Do NOT include <think> tags or internal reasoning. "
                "Give only the final answer.\n\n"
            ) + system
        if self.cfg.backend == "ollama":
            return self._chat_ollama(system, history, brief=brief)
        if self.cfg.backend == "http":
            return self._chat_http(system, history, brief=brief)
        raise RuntimeError(f"Unsupported LLM backend: {self.cfg.backend!r}")

    def stream_chat(
        self,
        system: str,
        history: List[Dict[str, str]],
        on_token: Callable[[str], None],
        on_done: Optional[Callable[[str, float], None]] = None,
        brief: bool = False,
        on_think_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Streaming chat — calls on_token(chunk) for each visible token.

        Parameters
        ----------
        system         : System prompt.
        history        : Conversation history.
        on_token       : Callback for each visible answer token.
        on_done        : Optional callback(full_text, elapsed_sec) on completion.
        brief          : Use shorter token limit for faster response.
        on_think_token : Optional callback for <think>…</think> reasoning tokens.
                         While inside a <think> block, tokens are routed here
                         instead of on_token so the UI can show reasoning progress
                         without cluttering the answer area.

        Returns the full assembled response string (answer only, no <think> blocks).
        """
        # brief 모드: thinking 스킵 유도 힌트를 system prompt 앞에 추가
        if brief:
            system = (
                "BRIEF MODE: Respond directly and concisely. "
                "Do NOT include <think> tags or internal reasoning. "
                "Give only the final answer.\n\n"
            ) + system
        if self.cfg.backend in ("ollama", "http"):
            return self._stream_ollama(
                system,
                history,
                on_token,
                on_done,
                brief=brief,
                on_think_token=on_think_token,
            )
        raise RuntimeError(f"Streaming not supported for backend: {self.cfg.backend!r}")

    # ------------------------------------------------------------------ #
    # Ollama 백엔드 (CP-1 신규, 권장)
    # ------------------------------------------------------------------ #

    def _chat_ollama(
        self,
        system: str,
        history: List[Dict[str, str]],
        brief: bool = False,
    ) -> str:
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

        max_tokens = _BRIEF_MAX_TOKENS if brief else self.cfg.max_output_tokens
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": False,
            "options": self._get_optimized_options(brief=brief),
        }

        # connect 10s, read 30s per chunk (non-streaming: total response timeout)
        resp = requests.post(url, json=payload, timeout=(10, 120))
        resp.raise_for_status()
        data = resp.json()

        try:
            return data["choices"][0]["message"]["content"]
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"Unexpected Ollama response format: {data!r}") from exc

    # ------------------------------------------------------------------ #
    # HTTP 백엔드 (LM Studio / 커스텀 서버 등)
    # ------------------------------------------------------------------ #

    def _stream_ollama(
        self,
        system: str,
        history: List[Dict[str, str]],
        on_token: Callable[[str], None],
        on_done: Optional[Callable[[str, float], None]],
        brief: bool = False,
        on_think_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Streaming SSE request to Ollama. Calls on_token(chunk) per visible token.

        <think>…</think> reasoning tokens from phi4-mini-reasoning are detected
        and routed to on_think_token (if provided) instead of on_token, so the UI
        can show "thinking…" feedback without polluting the answer area.
        Only the answer text (outside <think> blocks) is included in the return value.
        """
        url = self.cfg.http_url or _OLLAMA_DEFAULT_URL
        model = self.cfg.model_path or _OLLAMA_DEFAULT_MODEL
        max_tokens = _BRIEF_MAX_TOKENS if brief else self.cfg.max_output_tokens

        messages: List[Dict[str, str]] = []
        if not history or history[0].get("role") != "system":
            messages.append({"role": "system", "content": system})
        messages.extend(history)

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": True,
            "options": self._get_optimized_options(brief=brief),
        }

        t0 = time.perf_counter()
        answer_text = ""  # text outside <think> blocks
        _pending = ""  # partial token buffer for tag detection
        _in_think = False  # True while inside a <think> block

        session = self._get_session()
        # 120s 데드라인 타이머: 총 스트리밍 시간이 120s를 초과하면 session 닫기
        _deadline = threading.Timer(120.0, self.cancel)
        _deadline.start()
        try:
            with session.post(url, json=payload, stream=True, timeout=(10, 30)) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    raw = line.decode("utf-8", errors="replace")
                    if raw.startswith("data: "):
                        raw = raw[6:]
                    if raw.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(raw)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        token = delta.get("content", "")
                        if not token:
                            continue
                    except (json.JSONDecodeError, IndexError, KeyError):
                        continue

                    # ---- <think> token routing ----
                    _pending += token
                    while _pending:
                        if _in_think:
                            end_idx = _pending.find("</think>")
                            if end_idx == -1:
                                # All pending is reasoning — route to think callback
                                if on_think_token:
                                    on_think_token(_pending)
                                _pending = ""
                            else:
                                # Emit reasoning up to </think>
                                reasoning_chunk = _pending[:end_idx]
                                if reasoning_chunk and on_think_token:
                                    on_think_token(reasoning_chunk)
                                _in_think = False
                                _pending = _pending[end_idx + len("</think>") :]
                        else:
                            start_idx = _pending.find("<think>")
                            if start_idx == -1:
                                # All pending is answer text
                                answer_text += _pending
                                on_token(_pending)
                                _pending = ""
                            else:
                                # Emit answer text before <think>
                                before = _pending[:start_idx]
                                if before:
                                    answer_text += before
                                    on_token(before)
                                _in_think = True
                                _pending = _pending[start_idx + len("<think>") :]

        except Exception as exc:
            raise RuntimeError(f"Streaming error: {exc}") from exc
        finally:
            _deadline.cancel()  # 정상 완료 시 타이머 취소

        elapsed = time.perf_counter() - t0
        if on_done:
            on_done(answer_text, elapsed)
        return answer_text

    def _chat_http(
        self,
        system: str,
        history: List[Dict[str, str]],
        brief: bool = False,
    ) -> str:
        """Request to OpenAI-compatible HTTP server. http_url required."""

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

        max_tokens = _BRIEF_MAX_TOKENS if brief else self.cfg.max_output_tokens
        payload = {
            "model": self.cfg.model_path or "llama4:scout",
            "messages": messages,
            "max_tokens": max_tokens,
            "options": self._get_optimized_options(brief=brief),
        }

        resp = requests.post(self.cfg.http_url, json=payload, timeout=(10, 120))
        resp.raise_for_status()
        data = resp.json()

        try:
            return data["choices"][0]["message"]["content"]
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                f"Unexpected HTTP LLM response format: {data!r}"
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

    def recovery_action(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Determine recovery action for a failed SOP step.

        Called ONLY when automatic heuristics (popup / freeze detection) fail.
        Returns JSON: {action, target_text, reason}.

        Parameters
        ----------
        context : dict with keys:
            sop_step      : str  — current step ID
            target_button : str  — expected button text
            ocr_text      : str  — all text visible on screen (compressed)
            error_type    : str  — "button_not_found" | "popup" | "frozen"
            history       : list — last 3 step results
        """
        system = (
            "You are an OLED connector SOP agent assistant running on a Windows "
            "factory line PC. The automated SOP has encountered an exception. "
            "Analyze the situation and respond ONLY with valid JSON — no explanation, "
            "no markdown, no extra text. Use English only."
        )
        prompt = (
            f"Current SOP step: {context.get('sop_step', 'unknown')}\n"
            f"Expected button text: \"{context.get('target_button', '')}\"\n"
            f"All text visible on screen: {context.get('ocr_text', '(none)')}\n"
            f"Error type: {context.get('error_type', 'unknown')}\n"
            f"Recent step history: {context.get('history', [])}\n\n"
            "Respond with JSON only:\n"
            '{"action": "dismiss_popup|wait|restart_step|skip_step|abort", '
            '"target_text": "button text to click if action is dismiss_popup, else null", '
            '"reason": "brief explanation in English"}'
        )

        raw = self.chat(
            system=system,
            history=[{"role": "user", "content": prompt}],
            brief=True,
        )

        try:
            # Strip possible markdown fences
            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            result = json.loads(clean.strip())
            if not isinstance(result, dict):
                raise ValueError("Not a dict")
            return result
        except Exception:
            return {
                "action": "wait",
                "target_text": None,
                "reason": f"LLM response could not be parsed: {raw[:100]}",
            }

    def propose_sop_improvement(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze success patterns and propose SOP step improvements.

        Input: summary dict from CycleDetector.build_improvement_summary().
        Output: proposed changes to sop_steps.json for engineer review.

        The result is saved as sop_steps.proposed.json — never auto-applied.
        """
        system = (
            "You are an expert OLED connector SOP engineer. "
            "Analyze the success/failure patterns below and suggest minimal improvements "
            "to the SOP step configuration. "
            "Respond ONLY with a JSON object. Use English only."
        )
        prompt = (
            f"SOP run statistics (last {summary.get('sample_count', 0)} runs):\n"
            f"{json.dumps(summary, indent=2, ensure_ascii=False)}\n\n"
            "Suggest improvements as JSON:\n"
            '{"step_changes": [{"step_id": "...", "field": "...", "new_value": "...", '
            '"reason": "..."}], '
            '"summary": "brief overall assessment in English"}'
        )

        raw = self.chat(
            system=system,
            history=[{"role": "user", "content": prompt}],
        )

        try:
            clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            return json.loads(clean)
        except Exception:
            return {"step_changes": [], "summary": raw[:500], "raw": raw}
