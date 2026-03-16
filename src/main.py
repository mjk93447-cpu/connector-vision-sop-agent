"""
Main entry point for Connector Vision SOP Agent v3.0.

Default mode: PyQt6 GUI application.
Use --console flag to run in legacy CLI mode.

GUI Mode (default)
------------------
  python src/main.py              → Opens PyQt6 GUI
  python src/main.py --gui        → Same

Console Mode (legacy)
---------------------
  python src/main.py --console    → CLI mode

Console commands
----------------
[1] Start SOP run (normal speed)
[2] Start SOP run (fast)
[3] Start SOP run (slow)
[L] Analyze latest run with offline LLM  → writes config.proposed.json
[C] Chat with LLM about the latest run   → can apply config changes with your approval
[A] Show config audit history
[Q] Quit

LLM-assisted config changes (command [C])
-----------------------------------------
When the LLM suggests config parameter changes during a [C] chat session,
the agent asks:

  Apply these changes? [Y/N]:
  Enter your name for the audit log:
  Enter reason (press Enter to skip):

If confirmed, config.json is updated directly AND an entry is appended to
  logs/config_audit_<line_id>.jsonl

This means every change is traceable: who, when, what, why.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from src.config_loader import load_config
from src.config_audit import ConfigAuditLog
from src.control_engine import ControlEngine
from src.log_manager import LogManager
from src.sop_advisor import (
    apply_config_patch,
    apply_config_direct,
    summarize_failures,
    write_proposed_config,
    propose_actions,
    SAFE_NUMERIC_RANGES,
)
from src.sop_executor import SopExecutor
from src.vision_engine import DetectionConfig, VisionEngine

_CONFIG_PATH = "assets/config.json"

SpeedPreset = Literal["slow", "normal", "fast"]


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def _resolve_confidence_threshold(config: dict) -> float:
    if "ocr_threshold" in config:
        return float(config["ocr_threshold"])
    return float(config.get("vision", {}).get("confidence_threshold", 0.6))


def _get_line_id(config: dict) -> str:
    return str(config.get("line_id", "LINE-UNKNOWN"))


def _get_audit_log(config: dict) -> ConfigAuditLog:
    audit_cfg = config.get("audit", {})
    log_path = audit_cfg.get("log_path", "logs/config_audit.jsonl")
    log_dir = Path(log_path).parent
    line_id = _get_line_id(config)
    return ConfigAuditLog(line_id=line_id, log_dir=log_dir)


# ---------------------------------------------------------------------------
# Service builder
# ---------------------------------------------------------------------------


def _build_services(
    config: Optional[Dict[str, Any]] = None,
    speed: SpeedPreset = "normal",
) -> tuple[VisionEngine, ControlEngine, SopExecutor]:
    """Construct core services.  All timing comes from config when provided."""

    if config is None:
        config = load_config()

    vision = VisionEngine(
        DetectionConfig(
            confidence_threshold=_resolve_confidence_threshold(config),
        )
    )

    # Speed preset overrides only if config has no control section.
    has_control_cfg = bool(config.get("control"))

    if has_control_cfg:
        control = ControlEngine(vision_agent=vision, config=config)
    else:
        # Legacy speed-preset mapping (backward compat).
        if speed == "slow":
            move_duration, click_pause = 0.25, 0.15
        elif speed == "fast":
            move_duration, click_pause = 0.05, 0.01
        else:
            move_duration, click_pause = 0.10, 0.05
        control = ControlEngine(
            vision_agent=vision,
            retries=int(config.get("control", {}).get("retries", 3)),
            move_duration=move_duration,
            click_pause=click_pause,
        )

    executor = SopExecutor(vision=vision, control=control, config=config)
    return vision, control, executor


def main() -> list[str]:
    """Programmatic entry used by tests and non-interactive callers."""
    _, _, executor = _build_services(speed="normal")
    return executor.run()


# ---------------------------------------------------------------------------
# Console UI helpers
# ---------------------------------------------------------------------------


def _print_welcome() -> None:
    banner = """
