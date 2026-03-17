"""
SOP & vision auto-tuning helpers (Phase 4).

This module does NOT automatically modify the live config by default.
It can, however, apply changes DIRECTLY to config.json when the engineer
explicitly approves the change at the console and an audit record is created.

Two apply modes
---------------
1. **Proposed** (safe default):
   ``apply_config_patch()`` + ``write_proposed_config()``
   → writes ``assets/config.proposed.json``, leaves ``config.json`` untouched.

2. **Direct** (LLM-assisted, engineer-approved):
   ``apply_config_direct()``
   → patches ``config.json`` in place AND appends an entry to the audit log.
   Only available when ``config.llm.allow_config_write == true``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Safety guardrails — every numeric key that can be patched must be here.
# ---------------------------------------------------------------------------

SAFE_NUMERIC_RANGES: Dict[str, Tuple[float, float]] = {
    # Vision
    "confidence_threshold": (0.10, 0.99),
    "pin_area_min_px": (1.0, 500.0),
    # Pin validation
    "pin_count_min": (1.0, 200.0),
    "pin_count_max": (1.0, 200.0),
    # Control / timing  (seconds)
    "move_duration": (0.01, 5.0),
    "click_pause": (0.01, 5.0),
    "drag_duration": (0.01, 5.0),
    "retry_delay": (0.00, 10.0),
    "step_delay": (0.00, 10.0),
    # Control / count
    "retries": (1.0, 10.0),
    # Legacy key (kept for backward compat)
    "ocr_threshold": (0.30, 0.95),
}

# Keys that are never allowed to be patched via LLM (security).
_IMMUTABLE_KEYS = {"password", "version", "line_id"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _set_nested(config: Dict[str, Any], key: str, value: Any) -> None:
    """Set a potentially dotted key (e.g. ``'vision.confidence_threshold'``)."""

    parts = key.split(".")
    cursor: Dict[str, Any] = config
    for part in parts[:-1]:
        if part not in cursor or not isinstance(cursor[part], dict):
            cursor[part] = {}
        cursor = cursor[part]  # type: ignore[assignment]
    cursor[parts[-1]] = value


def _get_nested(config: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Get a potentially dotted key, returning *default* if not found."""

    parts = key.split(".")
    cursor: Any = config
    for part in parts:
        if not isinstance(cursor, dict):
            return default
        cursor = cursor.get(part, default)
        if cursor is default:
            return default
    return cursor


