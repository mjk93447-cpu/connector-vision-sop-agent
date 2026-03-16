"""
Config change audit logger for Connector Vision SOP Agent.

Every time the LLM (or a manual [A] command) writes directly to config.json,
this module appends a structured record to a per-line-PC JSONL file so that
engineering management can trace:

  - WHO approved the change (username typed at the console)
  - WHEN it was approved (ISO-8601 timestamp)
  - WHAT changed (old value → new value for each key)
  - WHY (free-text reason supplied by the engineer)
  - HOW (llm_chat / llm_analysis / manual_apply)

Log file:  logs/config_audit_{line_id}.jsonl   (one JSON object per line)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Audit entry dataclass (plain dict for JSON serialisability)
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_audit_entry(
    *,
    line_id: str,
    username: str,
    action: str,
    changes: Dict[str, Dict[str, Any]],
    reason: str = "",
    llm_recommendation: str = "",
    source: str = "llm_chat",
) -> Dict[str, Any]:
    """Build a single audit record dict (not yet written to disk).

    Parameters
    ----------
    line_id:
        PC identifier from config.json (e.g. "LINE-A3").
    username:
        Name entered at the console when approving the change.
    action:
        Short verb: "config_apply", "config_revert", etc.
    changes:
        Mapping of config key → {"old": <before>, "new": <after>}.
        Example: {"control.step_delay": {"old": 0.5, "new": 1.0}}
    reason:
        Free-text explanation typed by the engineer.
    llm_recommendation:
        Raw LLM text that led to this change (for traceability).
    source:
        How the change was triggered: "llm_chat", "llm_analysis", "manual".
    """
    return {
        "ts": _now_iso(),
        "line_id": line_id,
        "username": username,
        "action": action,
        "source": source,
        "changes": changes,
        "reason": reason,
        "llm_recommendation": llm_recommendation,
    }


# ---------------------------------------------------------------------------
# Audit log writer
# ---------------------------------------------------------------------------


class ConfigAuditLog:
    """Append-only JSONL audit log scoped to a single line PC.

    Usage::

        audit = ConfigAuditLog(line_id="LINE-A3", log_dir=Path("logs"))
        audit.record(
            username="Raj Kumar",
            action="config_apply",
            changes={"control.step_delay": {"old": 0.5, "new": 1.5}},
            reason="axis_x step was timing out",
            llm_recommendation="Increase step_delay to handle slow recipe load",
            source="llm_chat",
        )
        history = audit.get_history(limit=10)
    """

    def __init__(
        self, line_id: str = "LINE-UNKNOWN", log_dir: Path | str = "logs"
    ) -> None:
        self.line_id = line_id
        self._log_dir = Path(log_dir)
        self._log_path = self._log_dir / f"config_audit_{line_id}.jsonl"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        *,
        username: str,
        action: str = "config_apply",
        changes: Dict[str, Dict[str, Any]],
        reason: str = "",
        llm_recommendation: str = "",
        source: str = "llm_chat",
    ) -> Dict[str, Any]:
        """Write one audit entry and return the dict that was written."""

        entry = build_audit_entry(
            line_id=self.line_id,
            username=username,
            action=action,
            changes=changes,
            reason=reason,
            llm_recommendation=llm_recommendation,
            source=source,
        )
        self._append(entry)
        return entry

    def get_history(self, limit: Optional[int] = 50) -> List[Dict[str, Any]]:
        """Return the most recent *limit* entries (newest last).

        Returns an empty list if the log file does not exist yet.
        """

        if not self._log_path.exists():
            return []

        entries: List[Dict[str, Any]] = []
        with self._log_path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass  # Corrupted line — skip gracefully.

        if limit is not None:
            entries = entries[-limit:]
        return entries

    def format_history_table(self, limit: int = 10) -> str:
        """Return a human-readable table of recent changes for console display."""

        entries = self.get_history(limit=limit)
        if not entries:
            return "  (no config changes recorded yet)"

        lines: List[str] = [
            f"  {'TS':<22} {'USER':<18} {'ACTION':<16} {'KEYS CHANGED'}",
            "  " + "-" * 78,
        ]
        for e in entries:
            ts = e.get("ts", "?")[:19]
            user = e.get("username", "?")[:17]
            action = e.get("action", "?")[:15]
            keys = ", ".join(e.get("changes", {}).keys())
            lines.append(f"  {ts:<22} {user:<18} {action:<16} {keys}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _append(self, entry: Dict[str, Any]) -> None:
        self._log_dir.mkdir(parents=True, exist_ok=True)
        with self._log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
