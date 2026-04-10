"""GUI-first application entrypoint for the packaged SOP agent.

The app bundle must launch the PyQt6 GUI by default. The older console runner
in ``src/main.py`` is kept only for legacy/manual diagnostics.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.config_audit import ConfigAuditLog
from src.config_loader import load_config, resolve_app_path
from src.control_engine import ControlEngine
from src.gui.main_window import MainWindow
from src.model_artifacts import resolve_runtime_model
from src.ocr_engine import OCREngine
from src.sop_executor import SopExecutor
from src.vision_engine import DetectionConfig, VisionEngine


def _resolve_confidence_threshold(config: dict[str, Any]) -> float:
    if "ocr_threshold" in config:
        return float(config["ocr_threshold"])
    return float(config.get("vision", {}).get("confidence_threshold", 0.6))


def _resolve_ocr_threshold(config: dict[str, Any]) -> float:
    vision_cfg = config.get("vision", {})
    if "ocr_threshold" in vision_cfg:
        return float(vision_cfg["ocr_threshold"])
    return float(config.get("ocr_threshold", 0.8))


def _resolve_ocr_psm(config: dict[str, Any]) -> int:
    return int(config.get("vision", {}).get("ocr_psm", 7))


def _resolve_runtime_model_path(config: dict[str, Any]) -> Path:
    configured = config.get("vision", {}).get("model_path")
    return resolve_runtime_model(configured)


def _resolve_line_id(config: dict[str, Any]) -> str:
    return str(config.get("line_id", "LINE-UNKNOWN"))


def _build_runtime(config: dict[str, Any]) -> dict[str, Any]:
    config_path = resolve_app_path("assets/config.json")
    sop_steps_path = resolve_app_path("assets/sop_steps.json")

    vision = VisionEngine(
        DetectionConfig(
            model_path=str(_resolve_runtime_model_path(config)),
            confidence_threshold=_resolve_confidence_threshold(config),
            ocr_psm=_resolve_ocr_psm(config),
        )
    )
    ocr = OCREngine(backend="auto", threshold=_resolve_ocr_threshold(config))
    control = ControlEngine(vision_agent=vision, config=config, ocr_engine=ocr)
    executor = SopExecutor(
        vision=vision,
        control=control,
        config=config,
        sop_steps_path=Path(sop_steps_path),
    )

    llm = None
    llm_cfg = config.get("llm") or {}
    if llm_cfg.get("enabled"):
        try:
            from src.llm_offline import OfflineLLM  # noqa: PLC0415

            llm = OfflineLLM.from_config(llm_cfg)
        except Exception:
            llm = None

    audit_log = ConfigAuditLog(line_id=_resolve_line_id(config), log_dir=resolve_app_path("logs"))

    return {
        "config_path": Path(config_path),
        "sop_steps_path": Path(sop_steps_path),
        "vision": vision,
        "ocr": ocr,
        "control": control,
        "executor": executor,
        "llm": llm,
        "audit_log": audit_log,
    }


def run_gui(argv: list[str] | None = None) -> int:
    try:
        from PyQt6.QtWidgets import QApplication  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - depends on GUI runtime
        raise SystemExit(
            "PyQt6 is required for GUI mode. Rebuild or reinstall the GUI bundle."
        ) from exc

    app = QApplication(argv or sys.argv)
    config = load_config()
    runtime = _build_runtime(config)
    window = MainWindow(
        config=config,
        config_path=runtime["config_path"],
        sop_steps_path=runtime["sop_steps_path"],
        sop_executor=runtime["executor"],
        llm=runtime["llm"],
        audit_log=runtime["audit_log"],
        vision=runtime["vision"],
        ocr=runtime["ocr"],
    )
    window.show()
    return app.exec()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Connector Vision SOP Agent GUI launcher")
    parser.add_argument(
        "--console",
        action="store_true",
        help="Run the archived console entrypoint instead of the GUI.",
    )
    args = parser.parse_args(argv)

    if args.console:
        from src.main import run_console  # noqa: PLC0415

        run_console()
        return 0

    return run_gui(argv)


if __name__ == "__main__":
    raise SystemExit(main())
