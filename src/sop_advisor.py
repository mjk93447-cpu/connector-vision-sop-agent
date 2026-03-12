"""
SOP & vision auto-tuning helpers (Phase 4 skeleton).

This module does NOT automatically modify the live config. Instead it:

- Interprets LLM output (config_patch, sop_recommendations).
- Applies safe, validated patches to an in-memory config.
- Writes proposed configs to a separate `assets/config.proposed.json` file.
- Summarizes failure patterns from recent events, to help the LLM and humans.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple


SAFE_NUMERIC_RANGES: Dict[str, Tuple[float, float]] = {
    "ocr_threshold": (0.3, 0.95),
    "pin_count_min": (0.0, 1000.0),
    "confidence_threshold": (0.1, 0.99),
}


def _set_nested(config: Dict[str, Any], key: str, value: Any) -> None:
    """Set a potentially dotted key (e.g. 'vision.confidence_threshold')."""

    parts = key.split(".")
    cursor: Dict[str, Any] = config
    for part in parts[:-1]:
        if part not in cursor or not isinstance(cursor[part], dict):
            cursor[part] = {}
        cursor = cursor[part]  # type: ignore[assignment]
    cursor[parts[-1]] = value


def apply_config_patch(config: Dict[str, Any], patch: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """
    Apply a suggested config_patch to an in-memory config with basic safety checks.

    - Supports both top-level keys and dotted keys (e.g. 'vision.confidence_threshold').
    - Checks numeric keys against SAFE_NUMERIC_RANGES when possible.
    - Returns (new_config, warnings).
    """

    new_config = json.loads(json.dumps(config))  # deep copy via JSON
    warnings: List[str] = []

    for key, value in patch.items():
        simple_key = key.split(".")[-1]
        if isinstance(value, (int, float)) and simple_key in SAFE_NUMERIC_RANGES:
            lo, hi = SAFE_NUMERIC_RANGES[simple_key]
            if not (lo <= float(value) <= hi):
                warnings.append(
                    f"Key '{key}' with value {value!r} is outside safe range [{lo}, {hi}]; skipping."
                )
                continue

        try:
            _set_nested(new_config, key, value)
        except Exception as exc:  # pragma: no cover - defensive guard
            warnings.append(f"Failed to apply patch for key '{key}': {exc!r}")

    return new_config, warnings


def write_proposed_config(base_path: str | Path, new_config: Dict[str, Any]) -> Path:
    """
    Write a proposed config JSON next to the base config without overwriting it.

    Example:
      base_path = 'assets/config.json'
      -> writes 'assets/config.proposed.json'
    """

    base = Path(base_path)
    proposed = base.with_name("config.proposed.json")
    with proposed.open("w", encoding="utf-8") as stream:
        json.dump(new_config, stream, ensure_ascii=False, indent=2)
    return proposed


def summarize_failures(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Summarize failure patterns from a list of events.

    Expected event shape (LogEvent.asdict()):
      { "ts": "...", "level": "ERROR", "step": "...", "message": "...", "data": {...} }
    """

    by_step: Dict[str, int] = {}
    by_message: Dict[str, int] = {}

    for ev in events:
        level = str(ev.get("level", "")).upper()
        if level != "ERROR":
            continue
        step = str(ev.get("step", "unknown"))
        msg = str(ev.get("message", ""))
        by_step[step] = by_step.get(step, 0) + 1
        if msg:
            by_message[msg] = by_message.get(msg, 0) + 1

    return {
        "error_counts_by_step": by_step,
        "error_counts_by_message": by_message,
    }


def propose_actions(llm_output: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Normalize LLM output into a list of action dicts for human review.

    LLM output is expected to contain:
      - config_patch: dict
      - sop_recommendations: list[str]
    """

    actions: List[Dict[str, Any]] = []
    patch = llm_output.get("config_patch") or {}
    recs = llm_output.get("sop_recommendations") or []

    for key, value in patch.items():
        actions.append(
            {
                "type": "config_patch",
                "key": key,
                "value": value,
                "description": f"Update config key '{key}' to {value!r}",
            }
        )

    for rec in recs:
        actions.append(
            {
                "type": "sop_recommendation",
                "description": rec,
            }
        )

    return actions

