"""
SOP Cycle Detector — success pattern recording and analysis.

Records each successful SOP run to a JSONL file, then:
  - detect_cycles()  : finds repeating step patterns across recent runs
  - get_fast_path()  : returns timing/method hints from previous successes
  - propose_improvements() : summarizes patterns for LLM analysis

The recorded data is used by the LLM to propose sop_steps.proposed.json
improvements — which engineers can review and approve (no auto-apply).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_PATTERNS_PATH = Path("logs/success_patterns.jsonl")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class StepRecord:
    """Single step result within a run record."""

    step_id: str
    method: str  # "ocr" | "yolo" | "drag" | "validate_pins"
    elapsed_ms: int
    success: bool


@dataclass
class RunRecord:
    """Single successful SOP run."""

    run_id: str
    timestamp: float
    steps: List[StepRecord]
    total_ms: int


@dataclass
class CyclePattern:
    """Detected repeating pattern across multiple runs."""

    steps: List[str]  # step_id sequence
    avg_ms: int  # average total time
    success_rate: float  # fraction of runs fully successful
    ocr_method_rate: float  # fraction of steps resolved by OCR
    sample_count: int


# ---------------------------------------------------------------------------
# CycleDetector
# ---------------------------------------------------------------------------


class CycleDetector:
    """Record and analyze SOP run patterns for continuous improvement."""

    def __init__(
        self,
        patterns_path: Path = _DEFAULT_PATTERNS_PATH,
    ) -> None:
        self._path = patterns_path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_success(self, run: Dict[str, Any]) -> None:
        """Append a successful SOP run dict to the JSONL file.

        Expected keys:
            run_id      : str
            timestamp   : float (Unix)
            steps       : list of {step_id, method, elapsed_ms, success}
            total_ms    : int
        """
        try:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(run, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.warning("CycleDetector: failed to record run: %s", exc)

    def record_run(
        self,
        run_id: str,
        step_results: List[Dict[str, Any]],
        start_time: float,
    ) -> None:
        """Convenience method: record a run from step result dicts.

        step_results items should have: step_id, method, elapsed_ms, success.
        """
        total_ms = int((time.time() - start_time) * 1000)
        run = {
            "run_id": run_id,
            "timestamp": time.time(),
            "steps": step_results,
            "total_ms": total_ms,
        }
        self.record_success(run)

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def load_recent(self, n: int = 20) -> List[Dict[str, Any]]:
        """Load the most recent N run records from JSONL."""
        if not self._path.exists():
            return []
        lines: List[str] = []
        try:
            with self._path.open(encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as exc:
            logger.warning("CycleDetector: failed to load patterns: %s", exc)
            return []

        records = []
        for line in reversed(lines[-n * 2 :]):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(records) >= n:
                break
        return list(reversed(records))

    def detect_cycles(self, n_recent: int = 20) -> List[CyclePattern]:
        """Find repeating step patterns across the N most recent runs.

        Returns a list of CyclePattern sorted by occurrence frequency.
        """
        records = self.load_recent(n_recent)
        if len(records) < 2:
            return []

        # Extract step sequences
        sequences: List[List[str]] = []
        for rec in records:
            steps = rec.get("steps", [])
            sequences.append([s.get("step_id", "") for s in steps])

        # Find common sequence (most records have same step order)
        if not sequences:
            return []

        # Simple approach: find the modal sequence
        seq_counts: Dict[str, int] = {}
        seq_map: Dict[str, List[str]] = {}
        for seq in sequences:
            key = ",".join(seq)
            seq_counts[key] = seq_counts.get(key, 0) + 1
            seq_map[key] = seq

        # Build CyclePattern for most common sequences
        patterns: List[CyclePattern] = []
        for key, count in sorted(seq_counts.items(), key=lambda x: -x[1]):
            if count < 2:
                continue
            # Compute stats for matching runs
            matching = [
                r
                for r in records
                if ",".join(s.get("step_id", "") for s in r.get("steps", [])) == key
            ]
            total_mss = [r.get("total_ms", 0) for r in matching]
            avg_ms = int(sum(total_mss) / len(total_mss)) if total_mss else 0
            success_rate = count / len(records)

            # OCR method rate
            all_steps_flat = [s for r in matching for s in r.get("steps", [])]
            ocr_steps = [s for s in all_steps_flat if s.get("method") == "ocr"]
            ocr_rate = len(ocr_steps) / len(all_steps_flat) if all_steps_flat else 0.0

            patterns.append(
                CyclePattern(
                    steps=seq_map[key],
                    avg_ms=avg_ms,
                    success_rate=success_rate,
                    ocr_method_rate=ocr_rate,
                    sample_count=count,
                )
            )

        return patterns

    def get_fast_path(self, step_id: str) -> Optional[Dict[str, Any]]:
        """Return timing and method hints for a step from previous successes.

        Returns dict with: avg_ms, best_method, success_rate
        """
        records = self.load_recent(20)
        step_data: List[Dict[str, Any]] = []
        for rec in records:
            for step in rec.get("steps", []):
                if step.get("step_id") == step_id and step.get("success"):
                    step_data.append(step)

        if not step_data:
            return None

        avg_ms = int(sum(s.get("elapsed_ms", 0) for s in step_data) / len(step_data))
        methods = [s.get("method", "unknown") for s in step_data]
        best_method = max(set(methods), key=methods.count)

        return {
            "avg_ms": avg_ms,
            "best_method": best_method,
            "success_rate": len(step_data) / max(len(records), 1),
            "sample_count": len(step_data),
        }

    def build_improvement_summary(self, n_recent: int = 20) -> Dict[str, Any]:
        """Build a summary dict for LLM analysis → sop_steps improvements.

        This is passed to OfflineLLM.propose_sop_improvement() to generate
        a sop_steps.proposed.json that engineers can review and approve.
        """
        records = self.load_recent(n_recent)
        if not records:
            return {"patterns": [], "step_stats": {}, "sample_count": 0}

        # Per-step stats
        step_stats: Dict[str, Any] = {}
        for rec in records:
            for step in rec.get("steps", []):
                sid = step.get("step_id", "unknown")
                if sid not in step_stats:
                    step_stats[sid] = {
                        "successes": 0,
                        "failures": 0,
                        "methods": [],
                        "elapsed_ms": [],
                    }
                if step.get("success"):
                    step_stats[sid]["successes"] += 1
                else:
                    step_stats[sid]["failures"] += 1
                if step.get("method"):
                    step_stats[sid]["methods"].append(step["method"])
                if step.get("elapsed_ms"):
                    step_stats[sid]["elapsed_ms"].append(step["elapsed_ms"])

        # Compute averages
        for sid, stats in step_stats.items():
            total = stats["successes"] + stats["failures"]
            stats["success_rate"] = stats["successes"] / total if total > 0 else 0
            if stats["elapsed_ms"]:
                stats["avg_ms"] = int(
                    sum(stats["elapsed_ms"]) / len(stats["elapsed_ms"])
                )
            methods = stats["methods"]
            stats["dominant_method"] = (
                max(set(methods), key=methods.count) if methods else "unknown"
            )
            del stats["methods"], stats["elapsed_ms"]

        patterns = self.detect_cycles(n_recent)
        return {
            "sample_count": len(records),
            "step_stats": step_stats,
            "patterns": [
                {
                    "steps": p.steps,
                    "avg_ms": p.avg_ms,
                    "success_rate": p.success_rate,
                    "ocr_method_rate": p.ocr_method_rate,
                    "sample_count": p.sample_count,
                }
                for p in patterns
            ],
        }
