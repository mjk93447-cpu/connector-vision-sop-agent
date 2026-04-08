"""Verify that updated SOP JSON reloads into the Run SOP panel."""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

from PyQt6.QtWidgets import QApplication

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.config_loader import load_config
from src.gui.main_window import MainWindow
from src.gui_app import _build_runtime


def main() -> None:
    artifacts = Path("artifacts/qa")
    artifacts.mkdir(parents=True, exist_ok=True)

    config = load_config()
    runtime = _build_runtime(config)
    app = QApplication([])

    with tempfile.TemporaryDirectory(prefix="sop_reload_smoke_") as tmpdir:
        tmp_path = Path(tmpdir) / "sop_steps.json"
        source = Path("assets/sop_steps.json")
        tmp_path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

        window = MainWindow(
            config=config,
            config_path=runtime["config_path"],
            sop_steps_path=tmp_path,
            sop_executor=runtime["executor"],
            llm=runtime["llm"],
            audit_log=runtime["audit_log"],
            vision=runtime["vision"],
            ocr=runtime["ocr"],
        )
        window.show()
        app.processEvents()
        initial_count = len(window._steps)

        scenario = json.loads(Path("qa/scenarios/windows_settings_smoke.json").read_text(encoding="utf-8"))
        tmp_path.write_text(json.dumps(scenario, ensure_ascii=False, indent=2), encoding="utf-8")
        window.reload_sop_steps()
        app.processEvents()
        reloaded_count = len(window._steps)

        report = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "initial_count": initial_count,
            "reloaded_count": reloaded_count,
            "expected_reloaded_count": len([s for s in scenario["steps"] if s.get("enabled", True)]),
            "reload_ok": reloaded_count == len([s for s in scenario["steps"] if s.get("enabled", True)]),
        }
        out = artifacts / ("sop-reload-smoke-" + time.strftime("%Y%m%d-%H%M%S") + ".json")
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(out)
        window.close()


if __name__ == "__main__":
    main()
