"""
Unit tests for src/cycle_detector.py.

Uses a temporary directory for JSONL storage — no external dependencies.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.cycle_detector import CycleDetector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_step(
    step_id: str,
    method: str = "ocr",
    elapsed_ms: int = 200,
    success: bool = True,
) -> Dict[str, Any]:
    return {
        "step_id": step_id,
        "method": method,
        "elapsed_ms": elapsed_ms,
        "success": success,
    }


def _make_run(
    run_id: str = "run_001",
    steps: List[Dict[str, Any]] | None = None,
    total_ms: int = 2000,
    timestamp: float | None = None,
) -> Dict[str, Any]:
    return {
        "run_id": run_id,
        "timestamp": timestamp or time.time(),
        "steps": steps or [_make_step("login"), _make_step("save")],
        "total_ms": total_ms,
    }


_STANDARD_STEPS = [
    _make_step("login"),
    _make_step("open_recipe"),
    _make_step("mold_left_roi", method="yolo"),
    _make_step("save"),
]


# ---------------------------------------------------------------------------
# record_success / load_recent
# ---------------------------------------------------------------------------


class TestRecordAndLoad:
    def test_record_creates_file(self, tmp_path: Path) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "patterns.jsonl")
        cd.record_success(_make_run())
        assert (tmp_path / "patterns.jsonl").exists()

    def test_record_appends_lines(self, tmp_path: Path) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "patterns.jsonl")
        cd.record_success(_make_run("r1"))
        cd.record_success(_make_run("r2"))
        lines = (tmp_path / "patterns.jsonl").read_text().strip().splitlines()
        assert len(lines) == 2

    def test_record_valid_json(self, tmp_path: Path) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "patterns.jsonl")
        cd.record_success(_make_run("r1"))
        line = (tmp_path / "patterns.jsonl").read_text().strip()
        parsed = json.loads(line)
        assert parsed["run_id"] == "r1"

    def test_load_recent_returns_empty_when_no_file(self, tmp_path: Path) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "missing.jsonl")
        assert cd.load_recent() == []

    def test_load_recent_returns_all_if_under_limit(self, tmp_path: Path) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "p.jsonl")
        for i in range(5):
            cd.record_success(_make_run(f"run_{i}"))
        records = cd.load_recent(20)
        assert len(records) == 5

    def test_load_recent_respects_limit(self, tmp_path: Path) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "p.jsonl")
        for i in range(15):
            cd.record_success(_make_run(f"run_{i}"))
        records = cd.load_recent(5)
        assert len(records) == 5

    def test_load_recent_skips_malformed_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "p.jsonl"
        path.write_text('{"run_id": "good"}\nNOT_JSON\n{"run_id": "also_good"}\n')
        cd = CycleDetector(patterns_path=path)
        records = cd.load_recent(10)
        assert len(records) == 2

    def test_record_run_convenience(self, tmp_path: Path) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "p.jsonl")
        start = time.time() - 2  # 2 seconds ago
        cd.record_run("run_x", [_make_step("login"), _make_step("save")], start)
        records = cd.load_recent()
        assert len(records) == 1
        assert records[0]["run_id"] == "run_x"
        assert records[0]["total_ms"] >= 1000  # at least 1s elapsed

    def test_record_ignores_write_errors_gracefully(self, tmp_path: Path) -> None:
        """record_success should not raise on write failure."""
        cd = CycleDetector(patterns_path=Path("/nonexistent_dir/patterns.jsonl"))
        # Should not raise
        cd.record_success(_make_run())


# ---------------------------------------------------------------------------
# detect_cycles
# ---------------------------------------------------------------------------


class TestDetectCycles:
    def test_returns_empty_with_no_data(self, tmp_path: Path) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "p.jsonl")
        assert cd.detect_cycles() == []

    def test_returns_empty_with_single_run(self, tmp_path: Path) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "p.jsonl")
        cd.record_success(_make_run("r1", steps=_STANDARD_STEPS))
        assert cd.detect_cycles() == []

    def test_detects_repeated_sequence(self, tmp_path: Path) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "p.jsonl")
        for i in range(5):
            cd.record_success(
                _make_run(f"run_{i}", steps=_STANDARD_STEPS, total_ms=2000)
            )
        patterns = cd.detect_cycles()
        assert len(patterns) >= 1
        assert patterns[0].sample_count >= 2

    def test_cycle_pattern_fields(self, tmp_path: Path) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "p.jsonl")
        for i in range(3):
            cd.record_success(
                _make_run(f"run_{i}", steps=_STANDARD_STEPS, total_ms=2000)
            )
        patterns = cd.detect_cycles()
        assert len(patterns) >= 1
        p = patterns[0]
        assert isinstance(p.steps, list)
        assert isinstance(p.avg_ms, int)
        assert 0.0 <= p.success_rate <= 1.0
        assert 0.0 <= p.ocr_method_rate <= 1.0
        assert p.sample_count >= 2

    def test_avg_ms_calculation(self, tmp_path: Path) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "p.jsonl")
        for ms in [1000, 2000, 3000]:
            cd.record_success(_make_run("r", steps=_STANDARD_STEPS, total_ms=ms))
        patterns = cd.detect_cycles()
        assert len(patterns) >= 1
        assert patterns[0].avg_ms == 2000  # (1000+2000+3000)/3

    def test_ocr_method_rate(self, tmp_path: Path) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "p.jsonl")
        half_ocr_steps = [
            _make_step("login", method="ocr"),
            _make_step("save", method="yolo"),
        ]
        for i in range(4):
            cd.record_success(_make_run(f"r{i}", steps=half_ocr_steps))
        patterns = cd.detect_cycles()
        assert len(patterns) >= 1
        assert abs(patterns[0].ocr_method_rate - 0.5) < 0.01

    def test_different_sequences_separate_patterns(self, tmp_path: Path) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "p.jsonl")
        seq_a = [_make_step("login"), _make_step("save")]
        seq_b = [_make_step("login"), _make_step("apply")]
        for i in range(3):
            cd.record_success(_make_run(f"a{i}", steps=seq_a))
        for i in range(3):
            cd.record_success(_make_run(f"b{i}", steps=seq_b))
        patterns = cd.detect_cycles()
        assert len(patterns) == 2


# ---------------------------------------------------------------------------
# get_fast_path
# ---------------------------------------------------------------------------


class TestGetFastPath:
    def test_returns_none_when_no_data(self, tmp_path: Path) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "p.jsonl")
        assert cd.get_fast_path("login") is None

    def test_returns_none_for_unknown_step(self, tmp_path: Path) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "p.jsonl")
        cd.record_success(_make_run("r1", steps=[_make_step("login")]))
        assert cd.get_fast_path("nonexistent_step") is None

    def test_returns_dict_with_expected_keys(self, tmp_path: Path) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "p.jsonl")
        cd.record_success(_make_run("r1", steps=[_make_step("login", elapsed_ms=300)]))
        result = cd.get_fast_path("login")
        assert result is not None
        assert "avg_ms" in result
        assert "best_method" in result
        assert "success_rate" in result
        assert "sample_count" in result

    def test_avg_ms_correct(self, tmp_path: Path) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "p.jsonl")
        for ms in [200, 400, 600]:
            cd.record_success(
                _make_run(f"r{ms}", steps=[_make_step("login", elapsed_ms=ms)])
            )
        result = cd.get_fast_path("login")
        assert result is not None
        assert result["avg_ms"] == 400  # (200+400+600)/3

    def test_best_method_most_common(self, tmp_path: Path) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "p.jsonl")
        cd.record_success(_make_run("r1", steps=[_make_step("login", method="ocr")]))
        cd.record_success(_make_run("r2", steps=[_make_step("login", method="ocr")]))
        cd.record_success(_make_run("r3", steps=[_make_step("login", method="yolo")]))
        result = cd.get_fast_path("login")
        assert result is not None
        assert result["best_method"] == "ocr"

    def test_only_counts_successful_steps(self, tmp_path: Path) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "p.jsonl")
        cd.record_success(
            _make_run(
                "r1",
                steps=[
                    _make_step("login", elapsed_ms=100, success=True),
                    _make_step("login", elapsed_ms=999, success=False),
                ],
            )
        )
        result = cd.get_fast_path("login")
        assert result is not None
        assert result["avg_ms"] == 100  # only the successful step counted


# ---------------------------------------------------------------------------
# build_improvement_summary
# ---------------------------------------------------------------------------


class TestBuildImprovementSummary:
    def test_empty_when_no_data(self, tmp_path: Path) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "p.jsonl")
        summary = cd.build_improvement_summary()
        assert summary["sample_count"] == 0
        assert summary["step_stats"] == {}
        assert summary["patterns"] == []

    def test_includes_all_expected_keys(self, tmp_path: Path) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "p.jsonl")
        for i in range(3):
            cd.record_success(_make_run(f"r{i}", steps=_STANDARD_STEPS))
        summary = cd.build_improvement_summary()
        assert "sample_count" in summary
        assert "step_stats" in summary
        assert "patterns" in summary

    def test_step_stats_computed_per_step(self, tmp_path: Path) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "p.jsonl")
        steps = [_make_step("login"), _make_step("save")]
        for i in range(3):
            cd.record_success(_make_run(f"r{i}", steps=steps))
        summary = cd.build_improvement_summary()
        assert "login" in summary["step_stats"]
        assert "save" in summary["step_stats"]

    def test_step_stats_success_rate(self, tmp_path: Path) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "p.jsonl")
        cd.record_success(
            _make_run(
                "r1",
                steps=[
                    _make_step("login", success=True),
                    _make_step("login", success=False),
                ],
            )
        )
        summary = cd.build_improvement_summary()
        stats = summary["step_stats"]["login"]
        assert stats["success_rate"] == pytest.approx(0.5)

    def test_sample_count_correct(self, tmp_path: Path) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "p.jsonl")
        for i in range(7):
            cd.record_success(_make_run(f"r{i}", steps=_STANDARD_STEPS))
        summary = cd.build_improvement_summary()
        assert summary["sample_count"] == 7

    def test_dominant_method_in_step_stats(self, tmp_path: Path) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "p.jsonl")
        for i in range(3):
            cd.record_success(
                _make_run(f"r{i}", steps=[_make_step("login", method="ocr")])
            )
        summary = cd.build_improvement_summary()
        assert summary["step_stats"]["login"]["dominant_method"] == "ocr"

    def test_patterns_list_populated_with_repeated_sequences(
        self, tmp_path: Path
    ) -> None:
        cd = CycleDetector(patterns_path=tmp_path / "p.jsonl")
        for i in range(5):
            cd.record_success(_make_run(f"r{i}", steps=_STANDARD_STEPS))
        summary = cd.build_improvement_summary()
        assert len(summary["patterns"]) >= 1
        p = summary["patterns"][0]
        assert "steps" in p
        assert "avg_ms" in p
        assert "success_rate" in p
        assert "ocr_method_rate" in p
