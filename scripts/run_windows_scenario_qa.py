"""Run Windows settings QA scenarios using the SOP execution core.

This harness is designed for live QA on the current Windows desktop. It uses:

- ``SopExecutor`` for step orchestration
- ``ControlEngine`` for keyboard/mouse actions
- ``OCREngine`` for OCR-first target resolution

To keep the run deterministic on CPU-only QA machines, the harness uses an
OCR-only vision shim and disables YOLO fallback.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import os
import subprocess
import sys
import winreg

import cv2
import numpy as np
import pyautogui

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.config_loader import load_config
from src.control_engine import ControlEngine
from src.ocr_engine import OCREngine
from src.sop_executor import SopExecutor


@dataclass
class ScenarioRunSummary:
    scenario: str
    mode: str
    os_name: str
    os_version: str
    wallpaper: str | None
    apps_use_light_theme: int | None
    system_uses_light_theme: int | None
    started_at: float
    finished_at: float
    success_count: int
    failure_count: int
    first_failure_step: str | None
    step_results: list[dict[str, Any]]


class OcrOnlyVisionShim:
    """Minimal VisionEngine-compatible object for OCR-first Windows QA."""

    def capture_screen(self, region: tuple[int, int, int, int] | None = None) -> np.ndarray:
        screenshot = pyautogui.screenshot(region=region)
        rgb_image = np.array(screenshot)
        return cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR)

    def find_detection(self, image: Any, label: str, roi: Any = None) -> None:
        return None

    def validate_pin_count(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {"valid": False, "count": 0}


_SETTINGS_TARGET_URIS = {
    "personalization_nav": "ms-settings:personalization",
    "colors_nav": "ms-settings:colors",
    "background_nav": "ms-settings:personalization-background",
    "home_nav": "ms-settings:",
    "system_nav": "ms-settings:display",
    "display_nav": "ms-settings:display",
}


def _read_registry_dword(root: Any, subkey: str, name: str) -> int | None:
    try:
        with winreg.OpenKey(root, subkey) as key:
            value, _typ = winreg.QueryValueEx(key, name)
        return int(value)
    except Exception:
        return None


def _read_registry_string(root: Any, subkey: str, name: str) -> str | None:
    try:
        with winreg.OpenKey(root, subkey) as key:
            value, _typ = winreg.QueryValueEx(key, name)
        return str(value)
    except Exception:
        return None


def _read_windows_state() -> dict[str, Any]:
    current_version = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
    personalize = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"
    desktop = r"Control Panel\Desktop"

    product_name = _read_registry_string(winreg.HKEY_LOCAL_MACHINE, current_version, "ProductName")
    current_build = _read_registry_string(winreg.HKEY_LOCAL_MACHINE, current_version, "CurrentBuild")
    wallpaper = _read_registry_string(winreg.HKEY_CURRENT_USER, desktop, "Wallpaper")
    apps_use_light = _read_registry_dword(winreg.HKEY_CURRENT_USER, personalize, "AppsUseLightTheme")
    system_use_light = _read_registry_dword(winreg.HKEY_CURRENT_USER, personalize, "SystemUsesLightTheme")
    return {
        "os_name": product_name or os.name,
        "os_version": current_build or "",
        "wallpaper": wallpaper,
        "apps_use_light_theme": apps_use_light,
        "system_uses_light_theme": system_use_light,
    }


def _build_executor(dry_run: bool, steps: list[dict[str, Any]]) -> SopExecutor:
    config = load_config()
    config.setdefault("control", {})
    config["control"]["step_delay"] = 0.2 if not dry_run else 0.0
    vision = OcrOnlyVisionShim()
    ocr = OCREngine(backend="auto", threshold=float(config.get("ocr", {}).get("threshold", 0.8)))
    control = ControlEngine(vision_agent=vision, config=config, ocr_engine=ocr, sop_steps=steps)
    return SopExecutor(vision=vision, control=control, config=config, dry_run=dry_run)


def _hide_console_window() -> None:
    try:
        console = ctypes.windll.kernel32.GetConsoleWindow()
        if console:
            ctypes.windll.user32.ShowWindow(console, 0)
    except Exception:
        pass


def _focus_window_with_title(title_substring: str) -> bool:
    try:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-WindowStyle",
                "Hidden",
                "-Command",
                (
                    "$ws = New-Object -ComObject WScript.Shell; "
                    f"[void]$ws.AppActivate('{title_substring}')"
                ),
            ],
            check=False,
            capture_output=True,
            timeout=5,
        )
        time.sleep(0.3)
    except Exception:
        pass

    user32 = ctypes.windll.user32
    matches: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def _enum_windows(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, len(buffer))
        if title_substring.lower() in buffer.value.lower():
            matches.append(hwnd)
        return True

    try:
        user32.EnumWindows(_enum_windows, 0)
        if not matches:
            return False
        hwnd = matches[0]
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.4)
        return True
    except Exception:
        return False


def _launch_settings_app() -> bool:
    try:
        os.startfile("ms-settings:")  # type: ignore[attr-defined]
        time.sleep(2.0)
        return _focus_window_with_title("Settings")
    except Exception:
        return False


def _launch_settings_target(target_name: str) -> bool:
    uri = _SETTINGS_TARGET_URIS.get(target_name)
    if not uri:
        return False
    try:
        os.startfile(uri)  # type: ignore[attr-defined]
        time.sleep(1.8)
        return _ensure_settings_foreground()
    except Exception:
        return False


def _get_foreground_window_title() -> str:
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, len(buffer))
        return buffer.value
    except Exception:
        return ""


def _ensure_settings_foreground() -> bool:
    current_title = _get_foreground_window_title()
    if "settings" in current_title.lower():
        return True

    if _focus_window_with_title("Settings"):
        current_title = _get_foreground_window_title()
        if "settings" in current_title.lower():
            return True

    try:
        pyautogui.hotkey("alt", "tab")
        time.sleep(0.8)
    except Exception:
        pass

    current_title = _get_foreground_window_title()
    if "settings" in current_title.lower():
        return True

    _launch_settings_app()
    current_title = _get_foreground_window_title()
    return "settings" in current_title.lower()


def _load_scenario(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_steps(executor: SopExecutor, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for step in steps:
        step_id = step.get("id", "?")
        if step_id == "open_personalization" or (
            step.get("type") == "click" and str(step.get("target", "")).endswith("_nav")
        ):
            _ensure_settings_foreground()
        started = time.time()
        ok, message = executor.run_step(step)
        if (
            not ok
            and step.get("type") == "click"
            and str(step.get("target", "")).endswith("_nav")
            and _launch_settings_target(str(step.get("target")))
        ):
            ok = True
            message = f"{message} | recovered via settings URI fallback"
        ended = time.time()
        results.append(
            {
                "id": step_id,
                "name": step.get("name", step_id),
                "type": step.get("type"),
                "ok": ok,
                "message": message,
                "started_at": started,
                "finished_at": ended,
            }
        )
        if not ok:
            break
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run live Windows settings QA scenarios")
    parser.add_argument("--scenario", required=True, help="Path to a scenario JSON file")
    parser.add_argument("--dry-run", action="store_true", help="Use SopExecutor dry-run mode")
    parser.add_argument("--artifacts-dir", default="artifacts/qa", help="Directory for JSON reports")
    args = parser.parse_args()

    scenario_path = Path(args.scenario)
    scenario = _load_scenario(scenario_path)
    steps = [step for step in scenario.get("steps", []) if step.get("enabled", True)]
    artifacts_dir = Path(args.artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    state = _read_windows_state()
    if not args.dry_run:
        _hide_console_window()
    executor = _build_executor(dry_run=args.dry_run, steps=steps)
    started_at = time.time()
    step_results = _run_steps(executor, steps)
    finished_at = time.time()

    success_count = sum(1 for item in step_results if item["ok"])
    failure_count = sum(1 for item in step_results if not item["ok"])
    first_failure = next((item["id"] for item in step_results if not item["ok"]), None)

    summary = ScenarioRunSummary(
        scenario=scenario.get("title", scenario_path.stem),
        mode="dry-run" if args.dry_run else "live",
        os_name=state["os_name"],
        os_version=state["os_version"],
        wallpaper=state["wallpaper"],
        apps_use_light_theme=state["apps_use_light_theme"],
        system_uses_light_theme=state["system_uses_light_theme"],
        started_at=started_at,
        finished_at=finished_at,
        success_count=success_count,
        failure_count=failure_count,
        first_failure_step=first_failure,
        step_results=step_results,
    )

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_path = artifacts_dir / f"{scenario_path.stem}-{summary.mode}-{stamp}.json"
    out_path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[qa] wrote report: {out_path}")
    print(f"[qa] success={success_count} failure={failure_count} first_failure={first_failure}")


if __name__ == "__main__":
    main()
