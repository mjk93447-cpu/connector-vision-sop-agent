"""Ollama model capability registry for SOP generation and chat roles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ModelCapability:
    tag: str
    local_offline: bool
    context_window: int
    multimodal: bool
    structured_output: bool
    tool_calling: bool
    min_ram_gb: int
    role: str
    notes: str = ""


# Latest-first survey as of 2026-06-09 (offline line PC policy).
_MODEL_CAPABILITIES: Tuple[ModelCapability, ...] = (
    ModelCapability(
        tag="qwen3.7",
        local_offline=False,
        context_window=0,
        multimodal=True,
        structured_output=False,
        tool_calling=False,
        min_ram_gb=0,
        role="unavailable",
        notes="Weights not published; Ollama library 404. API/preview only.",
    ),
    ModelCapability(
        tag="kimi-k2.6",
        local_offline=False,
        context_window=262144,
        multimodal=True,
        structured_output=True,
        tool_calling=True,
        min_ram_gb=0,
        role="unavailable",
        notes="Ollama Cloud only (kimi-k2.6:cloud). Not usable offline.",
    ),
    ModelCapability(
        tag="qwen3.6:35b",
        local_offline=True,
        context_window=256000,
        multimodal=True,
        structured_output=True,
        tool_calling=True,
        min_ram_gb=24,
        role="sop_generation",
        notes="Best agentic quality; exceeds 16GB RAM.",
    ),
    ModelCapability(
        tag="qwen3.6:27b",
        local_offline=True,
        context_window=256000,
        multimodal=True,
        structured_output=True,
        tool_calling=True,
        min_ram_gb=17,
        role="sop_generation",
        notes="Borderline on 16GB CPU-only hosts.",
    ),
    ModelCapability(
        tag="qwen3:8b",
        local_offline=True,
        context_window=256000,
        multimodal=False,
        structured_output=True,
        tool_calling=True,
        min_ram_gb=8,
        role="sop_generation_primary",
        notes="Recommended primary for 16GB offline SOP Generate.",
    ),
    ModelCapability(
        tag="qwen3:4b",
        local_offline=True,
        context_window=256000,
        multimodal=False,
        structured_output=True,
        tool_calling=True,
        min_ram_gb=4,
        role="sop_generation_lite",
        notes="Fastest / lowest memory SOP Generate option.",
    ),
    ModelCapability(
        tag="gemma4:9b",
        local_offline=True,
        context_window=131072,
        multimodal=True,
        structured_output=True,
        tool_calling=True,
        min_ram_gb=10,
        role="chat_recovery",
        notes="Reliable tool calling for Chat and recovery_action.",
    ),
    ModelCapability(
        tag="gemma4:26b-a4b-it-q4_K_M",
        local_offline=True,
        context_window=262144,
        multimodal=True,
        structured_output=True,
        tool_calling=True,
        min_ram_gb=16,
        role="legacy_chat",
        notes="Legacy default; too heavy for 16GB SOP Generate primary.",
    ),
)

_DEFAULT_SOP_GENERATION_TAG = "qwen3:8b"
_DEFAULT_SOP_GENERATION_LITE_TAG = "qwen3:4b"
_DEFAULT_CHAT_TAG = "gemma4:9b"


def list_capabilities() -> List[ModelCapability]:
    return list(_MODEL_CAPABILITIES)


def get_capability(model_tag: str) -> Optional[ModelCapability]:
    normalized = model_tag.strip().lower()
    for cap in _MODEL_CAPABILITIES:
        if cap.tag.lower() == normalized:
            return cap
    prefix = normalized.split(":")[0]
    for cap in _MODEL_CAPABILITIES:
        if cap.tag.lower().startswith(prefix):
            return cap
    return None


def is_local_offline_model(model_tag: str) -> bool:
    cap = get_capability(model_tag)
    if cap is not None:
        return cap.local_offline
    return ":" in model_tag and not model_tag.endswith(":cloud")


def recommend_sop_generation_tag(ram_gb: int = 16, lite: bool = False) -> str:
    if lite or ram_gb < 12:
        return _DEFAULT_SOP_GENERATION_LITE_TAG
    if ram_gb < 20:
        return _DEFAULT_SOP_GENERATION_TAG
    return "qwen3.6:27b"


def recommend_chat_tag(ram_gb: int = 16) -> str:
    if ram_gb >= 20:
        return "gemma4:26b-a4b-it-q4_K_M"
    return _DEFAULT_CHAT_TAG


def validate_sop_generation_model(model_tag: str) -> None:
    cap = get_capability(model_tag)
    if cap is not None and not cap.local_offline:
        raise RuntimeError(
            f"SOP Generate requires a local offline Ollama model; '{model_tag}' is not available offline. "
            f"Use {recommend_sop_generation_tag()} instead."
        )
    if model_tag.endswith(":cloud"):
        raise RuntimeError(
            f"SOP Generate cannot use cloud-only model '{model_tag}' in offline mode."
        )


def capability_summary(model_tag: str) -> Dict[str, object]:
    cap = get_capability(model_tag)
    if cap is None:
        return {
            "tag": model_tag,
            "local_offline": is_local_offline_model(model_tag),
            "known": False,
        }
    return {
        "tag": cap.tag,
        "local_offline": cap.local_offline,
        "context_window": cap.context_window,
        "multimodal": cap.multimodal,
        "structured_output": cap.structured_output,
        "tool_calling": cap.tool_calling,
        "min_ram_gb": cap.min_ram_gb,
        "role": cap.role,
        "notes": cap.notes,
        "known": True,
    }


def models_for_role(role: str) -> List[str]:
    return [
        cap.tag for cap in _MODEL_CAPABILITIES if cap.role == role and cap.local_offline
    ]
