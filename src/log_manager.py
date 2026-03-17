"""
Structured logging, screenshot capture, and LLM-ready analysis scaffolding.

This module is designed for the Samsung OLED line SOP agent:

- Collects **JSON-structured logs** per SOP run (steps, timings, results, errors).
- Persists **image snapshots** (NumPy arrays or PIL Images) for later review.
- Prepares a compact **LLM analysis payload** so a model such as Qwen2.5-VL
  can diagnose failures and propose config/SOP adjustments.

Actual LLM API calls are intentionally left out so that:
- Offline EXE builds remain dependency-light.
- The line PC or a separate “LLM console” can wire in Qwen2.5-VL using the
  environment (REST endpoint, SDK, etc.).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image


ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def _now_iso() -> str:
    return datetime.utcnow().strftime(ISO_FORMAT)


@dataclass
class LogEvent:
    """Single structured log event for one SOP run."""

    ts: str
    level: str
    step: str
    message: str
    data: Dict[str, Any]


@dataclass
class RunSummary:
    """High-level summary metadata for a completed SOP run."""

    run_id: str
    started_at: str
    finished_at: str
    duration_sec: float
    success: bool
    error: str = ""
    notes: str = ""


class LogManager:
    """Manage JSON logs, screenshots, and LLM-ready analysis payloads."""

    def __init__(
        self,
        base_dir: str | Path = "logs",
        run_id: Optional[str] = None,
    ) -> None:
        base = Path(base_dir)
        base.mkdir(parents=True, exist_ok=True)

        if run_id is None:
            # Example: 2026-03-12T09-30-15Z_run-123456
            run_id = (
                datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
                + f"_run-{int(time.time())}"
            )

        self.base_dir = base
        self.run_id = run_id
        self.run_dir = base / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

        self.events: List[LogEvent] = []
        self.screenshots: List[Path] = []
        self.started_at = _now_iso()

        self._events_path = self.run_dir / "events.jsonl"
        self._summary_path = self.run_dir / "summary.json"

    # --------------------------------------------------------------------- #
    # Event logging
    # --------------------------------------------------------------------- #

    def log(
        self,
        step: str,
        message: str,
        level: str = "INFO",
        **data: Any,
    ) -> None:
        """Append a structured event to the in-memory buffer and JSONL file."""

        event = LogEvent(
            ts=_now_iso(),
            level=level.upper(),
            step=step,
            message=message,
            data=data,
        )
        self.events.append(event)

        # Write as JSON Lines for easy streaming/analysis.
        with self._events_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")

    def log_error(self, step: str, message: str, **data: Any) -> None:
        self.log(step=step, message=message, level="ERROR", **data)

    # --------------------------------------------------------------------- #
    # Screenshot capture helpers
    # --------------------------------------------------------------------- #

    def save_screenshot(
        self,
        image: np.ndarray | Image.Image,
        name: Optional[str] = None,
    ) -> Path:
        """Persist a screenshot PNG in the run directory and return its path."""

        screenshots_dir = self.run_dir / "screens"
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        if name is None:
            name = datetime.utcnow().strftime("%H%M%S_%f") + ".png"
        elif not name.lower().endswith(".png"):
            name = f"{name}.png"

        path = screenshots_dir / name

        if isinstance(image, Image.Image):
            pil_img = image
        else:
            # Assume HxWxC in BGR or RGB; PIL expects RGB.
            array = image
            if array.ndim == 2:
                pil_img = Image.fromarray(array.astype("uint8"), mode="L")
            else:
                # Best-effort: if it's likely BGR (OpenCV), flip to RGB.
                if array.shape[2] == 3:
                    b, g, r = np.dsplit(array, 3)
                    rgb = np.dstack((r, g, b))
                    pil_img = Image.fromarray(rgb.astype("uint8"), mode="RGB")
                else:
                    pil_img = Image.fromarray(array.astype("uint8"))

        pil_img.save(path)
        self.screenshots.append(path)
        self.log("screenshot", f"Saved screenshot {path.name}", path=str(path))
        return path

    # --------------------------------------------------------------------- #
    # Run completion & summary
    # --------------------------------------------------------------------- #

    def finalize(
        self,
        success: bool,
        error: str = "",
        notes: str = "",
    ) -> RunSummary:
        """Write a summary.json for the run and return the summary object."""

        finished_at = _now_iso()
        started_dt = datetime.strptime(self.started_at, ISO_FORMAT)
        finished_dt = datetime.strptime(finished_at, ISO_FORMAT)
        duration = (finished_dt - started_dt).total_seconds()

        summary = RunSummary(
            run_id=self.run_id,
            started_at=self.started_at,
            finished_at=finished_at,
            duration_sec=duration,
            success=success,
            error=error,
            notes=notes,
        )

        with self._summary_path.open("w", encoding="utf-8") as stream:
            json.dump(asdict(summary), stream, ensure_ascii=False, indent=2)

        return summary

    # --------------------------------------------------------------------- #
    # LLM analysis scaffolding
    # --------------------------------------------------------------------- #

    def build_llm_payload(
        self, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build a compact JSON payload that an external LLM (e.g. Qwen2.5-VL) can consume.

        The payload intentionally keeps text small enough to send over APIs while
        preserving the most important context:

        - summary.json (if present)
        - last N events
        - paths to key screenshots
        - current config snapshot (if provided)
        """

        last_events = [
            asdict(ev) for ev in self.events[-50:]
        ]  # last 50 events in memory

        summary: Dict[str, Any] = {}
        if self._summary_path.exists():
            with self._summary_path.open("r", encoding="utf-8") as stream:
                summary = json.load(stream)

        payload: Dict[str, Any] = {
            "run_id": self.run_id,
            "summary": summary,
            "events_tail": last_events,
            "screenshots": [str(path) for path in self.screenshots],
            "config_snapshot": config or {},
            "generated_at": _now_iso(),
        }
        return payload

    def analyze_with_llm(
        self,
        config: Optional[Dict[str, Any]] = None,
        model: str = "Qwen2.5-VL",
    ) -> Dict[str, Any]:
        """
        Run an offline LLM analysis when configured, otherwise fall back to a stub.

        Behavior:
        - If ``config`` is None or does not contain a truthy ``llm.enabled``,
          return a no-op envelope.
        - If an error occurs while constructing or calling the offline LLM,
          return a stub envelope with the error message attached.
        """

        payload = self.build_llm_payload(config=config)

        llm_cfg = (config or {}).get("llm") or {}
        enabled = bool(llm_cfg.get("enabled"))
        if not enabled:
            return {
                "model": model,
                "payload": payload,
                "config_patch": {},
                "sop_recommendations": [],
                "raw_text": "",
                "note": "LLM disabled in config or no llm block present.",
            }

        try:
            from src.llm_offline import OfflineLLM
        except Exception as exc:  # pragma: no cover - optional dependency
            return {
                "model": model,
                "payload": payload,
                "config_patch": {},
                "sop_recommendations": [],
                "raw_text": "",
                "note": f"OfflineLLM import failed: {exc!r}",
            }

        try:
            offline_llm = OfflineLLM.from_config(llm_cfg)
            analysis = offline_llm.analyze_logs(payload)
            # Ensure contract is stable even if backend returns partial keys.
            return {
                "model": model,
                "payload": payload,
                "config_patch": analysis.get("config_patch", {}),
                "sop_recommendations": analysis.get("sop_recommendations", []),
                "raw_text": analysis.get("raw_text", ""),
                "note": "",
            }
        except Exception as exc:  # pragma: no cover - defensive guard
            return {
                "model": model,
                "payload": payload,
                "config_patch": {},
                "sop_recommendations": [],
                "raw_text": "",
                "note": f"LLM analysis failed: {exc!r}",
            }
