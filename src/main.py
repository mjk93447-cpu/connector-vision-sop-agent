"""
Main entry point for Connector Vision SOP Agent v1.0.

Priority path: src/main.py -> EXE build -> test validation for Samsung OLED
line deployment with YOLO, OCR, PyAutoGUI, JSON logging, and retry handling.

When packaged as an EXE on the line PC, this module also exposes a simple
hybrid console UI so engineers can:

- See first-run guidance and usage examples.
- Start/stop the 12-step SOP run.
- Adjust basic speed presets (slow/normal/fast) that map to click/drag timing.
- Trigger an optional LLM analysis pass over the latest run logs when wired.
"""

from __future__ import annotations

from typing import Literal

from pathlib import Path
import json

from src.config_loader import load_config
from src.control_engine import ControlEngine
from src.log_manager import LogManager
from src.sop_advisor import (
    apply_config_patch,
    summarize_failures,
    write_proposed_config,
    propose_actions,
)
from src.sop_executor import SopExecutor
from src.vision_engine import DetectionConfig, VisionEngine


def _resolve_confidence_threshold(config: dict) -> float:
    """Support both flat and nested config layouts during scaffold evolution."""

    if "ocr_threshold" in config:
        return float(config["ocr_threshold"])
    return float(config.get("vision", {}).get("confidence_threshold", 0.6))


def _resolve_ocr_psm(config: dict) -> int:
    """Read OCR page segmentation mode with a sensible scaffold default."""

    return int(config.get("vision", {}).get("ocr_psm", 7))


def _resolve_retries(config: dict) -> int:
    """Read retry count from config or fall back to the default."""

    return int(config.get("control", {}).get("retries", 3))


SpeedPreset = Literal["slow", "normal", "fast"]


def _build_services(speed: SpeedPreset = "normal") -> tuple[VisionEngine, ControlEngine, SopExecutor]:
    """Construct core services with optional speed presets for line engineers."""

    config = load_config()
    vision = VisionEngine(
        DetectionConfig(
            confidence_threshold=_resolve_confidence_threshold(config),
            ocr_psm=_resolve_ocr_psm(config),
        )
    )

    # Map speed preset to mouse movement / click pacing.
    if speed == "slow":
        move_duration = 0.25
        click_pause = 0.15
    elif speed == "fast":
        move_duration = 0.05
        click_pause = 0.01
    else:
        move_duration = 0.1
        click_pause = 0.05

    control = ControlEngine(
        vision_agent=vision,
        retries=_resolve_retries(config),
        move_duration=move_duration,
        click_pause=click_pause,
    )
    executor = SopExecutor(vision=vision, control=control)
    return vision, control, executor


def main() -> list[str]:
    """
    Programmatic entry used by tests and non-interactive callers.

    Runs the SOP sequence once with the default speed preset and returns
    the trace of step results.
    """

    _, _, executor = _build_services(speed="normal")
    return executor.run()


def _print_welcome() -> None:
    """Print first-run guidance for the line PC console."""

    banner = """
======================================================================
 Connector Vision SOP Agent v1.0  (YOLO26n + OCR + PyAutoGUI)
======================================================================

This EXE automates the 12-step OLED connector SOP:
- Login, recipe load, Mold Left/Right ROI, axis marking, pin checks, save/apply.

Usage (console):
  [1] Start SOP run (normal speed)
  [2] Start SOP run (fast)
  [3] Start SOP run (slow)
  [L] Analyze latest run with LLM (if wired)
  [Q] Quit

Note:
- You can always stop the program with CTRL+C.
- Speed presets only affect mouse move/drag timing, not detection thresholds.
"""
    print(banner.strip())