======================================================================
 Connector Vision SOP Agent v3.0  (YOLO26x + phi4-mini [Offline])
======================================================================

12-step OLED connector SOP automation with offline LLM assistance.

Commands:
  [1] Start SOP run (normal speed — uses config.control timings)
  [2] Start SOP run (fast preset)
  [3] Start SOP run (slow preset)
  [L] LLM analysis of latest run  (writes config.proposed.json)
  [C] Chat with LLM about latest run  (can apply config changes)
  [A] Show config change audit history
  [Q] Quit

Tip: Edit assets/config.json to tune pin counts, timing, and thresholds.
     All changes via [C] are logged with your name and timestamp.
"""
    print(banner.strip())


def _ask_yes_no(prompt: str) -> bool:
    """Return True if the user answers Y/y."""
    try:
        ans = input(prompt).strip().lower()
        return ans in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def _ask_input(prompt: str, default: str = "") -> str:
    """Return stripped input, or *default* on EOF/interrupt."""
    try:
        val = input(prompt).strip()
        return val if val else default
    except (EOFError, KeyboardInterrupt):
        return default


# ---------------------------------------------------------------------------
# LLM config-patch extraction helper
# ---------------------------------------------------------------------------

# Keys the LLM is allowed to suggest (must also be in SAFE_NUMERIC_RANGES or
# be a known string key).
_ALLOWED_PATCH_KEYS = set(SAFE_NUMERIC_RANGES.keys()) | {
    "llm.enabled",
    "vision.confidence_threshold",
    "control.step_delay",
    "control.move_duration",
    "control.click_pause",
    "control.drag_duration",
    "control.retry_delay",
    "control.retries",
    "pin_count_min",
    "pin_count_max",
}

_PATCH_JSON_RE = re.compile(
    r"config[_\s]*patch\s*[:\-]?\s*(\{[^}]+\})",
    re.IGNORECASE | re.DOTALL,
)


def _extract_patch_from_llm_text(text: str) -> Optional[Dict[str, Any]]:
    """Try to parse a JSON config_patch block from an LLM response.

    Returns None if nothing parseable is found.
    """
    match = _PATCH_JSON_RE.search(text)
    if not match:
        return None
    try:
        candidate = json.loads(match.group(1))
        if isinstance(candidate, dict):
            return candidate
    except json.JSONDecodeError:
        pass
    return None


def _prompt_config_apply(
    cfg: Dict[str, Any],
    patch: Dict[str, Any],
    audit_log: ConfigAuditLog,
    llm_text: str,
    source: str = "llm_chat",
) -> Optional[Dict[str, Any]]:
    """Ask the engineer for approval, then apply or skip.

    Returns the updated config dict on approval, None if skipped.
    """
    print("\n[LLM SUGGESTION] Config changes proposed:")
    for key, val in patch.items():
        old = cfg
        for part in key.split("."):
            old = old.get(part, {}) if isinstance(old, dict) else "?"
        print(f"  {key}: {old!r}  →  {val!r}")

    audit_cfg = cfg.get("audit", {})
    require_username = audit_cfg.get("require_username", True)

    if not _ask_yes_no("\nApply these changes to config.json? [Y/N]: "):
        print("  Skipped. No changes applied.")
        return None

    username = ""
    if require_username:
        while not username:
            username = _ask_input("  Enter your name (required for audit log): ")
            if not username:
                print("  Name is required. Please enter your name.")
    else:
        username = _ask_input("  Enter your name (optional): ", default="anonymous")

    reason = _ask_input("  Enter reason for change (press Enter to skip): ")

    allow_write = cfg.get("llm", {}).get("allow_config_write", False)
    if not allow_write:
        print(
            "\n  [BLOCKED] config.json -> llm.allow_config_write is false.\n"
            "  To enable direct LLM config writes, set it to true in config.json first.\n"
            "  Writing to config.proposed.json instead."
        )
        new_cfg, warnings = apply_config_patch(cfg, patch)
        proposed_path = write_proposed_config(_CONFIG_PATH, new_cfg)
        print(f"  Proposed config written to: {proposed_path}")
        for w in warnings:
            print(f"  Warning: {w}")
        return None

    new_cfg, warnings, audit_entry = apply_config_direct(
        config=cfg,
        patch=patch,
        config_path=_CONFIG_PATH,
        audit_log=audit_log,
        username=username,
        reason=reason,
        llm_recommendation=llm_text[:500],
        source=source,
    )

    if audit_entry:
        print("\n  [OK] config.json updated. Audit entry saved:")
        print(f"       {audit_log._log_path}")
        print(f"       Changed by: {username}  at: {audit_entry['ts']}")
    for w in warnings:
        print(f"  Warning: {w}")

    return new_cfg


# ---------------------------------------------------------------------------
# Console main loop
# ---------------------------------------------------------------------------


def run_console() -> None:
    """Hybrid console UI for the line PC."""

    _print_welcome()
    last_log_manager: LogManager | None = None
    cfg = load_config()
    audit_log = _get_audit_log(cfg)

    while True:
        try:
            cmd = input("\nSelect command [1/2/3/L/C/A/Q]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting Connector Vision SOP Agent.")
            break

        if cmd in ("q", "quit", "exit"):
            print("Goodbye.")
            break

        # ----------------------------------------------------------------
        # [1/2/3] Run SOP
        # ----------------------------------------------------------------
        if cmd in ("1", "2", "3"):
            speed_map = {"1": "normal", "2": "fast", "3": "slow"}
            speed: SpeedPreset = speed_map[cmd]

            cfg = load_config()  # Re-read so latest config edits are picked up.
            audit_log = _get_audit_log(cfg)

            print(f"\n[RUN] Starting SOP (speed={speed!r}) ...")
            print(
                f"      pin_count_min={cfg.get('pin_count_min')}  "
                f"pin_count_max={cfg.get('pin_count_max')}  "
                f"step_delay={cfg.get('control', {}).get('step_delay')}s"
            )
            log_manager = LogManager()
            last_log_manager = log_manager

            try:
                _, _, executor = _build_services(config=cfg, speed=speed)
                trace = executor.run()
                for line in trace:
                    print("  ", line)
                    log_manager.log(step="sop", message=line)
                summary = log_manager.finalize(success=True)
                print(
                    f"\n[OK] SOP complete in {summary.duration_sec:.1f}s "
                    f"(run_id={summary.run_id})."
                )
            except KeyboardInterrupt:
                log_manager.log_error(step="sop", message="Run interrupted by user.")
                summary = log_manager.finalize(success=False, error="Interrupted")
                print(f"\n[INTERRUPTED] (run_id={summary.run_id}).")
            except Exception as exc:  # pragma: no cover
                log_manager.log_error(
                    step="sop", message="Unhandled exception", error=str(exc)
                )
                summary = log_manager.finalize(success=False, error=str(exc))
                print(f"\n[ERROR] {exc!r} (run_id={summary.run_id}).")
            continue

        # ----------------------------------------------------------------
        # [L] LLM analysis → config.proposed.json
        # ----------------------------------------------------------------
        if cmd == "l":
            if last_log_manager is None:
                print("No run yet. Run SOP first ([1/2/3]).")
                continue

            cfg = load_config()
            audit_log = _get_audit_log(cfg)

            try:
                result = last_log_manager.analyze_with_llm(config=cfg)
                note = result.get("note", "")
                if note:
                    print(f"\n[LLM] Note: {note}")

                patch = result.get("config_patch") or {}
                actions = propose_actions(result)

                if actions:
                    print("\n[LLM] Proposed actions:")
                    for idx, a in enumerate(actions, 1):
                        atype = a.get("type", "")
                        if atype == "config_patch":
                            print(f"  {idx}. [CONFIG] {a['description']}")
                        else:
                            print(f"  {idx}. [SOP]    {a['description']}")

                events_tail = result.get("payload", {}).get("events_tail", [])
                if events_tail:
                    fs = summarize_failures(events_tail)
                    by_step = fs.get("error_counts_by_step", {})
                    if by_step:
                        print("\n  Error counts by step:")
                        for step, cnt in by_step.items():
                            print(f"    {step}: {cnt}")

                if patch:
                    new_cfg, warnings = apply_config_patch(cfg, patch)
                    proposed_path = write_proposed_config(_CONFIG_PATH, new_cfg)
                    print(f"\n  Proposed config → {proposed_path}")
                    for w in warnings:
                        print(f"  Warning: {w}")
                    print(
                        "\n  To apply: copy values from config.proposed.json into "
                        "config.json,\n  or use [C] chat mode with llm.allow_config_write=true."
                    )
                else:
                    print("\n  No config patch suggested.")

            except Exception as exc:  # pragma: no cover
                print(f"[LLM ERROR] {exc!r}")
            continue

        # ----------------------------------------------------------------
        # [C] LLM chat — can apply config changes with audit
        # ----------------------------------------------------------------
        if cmd == "c":
            if last_log_manager is None:
                print("No run yet. Run SOP first ([1/2/3]).")
                continue

            from src.llm_offline import OfflineLLM

            cfg = load_config()
            audit_log = _get_audit_log(cfg)
            llm_cfg = cfg.get("llm") or {}

            if not llm_cfg.get("enabled"):
                print(
                    "LLM is disabled (llm.enabled=false in config.json).\n"
                    "Set it to true and ensure Ollama is running, then retry."
                )
                continue

            try:
                offline_llm = OfflineLLM.from_config(llm_cfg)
            except Exception as exc:  # pragma: no cover
                print(
                    f"[LLM ERROR] Cannot init LLM: {exc!r}\n"
                    "  Check config.json llm.model_path / http_url."
                )
                continue

            payload = last_log_manager.build_llm_payload(config=cfg)
            allow_write = llm_cfg.get("allow_config_write", False)
            write_note = (
                "LLM config write: ENABLED (changes will be applied with your approval)"
                if allow_write
                else "LLM config write: DISABLED (set llm.allow_config_write=true to enable)"
            )

            system = (
                "You are an expert Samsung OLED connector SOP and machine vision engineer "
                "for an offline line PC. Help the engineer diagnose issues and tune parameters. "
                "When suggesting config changes, output a JSON block labelled 'config_patch' "
                'with dotted keys (e.g. {"control.step_delay": 1.5, "pin_count_min": 40}). '
                "Keep answers short, practical, and in English."
            )

            print(f"\n[CHAT] {write_note}")
            print(
                "       Type '/exit' to return.  '/apply' to manually trigger apply prompt."
            )
            print("       Example questions:")
            print("         - 'Summarize this SOP run and any failures'")
            print("         - 'Why did pin count fail? Suggest a fix.'")
            print("         - 'Increase timing to avoid collision with slow programs'")

            history: List[Dict[str, str]] = [
                {
                    "role": "user",
                    "content": (
                        "Latest SOP run payload:\n"
                        f"{json.dumps(payload, ensure_ascii=False)[:llm_cfg.get('max_input_tokens', 6144)]}"
                        "\n\nSummarize what happened and flag any issues."
                    ),
                }
            ]

            last_llm_text = ""
            last_patch: Optional[Dict[str, Any]] = None

            try:
                first_answer = offline_llm.chat(system=system, history=history)
                print("\n[LLM]", first_answer)
                history.append({"role": "assistant", "content": first_answer})
                last_llm_text = first_answer
                last_patch = _extract_patch_from_llm_text(first_answer)
                if last_patch:
                    print(
                        "[LLM] Config patch detected in response — type '/apply' to apply."
                    )
            except Exception as exc:  # pragma: no cover
                print(f"[LLM ERROR] {exc!r}")
                continue

            while True:
                try:
                    user_q = input("\n[You] ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nLeaving chat mode.")
                    break

                if user_q.lower() in ("", "/exit", "exit", "quit"):
                    print("Leaving chat mode.")
                    break

                # Manual apply trigger.
                if user_q.lower() == "/apply":
                    if not last_patch:
                        print("  No config patch found in recent LLM responses.")
                        print(
                            "  Ask the LLM to suggest specific parameter changes first."
                        )
                    else:
                        cfg = load_config()
                        updated = _prompt_config_apply(
                            cfg, last_patch, audit_log, last_llm_text, source="llm_chat"
                        )
                        if updated is not None:
                            cfg = updated
                    continue

                history.append({"role": "user", "content": user_q})
                try:
                    answer = offline_llm.chat(system=system, history=history)
                    print("[LLM]", answer)
                    history.append({"role": "assistant", "content": answer})
                    last_llm_text = answer

                    patch_candidate = _extract_patch_from_llm_text(answer)
                    if patch_candidate:
                        last_patch = patch_candidate
                        print(
                            "[LLM] Config patch detected — type '/apply' to apply "
                            "with your approval and audit log entry."
                        )
                except Exception as exc:  # pragma: no cover
                    print(f"[LLM ERROR] {exc!r}")
                    break

            continue

        # ----------------------------------------------------------------
        # [A] Audit history
        # ----------------------------------------------------------------
        if cmd == "a":
            cfg = load_config()
            audit_log = _get_audit_log(cfg)
            print(f"\n[AUDIT] Config change history — {audit_log._log_path}")
            print(audit_log.format_history_table(limit=20))
            continue

        print("Unknown command. Choose one of [1/2/3/L/C/A/Q].")


# ---------------------------------------------------------------------------
# GUI entry point
# ---------------------------------------------------------------------------


def run_gui() -> None:
    """Launch the PyQt6 GUI application."""
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        print(
            "[ERROR] PyQt6 is not installed.\n"
            "  Install with: pip install PyQt6>=6.7.0\n"
            "  Or run in console mode: python src/main.py --console"
        )
        sys.exit(1)

    cfg = load_config()
    audit_log = _get_audit_log(cfg)

    # Resolve asset paths — when frozen (PyInstaller EXE), look next to the EXE first.
    if getattr(sys, "frozen", False):
        _exe_dir = Path(sys.executable).parent
        config_path = _exe_dir / _CONFIG_PATH
        sop_steps_path = _exe_dir / "assets" / "sop_steps.json"
        if not sop_steps_path.exists():
            # Fallback: bundled copy inside _MEIPASS
            sop_steps_path = (
                Path(getattr(sys, "_MEIPASS", ".")) / "assets" / "sop_steps.json"
            )
    else:
        config_path = Path(_CONFIG_PATH)
        sop_steps_path = Path("assets/sop_steps.json")

    # Try to build LLM if enabled
    llm = None
    if cfg.get("llm", {}).get("enabled"):
        try:
            from src.llm_offline import OfflineLLM

            llm = OfflineLLM.from_config(cfg.get("llm", {}))
        except Exception as exc:
            print(f"[WARN] LLM init failed: {exc!r} — continuing without LLM.")

    # Build vision/control/executor (graceful fail — GUI still opens)
    executor = None
    try:
        _, _, executor = _build_services(config=cfg, speed="normal")
        # Attach sop_steps_path for dynamic step loading
        executor._sop_steps_path = sop_steps_path
    except Exception as exc:
        print(f"[WARN] Service init failed: {exc!r} — SOP tab will show warning.")

    app = QApplication(sys.argv)
    app.setApplicationName("Connector Vision SOP Agent")
    app.setApplicationVersion("3.0.0")

    from src.gui.main_window import MainWindow

    window = MainWindow(
        config=cfg,
        config_path=config_path,
        sop_steps_path=sop_steps_path,
        sop_executor=executor,
        llm=llm,
        audit_log=audit_log,
    )
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--console" in args or "-c" in args:
        try:
            run_console()
        except KeyboardInterrupt:
            print("\nExiting Connector Vision SOP Agent.")
    else:
        run_gui()
