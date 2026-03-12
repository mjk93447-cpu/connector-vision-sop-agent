"""
Offline LLM integration for Connector Vision SOP Agent.

This module is responsible for talking to a **local** LLM backend on the
line PC (no internet). It supports two backends:

- ``llama_cpp``: direct GGUF loading via `llama-cpp-python`
- ``http``: a local HTTP server (LM Studio, Ollama, etc.) that exposes a
  Qwen-compatible chat API.

The goal is to keep this module self-contained and optionally import any
heavy dependencies. If a backend is misconfigured or unavailable, callers
should receive a clear, non-crashing error.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Type


BackendType = Literal["llama_cpp", "http"]


@dataclass
class LLMConfig:
    backend: BackendType = "llama_cpp"
    model_path: str | None = None
    ctx_size: int = 4096
    gpu_layers: int = 0
    http_url: str | None = None
    max_input_tokens: int = 4096
    max_output_tokens: int = 512

    @classmethod
    def from_dict(cls: Type["LLMConfig"], data: Dict[str, Any]) -> "LLMConfig":
        return cls(
            backend=data.get("backend", "llama_cpp"),
            model_path=data.get("model_path"),
            ctx_size=int(data.get("ctx_size", 4096)),
            gpu_layers=int(data.get("gpu_layers", 0)),
            http_url=data.get("http_url"),
            max_input_tokens=int(data.get("max_input_tokens", 4096)),
            max_output_tokens=int(data.get("max_output_tokens", 512)),
        )


class OfflineLLM:
    """Lightweight wrapper around a local LLM instance.

    This class intentionally does not import heavy dependencies at module
    import time. Instead, imports occur inside methods so that:

    - The EXE can run even when the LLM runtime is not installed.
    - Errors are surfaced as clear RuntimeError messages.
    """

    def __init__(self, cfg: LLMConfig) -> None:
        self.cfg = cfg

    # ------------------------------------------------------------------ #
    # Constructors
    # ------------------------------------------------------------------ #

    @classmethod
    def from_config(cls, cfg_dict: Dict[str, Any]) -> "OfflineLLM":
        cfg = LLMConfig.from_dict(cfg_dict)
        return cls(cfg)

    # ------------------------------------------------------------------ #
    # Core chat interface
    # ------------------------------------------------------------------ #

    def chat(self, system: str, history: List[Dict[str, str]]) -> str:
        """Run a single-turn chat completion with the local LLM.

        `history` is a list of {role, content} messages. This method always
        appends the system prompt as the first message if not already present.
        """

        if self.cfg.backend == "llama_cpp":
            return self._chat_llama_cpp(system, history)
        if self.cfg.backend == "http":
            return self._chat_http(system, history)
        raise RuntimeError(f"Unsupported LLM backend: {self.cfg.backend!r}")

    def _chat_llama_cpp(self, system: str, history: List[Dict[str, str]]) -> str:
        try:
            from llama_cpp import Llama  # type: ignore[import]
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "llama-cpp-python is not installed; cannot use 'llama_cpp' backend."
            ) from exc

        if not self.cfg.model_path:
            raise RuntimeError("LLMConfig.model_path is required for 'llama_cpp' backend.")

        # Build chat messages, ensuring system prompt is first.
        messages: List[Dict[str, str]] = []
        if not history or history[0].get("role") != "system":
            messages.append({"role": "system", "content": system})
        messages.extend(history)

        llm = Llama(
            model_path=self.cfg.model_path,
            n_ctx=self.cfg.ctx_size,
            n_gpu_layers=self.cfg.gpu_layers,
            # NOTE: other performance knobs (threads, batch_size) can be added later.
        )

        result = llm.create_chat_completion(
            messages=messages,
            max_tokens=self.cfg.max_output_tokens,
        )
        # Qwen-style chat APIs typically return the answer in choices[0].message.content
        try:
            return result["choices"][0]["message"]["content"]
        except Exception as exc:  # pragma: no cover - defensive
            raise RuntimeError(f"Unexpected Llama chat response format: {result!r}") from exc

    def _chat_http(self, system: str, history: List[Dict[str, str]]) -> str:
        try:
            import requests  # type: ignore[import]
        except Exception as exc:  # pragma: no cover - optional dependency
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
            "model": self.cfg.model_path or "qwen2.5-vl-7b",
            "messages": messages,
            "max_tokens": self.cfg.max_output_tokens,
        }

        resp = requests.post(self.cfg.http_url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        # Qwen-compatible HTTP APIs often mirror OpenAI's format.
        try:
            return data["choices"][0]["message"]["content"]
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"Unexpected HTTP LLM response format: {data!r}") from exc

    # ------------------------------------------------------------------ #
    # Log-aware analysis helper
    # ------------------------------------------------------------------ #

    def analyze_logs(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Use the LLM to analyze a SOP run payload and suggest adjustments.

        The prompt is designed to be model-agnostic and should work with
        Qwen2.5-VL and related models.
        """

        system = (
            "You are an expert Samsung OLED connector SOP and machine vision "
            "engineer. You receive structured logs, a summary, and configuration "
            "for an automation run. Diagnose issues and propose safe, minimal "
            "changes to improve robustness. Return a short JSON with keys:\n"
            "- config_patch: dict of keys to update in config.json\n"
            "- sop_recommendations: list of human-readable suggestions\n"
            "- raw_text: your full reasoning in natural language"
        )

        # We send a single user message with the payload as JSON text.
        import json

        user_content = json.dumps(payload, ensure_ascii=False)

        history = [
            {"role": "user", "content": f"Here is the latest SOP run payload:\n{user_content}"}
        ]

        raw = self.chat(system=system, history=history)

        # Try to parse a JSON object from the model output; if parsing fails,
        # wrap the raw text in the expected envelope.
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