def run_console() -> None:
    """
    Hybrid console UI for the line PC.

    This function is invoked only when running the module as a script/EXE.
    """

    _print_welcome()
    last_log_manager: LogManager | None = None

    while True:
        try:
            cmd = input("\nSelect command [1/2/3/L/Q]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting Connector Vision SOP Agent.")
            break

        if cmd in ("q", "quit", "exit"):
            print("Goodbye.")
            break

        if cmd in ("1", "2", "3"):
            if cmd == "1":
                speed: SpeedPreset = "normal"
            elif cmd == "2":
                speed = "fast"
            else:
                speed = "slow"

            print(f"\n[RUN] Starting SOP at '{speed}' speed...")
            log_manager = LogManager()
            last_log_manager = log_manager

            try:
                _, _, executor = _build_services(speed=speed)
                trace = executor.run()
                for line in trace:
                    print("  ", line)
                    log_manager.log(step="sop", message=line)
                summary = log_manager.finalize(success=True)
                print(f"\n[OK] SOP run completed in {summary.duration_sec:.1f}s (run_id={summary.run_id}).")
            except KeyboardInterrupt:
                log_manager.log_error(step="sop", message="Run interrupted by user (CTRL+C).")
                summary = log_manager.finalize(success=False, error="Interrupted by user")
                print(f"\n[INTERRUPTED] SOP run stopped (run_id={summary.run_id}).")
            except Exception as exc:  # pragma: no cover - defensive guard.
                log_manager.log_error(step="sop", message="Unhandled exception", error=str(exc))
                summary = log_manager.finalize(success=False, error=str(exc))
                print(f"\n[ERROR] SOP run failed: {exc!r} (run_id={summary.run_id}).")

            continue

        if cmd in ("l",):
            if last_log_manager is None:
                print("No completed run found yet. Please start a SOP run first (option 1/2/3).")
                continue

            try:
                cfg = load_config()
                result = last_log_manager.analyze_with_llm(config=cfg)
                print("\n[LLM] Offline analysis result (config.json -> llm.* 기반):")
                note = result.get("note", "")
                if note:
                    print(f"      Note: {note}")

                patch = result.get("config_patch", {}) or {}
                recs = result.get("sop_recommendations", []) or []

                if patch:
                    print("      Suggested config_patch keys:", ", ".join(patch.keys()))
                else:
                    print("      No config_patch suggested.")

                if recs:
                    print("      SOP recommendations:")
                    for idx, rec in enumerate(recs, 1):
                        print(f"        {idx}. {rec}")
                else:
                    print("      No SOP recommendations.")

                # Normalize into high-level actions for human review.
                actions = propose_actions(result)
                if actions:
                    print("      Proposed actions (for engineer review):")
                    for idx, action in enumerate(actions, 1):
                        atype = action.get("type", "unknown")
                        desc = action.get("description", "")
                        if atype == "config_patch":
                            key = action.get("key")
                            value = action.get("value")
                            print(f"        {idx}. [CONFIG] {desc} (key={key!r}, value={value!r})")
                        elif atype == "sop_recommendation":
                            print(f"        {idx}. [SOP] {desc}")
                        else:
                            print(f"        {idx}. [{atype.upper()}] {desc}")

                # Phase 4 Checkpoint 2: write a proposed config, do not auto-apply.
                if patch:
                    new_cfg, warnings = apply_config_patch(cfg, patch)
                    proposed_path = write_proposed_config("assets/config.json", new_cfg)
                    print(f"      Proposed config written to: {proposed_path}")
                    if warnings:
                        print("      Warnings while applying patch:")
                        for w in warnings:
                            print(f"        - {w}")

                # Summarize recent failures (best effort; may be empty).
                events_tail = result.get("payload", {}).get("events_tail", [])
                if events_tail:
                    summary = summarize_failures(events_tail)
                    by_step = summary.get("error_counts_by_step", {})
                    if by_step:
                        print("      Error counts by step (from recent events):")
                        for step, count in by_step.items():
                            print(f"        {step}: {count}")

                print(
                    "      (config.json은 자동으로 변경되지 않습니다. "
                    "assets/config.proposed.json 파일을 편집기로 열어 검토한 뒤, "
                    "허용할 변경만 수동으로 config.json에 반영하세요.)"
                )
            except Exception as exc:  # pragma: no cover - defensive guard.
                print(f"[LLM ERROR] Failed to run offline LLM analysis: {exc!r}")

            continue

        if cmd in ("c",):
            if last_log_manager is None:
                print("No completed run found yet. Please start a SOP run first (option 1/2/3).")
                continue

            from src.llm_offline import OfflineLLM  # optional dependency; may raise if missing

            cfg = load_config()
            llm_cfg = cfg.get("llm") or {}
            if not llm_cfg.get("enabled"):
                print(
                    "LLM is disabled in config.json (llm.enabled is false). "
                    "config.json의 llm.enabled 값을 true로 변경한 뒤 다시 시도하세요."
                )
                continue

            try:
                offline_llm = OfflineLLM.from_config(llm_cfg)
            except Exception as exc:  # pragma: no cover - defensive
                print(
                    "[LLM ERROR] Failed to initialize offline LLM: "
                    f"{exc!r}\n"
                    "  - assets/config.json 의 llm.model_path / backend 설정을 확인하세요.\n"
                    "  - 필요한 경우 llama-cpp-python 또는 HTTP LLM 서버가 정상 동작하는지 점검하세요."
                )
                continue

            # Build initial context from the latest run payload.
            payload = last_log_manager.build_llm_payload(config=cfg)
            import json

            system = (
                "You are an expert Samsung OLED connector SOP and machine vision engineer. "
                "You will help the user understand and troubleshoot the latest SOP run. "
                "Use the provided JSON payload as context, but keep answers short and practical."
            )
            print("\n[CHAT] Enter chat mode. Type '/exit' to return to the main menu.")
            print("       The model has been given the latest run payload as context.")
            print("       Example questions:")
            print("         - \"이번 SOP 실행에서 실패한 단계와 이유를 요약해줘\"")
            print("         - \"핀 카운트 관련해서 어떤 튜닝을 시도해 보면 좋을까?\"")
            print("         - \"ROI 설정이 자주 실패하는 원인을 추정해줘\"")

            # Provide a short summary question as the first turn.
            history: list[dict[str, str]] = [
                {
                    "role": "user",
                    "content": (
                        "Here is the latest SOP run payload:\n"
                        f"{json.dumps(payload, ensure_ascii=False)[: offline_llm.cfg.max_input_tokens]}"
                        "\nSummarize what happened and any obvious issues."
                    ),
                }
            ]

            try:
                first_answer = offline_llm.chat(system=system, history=history)
                print("\n[LLM]", first_answer)
                # Keep the conversation history going.
                history.append({"role": "assistant", "content": first_answer})
            except Exception as exc:  # pragma: no cover
                print(
                    "[LLM ERROR] Failed initial summary: "
                    f"{exc!r}\n"
                    "  - LLM 모델/서버 상태와 config.json의 llm.* 설정을 다시 확인한 뒤 재시도하세요."
                )
                continue

            while True:
                try:
                    user_q = input("\n[You] ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nLeaving chat mode.")
                    break

                if user_q.lower() in ("", "/exit", "exit", "quit", "/quit"):
                    print("Leaving chat mode.")
                    break

                if not user_q:
                    print("  (질문을 입력하거나 '/exit'로 종료할 수 있습니다.)")
                    continue

                history.append({"role": "user", "content": user_q})
                try:
                    answer = offline_llm.chat(system=system, history=history)
                    print("[LLM]", answer)
                    history.append({"role": "assistant", "content": answer})
                except Exception as exc:  # pragma: no cover
                    print(
                        "[LLM ERROR] Chat failed: "
                        f"{exc!r}\n"
                        "  - 네트워크/로컬 LLM 서버 또는 모델 설정 문제일 수 있습니다. "
                        "config.json과 LLM 프로세스를 확인한 뒤 다시 시도하세요."
                    )
                    break

            continue

        print("Unrecognized command. Please choose one of [1/2/3/L/C/Q].")


if __name__ == "__main__":
    try:
        run_console()
    except KeyboardInterrupt:
        print("\nExiting Connector Vision SOP Agent.")