def _validate_patch(
    patch: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    """Return (safe_patch, warnings) after stripping dangerous or out-of-range keys."""

    safe: Dict[str, Any] = {}
    warnings: List[str] = []

    for key, value in patch.items():
        simple_key = key.split(".")[-1]

        # Block immutable keys.
        if simple_key in _IMMUTABLE_KEYS:
            warnings.append(f"Key '{key}' is immutable and cannot be changed via LLM.")
            continue

        # Range-check numeric values.
        if isinstance(value, (int, float)) and simple_key in SAFE_NUMERIC_RANGES:
            lo, hi = SAFE_NUMERIC_RANGES[simple_key]
            if not (lo <= float(value) <= hi):
                warnings.append(
                    f"Key '{key}' value {value!r} is outside safe range "
                    f"[{lo}, {hi}]; skipped."
                )
                continue

        safe[key] = value

    return safe, warnings


# ---------------------------------------------------------------------------
# Public API — patch helpers
# ---------------------------------------------------------------------------


def apply_config_patch(
    config: Dict[str, Any],
    patch: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    """Apply *patch* to an in-memory copy of *config* (no disk writes).

    Returns ``(new_config, warnings)``.
    """

    new_config = json.loads(json.dumps(config))  # deep copy via JSON
    safe_patch, warnings = _validate_patch(patch)

    for key, value in safe_patch.items():
        try:
            _set_nested(new_config, key, value)
        except Exception as exc:  # pragma: no cover
            warnings.append(f"Failed to apply patch for key '{key}': {exc!r}")

    return new_config, warnings


def write_proposed_config(
    base_path: str | Path,
    new_config: Dict[str, Any],
) -> Path:
    """Write proposed config to ``<base>.proposed.json`` (safe, no overwrite)."""

    base = Path(base_path)
    proposed = base.with_name("config.proposed.json")
    with proposed.open("w", encoding="utf-8") as stream:
        json.dump(new_config, stream, ensure_ascii=False, indent=2)
    return proposed


def apply_config_direct(
    config: Dict[str, Any],
    patch: Dict[str, Any],
    config_path: str | Path,
    audit_log: Any,
    *,
    username: str,
    reason: str = "",
    llm_recommendation: str = "",
    source: str = "llm_chat",
) -> Tuple[Dict[str, Any], List[str], Any]:
    """Apply *patch* DIRECTLY to ``config.json`` and write an audit entry.

    This function:
    1. Validates patch against SAFE_NUMERIC_RANGES and _IMMUTABLE_KEYS.
    2. Builds a ``changes`` dict recording old → new for each key.
    3. Writes the patched config to ``config_path`` (overwrites).
    4. Appends an audit entry via ``audit_log.record()``.

    Parameters
    ----------
    config:       Current in-memory config dict.
    patch:        Proposed changes (dotted keys accepted).
    config_path:  Path to ``assets/config.json``.
    audit_log:    A ``ConfigAuditLog`` instance.
    username:     Name supplied by the engineer at the console.
    reason:       Free-text reason for the change.
    llm_recommendation: Raw LLM text that triggered the change.
    source:       "llm_chat" | "llm_analysis" | "manual".

    Returns
    -------
    (new_config, warnings, audit_entry)
    """

    new_config, warnings = apply_config_patch(config, patch)

    # Build the changes dict (old → new) for audit.
    changes: Dict[str, Dict[str, Any]] = {}
    safe_patch, _ = _validate_patch(patch)
    for key, new_val in safe_patch.items():
        old_val = _get_nested(config, key)
        changes[key] = {"old": old_val, "new": new_val}

    if not changes:
        return new_config, warnings, None

    # Write config.json in place.
    cfg_path = Path(config_path)
    with cfg_path.open("w", encoding="utf-8") as fh:
        json.dump(new_config, fh, ensure_ascii=False, indent=2)

    # Record audit entry.
    audit_entry = audit_log.record(
        username=username,
        action="config_apply",
        changes=changes,
        reason=reason,
        llm_recommendation=llm_recommendation,
        source=source,
    )

    return new_config, warnings, audit_entry


# ---------------------------------------------------------------------------
# Failure summariser
# ---------------------------------------------------------------------------


def summarize_failures(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarize failure patterns from a list of LogEvent dicts."""

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


# ---------------------------------------------------------------------------
# Action normaliser
# ---------------------------------------------------------------------------


def suggest_training_needs(
    events: List[Dict[str, Any]],
    class_names: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Analyse failure events and suggest which YOLO classes need more training.

    Returns a list of suggestion dicts::

        [
          {
            "class": "login_button",
            "reason": "3번 미검출 — 신뢰도 < 0.6",
            "suggested_action": "Tab 7 Training 패널에서 ...",
            "priority": "high" | "medium" | "low",
          },
          ...
        ]
    """
    from src.vision_engine import DEFAULT_TARGET_LABELS  # noqa: PLC0415

    all_classes = class_names or list(DEFAULT_TARGET_LABELS)

    miss_counts: Dict[str, int] = {c: 0 for c in all_classes}
    low_conf_counts: Dict[str, int] = {c: 0 for c in all_classes}

    for ev in events:
        msg = str(ev.get("message", "")).lower()
        lvl = str(ev.get("level", "")).upper()
        if lvl not in ("ERROR", "WARNING"):
            continue
        for cls in all_classes:
            if cls.lower() in msg and (
                "not found" in msg or "미검출" in msg or "failed" in msg
            ):
                miss_counts[cls] += 1
            if cls.lower() in msg and (
                "conf" in msg or "confidence" in msg or "낮" in msg
            ):
                low_conf_counts[cls] += 1

    suggestions: List[Dict[str, Any]] = []
    for cls in all_classes:
        misses = miss_counts.get(cls, 0)
        low_conf = low_conf_counts.get(cls, 0)
        total = misses + low_conf
        if total == 0:
            continue

        if misses >= 3 or total >= 5:
            priority = "high"
        elif total >= 2:
            priority = "medium"
        else:
            priority = "low"

        reasons: List[str] = []
        if misses > 0:
            reasons.append(f"{misses}번 미검출")
        if low_conf > 0:
            reasons.append(f"{low_conf}번 낮은 신뢰도")

        suggestions.append(
            {
                "class": cls,
                "reason": ", ".join(reasons),
                "suggested_action": (
                    f"🧠 Tab 7 Training 패널에서 '{cls}' 영역 bbox를 "
                    f"5장 이상 추가한 뒤 [학습 시작] 버튼을 누르세요. "
                    f"실제 라인 화면 캡처 이미지 사용을 권장합니다."
                ),
                "priority": priority,
            }
        )

    _order = {"high": 0, "medium": 1, "low": 2}
    suggestions.sort(key=lambda s: _order.get(s.get("priority", "low"), 2))
    return suggestions


def propose_actions(llm_output: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalize LLM output into a list of action dicts for human review."""

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
