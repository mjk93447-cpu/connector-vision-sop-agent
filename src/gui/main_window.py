"""
MainWindow — PyQt6 QMainWindow for Connector Vision SOP Agent.

Seven-tab layout:
  Tab 1 (▶ Run SOP)   — SopPanel
  Tab 2 (👁 Vision)   — VisionPanel
  Tab 3 (💬 LLM Chat) — LlmPanel
  Tab 4 (📋 SOP Edit) — SopEditorPanel
  Tab 5 (⚙ Config)   — ConfigPanel
  Tab 6 (📊 Audit)    — AuditPanel
  Tab 7 (🧠 Training) — TrainingPanel

The window wires QThread workers (SopWorker, LLMWorker, TrainingWorker)
so all heavy computation runs off the main thread.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from PyQt6.QtCore import QTimer
    from PyQt6.QtGui import QImage, QPixmap
    from PyQt6.QtWidgets import (
        QApplication,
        QLabel,
        QMainWindow,
        QMessageBox,
        QStatusBar,
        QTabWidget,
    )

    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False
    QMainWindow = object  # type: ignore[assignment,misc]

from src.gui.panels.audit_panel import AuditPanel
from src.gui.panels.config_panel import ConfigPanel
from src.gui.panels.llm_panel import LlmPanel
from src.gui.panels.sop_editor_panel import SopEditorPanel
from src.gui.panels.sop_panel import SopPanel
from src.gui.panels.training_panel import TrainingPanel
from src.gui.panels.vision_panel import VisionPanel
from src.gui.workers import AnalysisWorker, LLMStreamWorker, LLMWorker, SopWorker

_APP_VERSION = "4.5.0"


class MainWindow(QMainWindow):  # type: ignore[misc]
    """Top-level application window."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        config_path: Optional[Path] = None,
        sop_steps_path: Optional[Path] = None,
        sop_executor: Optional[Any] = None,
        llm: Optional[Any] = None,
        audit_log: Optional[Any] = None,
        log_manager: Optional[Any] = None,
        vision: Optional[Any] = None,
        ocr: Optional[Any] = None,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._config = config or {}
        self._config_path = config_path or Path("assets/config.json")
        self._sop_steps_path = sop_steps_path or Path("assets/sop_steps.json")
        self._sop_executor = sop_executor
        self._llm = llm
        self._audit_log = audit_log
        self._log_manager: Optional[Any] = log_manager
        # vision engine — used to run YOLO on screenshots
        self._vision: Optional[Any] = vision or (
            getattr(sop_executor, "vision", None) if sop_executor else None
        )
        self._ocr: Optional[Any] = ocr
        self._steps: List[Dict[str, Any]] = []
        self._worker: Optional[Any] = None
        self._llm_worker: Optional[Any] = None

        # ExceptionHandler for M2 popup monitoring during SOP execution
        self._exception_handler: Optional[Any] = None
        try:
            from src.exception_handler import ExceptionHandler  # noqa: PLC0415

            self._exception_handler = ExceptionHandler(config=self._config)
        except Exception:  # noqa: BLE001
            pass

        # Timer for periodic popup detection during SOP runs (M2)
        self._exc_monitor_timer: Optional[Any] = None

        self._load_steps()
        self._setup_ui()
        self._connect_signals()
        self._update_status()

    # ------------------------------------------------------------------
    # Public API (called by panels / tests)
    # ------------------------------------------------------------------

    def reload_sop_steps(self) -> None:
        """Reload sop_steps.json and update Run SOP panel."""
        self._load_steps()
        self._sop_panel.set_steps(self._steps)
        self._update_status()

    def on_llm_send(
        self,
        history: List[Dict[str, str]],
        system: Optional[str] = None,
        brief: bool = False,
        streaming: bool = True,
        image_b64: Optional[str] = None,
    ) -> None:
        """Start LLMStreamWorker (or LLMWorker) for a chat turn.

        Steps performed before starting the worker:
        1. Ollama health check — raises clear error if server not running.
        2. CPU-only detection — shows info message so user knows to expect delay.
        """
        if self._llm is None:
            self._llm_panel.on_llm_error(
                "LLM is not configured. Please check the llm settings in config.json."
            )
            return

        # Health check + CPU warning (Step 2-E)
        # Non-fatal: if Ollama is slow to respond (e.g. network drive / low RAM)
        # we still attempt the actual streaming request rather than aborting early.
        # The worker will surface a proper error if Ollama is truly unreachable.
        health_check = getattr(self._llm, "check_health", None)
        if callable(health_check):
            try:
                cpu_msg = health_check()
                if cpu_msg:
                    self._llm_panel.on_analysis_ready(
                        {
                            "raw_text": cpu_msg,
                            "config_patch": {},
                            "sop_recommendations": [],
                        }
                    )
            except RuntimeError as exc:
                # Log the warning in the chat but do NOT abort — let the worker try.
                self._llm_panel.on_analysis_ready(
                    {
                        "raw_text": f"⚠️ Health check warning (will attempt anyway): {exc}",
                        "config_patch": {},
                        "sop_recommendations": [],
                    }
                )

        if system is None:
            system = (
                "You are an expert in Samsung OLED connector line SOP procedures. "
                "Help the engineer diagnose and resolve SOP execution issues clearly and accurately. "
                "Respond in English, using technical terms where appropriate."
            )

        # Inject recent run log context into system prompt
        log_ctx = self._build_log_context_for_llm()
        enriched_system = system + ("\n\n" + log_ctx if log_ctx else "")

        if streaming:
            worker = LLMStreamWorker(
                self._llm,
                system_prompt=enriched_system,
                history=history,
                brief=brief,
                image_b64=image_b64,
            )
            worker.token_ready.connect(self._llm_panel.on_token_ready)
            worker.think_token_ready.connect(self._llm_panel.on_think_token_ready)
            worker.elapsed_tick.connect(self._llm_panel.on_elapsed_tick)
            worker.response_done.connect(self._llm_panel.on_streaming_done)
            worker.error_occurred.connect(self._llm_panel.on_llm_error)
            self._llm_panel._worker = worker  # expose for Stop button
            self._llm_worker = worker
            worker.start()
        else:
            self._llm_worker = LLMWorker(
                self._llm,
                system_prompt=enriched_system,
                history=history,
                image_b64=image_b64,
            )
            self._llm_worker.response_ready.connect(self._llm_panel.on_llm_response)
            self._llm_worker.error_occurred.connect(self._llm_panel.on_llm_error)
            self._llm_worker.start()

    def on_llm_analyze(self) -> None:
        """Start AnalysisWorker using the latest log payload."""
        if self._llm is None:
            self._llm_panel.on_llm_error("LLM is not configured.")
            return
        if self._log_manager is None:
            self._llm_panel.on_llm_error(
                "No SOP run history yet. Please run the SOP from the ▶ Run SOP tab first."
            )
            return
        # Use real LogManager payload (Phase 2)
        payload: Dict[str, Any] = self._log_manager.build_llm_payload(
            config=self._config
        )
        self._llm_panel.set_sending(True)
        worker = AnalysisWorker(self._llm, payload)
        worker.analysis_ready.connect(self._llm_panel.on_analysis_ready)
        worker.error_occurred.connect(self._llm_panel.on_llm_error)
        worker.finished.connect(lambda: self._llm_panel.set_sending(False))
        worker.start()
        self._llm_worker = worker

    # ------------------------------------------------------------------
    # Private — setup
    # ------------------------------------------------------------------

    def _load_steps(self) -> None:
        if not self._sop_steps_path.exists():
            self._steps = []
            return
        try:
            data = json.loads(self._sop_steps_path.read_text(encoding="utf-8"))
            self._steps = [s for s in data.get("steps", []) if s.get("enabled", True)]
        except Exception:  # noqa: BLE001
            self._steps = []

    def _setup_ui(self) -> None:
        if not _QT_AVAILABLE:
            return

        line_id = self._config.get("line_id", "LINE-??")
        model = self._config.get("llm", {}).get("model", "offline")
        self.setWindowTitle(
            f"Connector Vision SOP Agent v{_APP_VERSION} — {line_id} | {model}"
        )
        self.resize(1100, 720)
        self.setMinimumSize(800, 560)

        # Central widget with tab bar
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        # Instantiate panels
        self._sop_panel = SopPanel(
            steps=self._steps,
            ocr_engine=self._ocr,
            vision_engine=self._vision,
        )
        self._vision_panel = VisionPanel()
        self._llm_panel = LlmPanel()
        self._sop_editor_panel = SopEditorPanel(
            sop_path=self._sop_steps_path,
            llm=self._llm,
            ocr=self._ocr,
        )
        self._config_panel = ConfigPanel(
            config=self._config, config_path=self._config_path
        )
        self._audit_panel = AuditPanel(audit_log=self._audit_log)
        self._training_panel = TrainingPanel()
        # Wire VisionEngine so TrainingPanel can hot-reload weights after training.
        # Without this, "Reload Model" always shows "VisionEngine not available."
        self._training_panel.set_vision_engine(self._vision)

        self._tabs.addTab(self._sop_panel, "▶ Run SOP")
        self._tabs.addTab(self._vision_panel, "👁 Vision")
        self._tabs.addTab(self._llm_panel, "💬 LLM Chat")
        self._tabs.addTab(self._sop_editor_panel, "📋 SOP Editor")
        self._tabs.addTab(self._config_panel, "⚙ Config")
        self._tabs.addTab(self._audit_panel, "📊 Audit")
        self._tabs.addTab(self._training_panel, "🧠 Training")

        self.setCentralWidget(self._tabs)

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._lbl_status = QLabel("Status: READY")
        self._lbl_steps = QLabel("0 steps")
        self._lbl_pins = QLabel("Pins: –/–")
        self._lbl_llm = QLabel("LLM: –")
        self._lbl_ocr = QLabel("OCR: –")

        for lbl in [
            self._lbl_status,
            self._lbl_steps,
            self._lbl_pins,
            self._lbl_llm,
            self._lbl_ocr,
        ]:
            self._status_bar.addPermanentWidget(lbl)

        # Refresh audit every time the Audit tab is shown
        self._tabs.currentChanged.connect(self._on_tab_changed)

        # Exception monitor timer — started when SOP runs, stopped on finish (M2)
        if _QT_AVAILABLE:
            self._exc_monitor_timer = QTimer(self)
            self._exc_monitor_timer.setInterval(5000)  # check every 5 s
            self._exc_monitor_timer.timeout.connect(self._on_exception_popup_tick)

        # Deferred preflight: resolution + OCR health (H4 + H2 + M3)
        if _QT_AVAILABLE:
            QTimer.singleShot(500, self._run_preflight)

    def _connect_signals(self) -> None:
        if not _QT_AVAILABLE:
            return

        # Run SOP buttons
        self._sop_panel._btn_run.clicked.connect(self._on_run_sop)
        self._sop_panel._btn_stop.clicked.connect(self._on_stop_sop)

        # LLM apply patch
        self._llm_panel.apply_patch_requested.connect(self._on_apply_patch)

        # H1: Wire training_finished → update status bar + reload notification
        self._training_panel.training_finished.connect(self._on_training_finished)

        # v3.5.0: Wire ControlEngine._trace_cb → SopPanel.add_trace_entry
        if self._sop_executor is not None:
            control_engine = getattr(self._sop_executor, "control", None)
            if control_engine is not None and hasattr(control_engine, "_trace_cb"):
                sop_panel_ref = self._sop_panel

                def _on_trace(trace: dict) -> None:
                    sop_panel_ref.add_trace_entry(trace)

                control_engine._trace_cb = _on_trace

        # v3.5.0: Wire TrainingPanel.registry_changed → SopEditorPanel refresh
        self._training_panel.registry_changed.connect(self._on_registry_changed)

        # Make LlmPanel's parent calls work
        # (LlmPanel calls self.parent().on_llm_send() etc.)

    def _update_status(self) -> None:
        if not _QT_AVAILABLE:
            return
        n_steps = len(self._steps)
        pin_min = self._config.get("pin_count_min", "?")
        pin_max = self._config.get("pin_count_max", "?")
        llm_enabled = self._config.get("llm", {}).get("enabled", False)

        self._lbl_steps.setText(f"{n_steps} steps")
        self._lbl_pins.setText(f"Pins: {pin_min}/{pin_max}")
        self._lbl_llm.setText(f"LLM: {'✓' if llm_enabled else '✗'}")

        # OCR status
        if self._ocr is not None:
            backend = getattr(self._ocr, "_backend", "?")
            self._lbl_ocr.setText(f"OCR: {backend}")
        else:
            self._lbl_ocr.setText("OCR: ✗")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_run_sop(self) -> None:
        if self._sop_executor is None:
            if _QT_AVAILABLE:
                QMessageBox.warning(
                    self, "Cannot Run SOP", "SopExecutor is not initialized."
                )
            return

        self._sop_panel.set_running(True)
        self._sop_panel.append_log("=" * 60)
        self._lbl_status.setText("Status: RUNNING")

        # M2: start popup monitor during SOP execution
        if self._exc_monitor_timer is not None:
            self._exc_monitor_timer.start()

        # Create a fresh LogManager for this run
        try:
            from src.log_manager import LogManager

            self._log_manager = LogManager()
        except Exception:  # noqa: BLE001
            self._log_manager = None

        self._worker = SopWorker(self._sop_executor, steps=self._steps)
        self._worker.step_started.connect(self._sop_panel.on_step_started)
        self._worker.step_finished.connect(self._sop_panel.on_step_finished)
        self._worker.log_message.connect(self._sop_panel.on_log_message)
        self._worker.log_message.connect(self._on_worker_log)
        self._worker.screenshot_ready.connect(self._on_screenshot_ready)
        self._worker.screenshot_ready.connect(self._on_screenshot_for_training)
        self._worker.sop_finished.connect(self._on_sop_finished)
        self._worker.start()
        # Minimize window during SOP execution to prevent GUI elements
        # (buttons, log text) from interfering with OCR screen recognition.
        self.showMinimized()

    def _on_stop_sop(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.abort()

    def _on_worker_log(self, text: str) -> None:
        """Forward SOP worker log lines to the active LogManager."""
        if self._log_manager is not None:
            try:
                self._log_manager.log(step="sop", message=text)
            except Exception:  # noqa: BLE001
                pass

    def _on_screenshot_ready(self, img: Any) -> None:
        """Convert a numpy BGR ndarray to QPixmap and show in VisionPanel."""
        if not _QT_AVAILABLE:
            return
        try:
            import numpy as np  # noqa: PLC0415

            arr = img
            if not isinstance(arr, np.ndarray):
                return
            # BGR → RGB
            rgb = arr[:, :, ::-1].copy()
            h, w, ch = rgb.shape
            qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
            pmap = QPixmap.fromImage(qimg)
            self._vision_panel.set_screenshot(pmap)

            # YOLO detection — run if vision engine is available
            if self._vision is not None:
                try:
                    detections = self._vision.detect(arr)
                    det_list = [
                        {
                            "label": d.label,
                            "bbox": list(d.bbox),
                            "conf": d.confidence,
                        }
                        for d in detections
                    ]
                    self._vision_panel.set_detections(det_list)
                except Exception:  # noqa: BLE001
                    pass  # detection failed — still show screenshot
        except Exception:  # noqa: BLE001
            pass

    def _on_sop_finished(self, success: bool, summary: str) -> None:
        self._sop_panel.on_sop_finished(success, summary)
        status = "DONE" if success else "FAILED"
        self._lbl_status.setText(f"Status: {status}")
        # M2: stop popup monitor
        if self._exc_monitor_timer is not None:
            self._exc_monitor_timer.stop()
        # Finalize LogManager
        if self._log_manager is not None:
            try:
                self._log_manager.finalize(success=success)
            except Exception:  # noqa: BLE001
                pass
        if self._audit_panel:
            self._audit_panel.refresh()
        # Restore window after SOP completes (was minimized to avoid OCR interference).
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _on_apply_patch(
        self, patch: Dict[str, Any], username: str, reason: str
    ) -> None:
        """Apply a config patch from the LLM chat panel."""
        if not _QT_AVAILABLE:
            return
        allow_write = self._config.get("llm", {}).get("allow_config_write", False)
        if not allow_write:
            QMessageBox.warning(
                self,
                "Direct Edit Disabled",
                "llm.allow_config_write is false in config.json.\n"
                "Saving as config.proposed.json instead.",
            )
            try:
                from src.sop_advisor import apply_config_patch, write_proposed_config

                new_cfg, warnings = apply_config_patch(self._config, patch)
                proposed = write_proposed_config(self._config_path, new_cfg)
                msg = f"config.proposed.json saved:\n{proposed}"
                if warnings:
                    msg += "\n\nWarnings:\n" + "\n".join(warnings)
                QMessageBox.information(self, "Saved", msg)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "Save Error", str(exc))
            return

        try:
            from src.sop_advisor import apply_config_direct

            new_cfg, warnings, entry = apply_config_direct(
                config=self._config,
                patch=patch,
                config_path=self._config_path,
                audit_log=self._audit_log,
                username=username,
                reason=reason,
                source="llm_chat",
            )
            self._config = new_cfg
            self._config_panel.set_config(new_cfg)
            msg = "config.json updated successfully!"
            if warnings:
                msg += "\n\nWarnings:\n" + "\n".join(warnings)
            QMessageBox.information(self, "Applied", msg)
            self._audit_panel.refresh()
            self._update_status()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Apply Error", str(exc))

    def _on_screenshot_for_training(self, img: Any) -> None:
        """Forward the latest SOP screenshot to the Training panel for annotation."""
        try:
            import numpy as np  # noqa: PLC0415

            if isinstance(img, np.ndarray):
                self._training_panel.set_image_for_annotation(img, "sop_capture.png")
        except Exception:  # noqa: BLE001
            pass

    def _on_tab_changed(self, index: int) -> None:
        # Refresh audit log when Audit tab (index 5) is shown
        if index == 5 and self._audit_panel:
            self._audit_panel.refresh()

    # ------------------------------------------------------------------
    # LLM log context injection helpers
    # ------------------------------------------------------------------

    def _load_recent_log_events(self, max_events: int = 20) -> list:
        """Load last ``max_events`` log entries from the most recent logs/ run dir.

        Returns a list of ``types.SimpleNamespace`` objects with
        ``.level``, ``.step``, ``.message`` attributes.
        Never raises — returns [] on any error.
        """
        import types

        try:
            logs_dir = Path("logs")
            if not logs_dir.exists():
                return []
            run_dirs = sorted(
                [p for p in logs_dir.iterdir() if p.is_dir()],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for run_dir in run_dirs[:3]:
                events_file = run_dir / "events.jsonl"
                if not events_file.exists():
                    continue
                try:
                    raw = events_file.read_text(encoding="utf-8").strip().splitlines()
                    events = []
                    for line in raw[-max_events:]:
                        try:
                            d = json.loads(line)
                            ev = types.SimpleNamespace(
                                level=d.get("level", "INFO"),
                                step=d.get("step", ""),
                                message=d.get("message", ""),
                            )
                            events.append(ev)
                        except Exception:
                            continue
                    if events:
                        return events
                except Exception:
                    continue
        except Exception:
            pass
        return []

    def _build_log_context_for_llm(self) -> str:
        """Build a compact recent-log summary to inject into the LLM system prompt.

        Priority:
        1. Active ``_log_manager`` in-memory events (current run).
        2. Most recent ``logs/{run_id}/events.jsonl`` on disk.
        3. CycleDetector sample count if available.

        Returns empty string when no log data is found.
        """
        try:
            events: list = []
            run_summary = ""

            if self._log_manager is not None and getattr(
                self._log_manager, "events", None
            ):
                events = self._log_manager.events[-20:]
                try:
                    summary_path = self._log_manager.run_dir / "summary.json"
                    if summary_path.exists():
                        s = json.loads(summary_path.read_text())
                        status = "SUCCESS" if s.get("success") else "FAILED"
                        err = s.get("error", "")
                        run_summary = "Run " + status + (f": {err}" if err else "")
                except Exception:
                    pass
            else:
                events = self._load_recent_log_events(20)

            if not events:
                return ""

            lines = [run_summary] if run_summary else []
            for ev in events:
                lvl = getattr(ev, "level", "INFO")
                step = getattr(ev, "step", "")
                msg = getattr(ev, "message", "")[:80]
                prefix = "⚠" if lvl in ("ERROR", "WARNING") else "·"
                lines.append(f"{prefix}[{step}] {msg}")

            # Append CycleDetector stats if available
            try:
                from src.cycle_detector import CycleDetector  # noqa: PLC0415

                cd_summary = CycleDetector().build_improvement_summary(n_recent=10)
                count = cd_summary.get("sample_count", 0)
                if count > 0:
                    lines.append(f"CYCLE: {count} recent runs recorded")
            except Exception:
                pass

            return "RECENT ISSUES:\n" + "\n".join(lines)
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # H1: Training completion handler
    # ------------------------------------------------------------------

    def _on_training_finished(self, weights_path: str) -> None:
        """Called when TrainingPanel emits training_finished.

        Updates the status bar so the operator knows the Vision model
        has been refreshed without needing to check the Training tab.
        """
        if not _QT_AVAILABLE:
            return
        self._lbl_status.setText("Status: MODEL UPDATED — capture to verify")
        self._lbl_status.setToolTip(f"New weights: {weights_path}")

    def _on_registry_changed(self) -> None:
        """Called when TrainingPanel.registry_changed is emitted (new class saved).

        Reloads SopEditorPanel steps so the target-class dropdown picks up
        any newly registered classes without requiring a restart.
        """
        if hasattr(self._sop_editor_panel, "_load_steps"):
            try:
                self._sop_editor_panel._load_steps()
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------
    # M2: ExceptionHandler periodic popup monitor
    # ------------------------------------------------------------------

    def _on_exception_popup_tick(self) -> None:
        """Periodic popup scanner running every 5 s during SOP execution.

        Detects Windows dialogs (Update, Activation, UAC, SmartScreen) that
        would block SOP button clicks.  Logs a warning in the SOP panel so
        the operator can manually dismiss the popup.  Full auto-recovery via
        ExceptionHandler.handle_exception() is not attempted here to avoid
        interfering with the in-progress SOP worker thread.
        """
        if self._exception_handler is None:
            return
        if self._worker is None or not self._worker.isRunning():
            return
        try:
            popup = self._exception_handler.detect_popup()
            if popup:
                title = popup.get("title", "Unknown dialog")
                msg = f"⚠ Popup detected: '{title}' — please dismiss manually"
                self._sop_panel.append_log(msg)
                self._lbl_status.setText("Status: POPUP DETECTED")
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # H2 + H4 + M3: Startup preflight checks
    # ------------------------------------------------------------------

    def _run_preflight(self) -> None:
        """Run resolution + OCR health checks after the UI is fully shown.

        Deferred 500 ms via QTimer so the main window is visible first.
        """
        self._check_screen_resolution()  # H4
        self._run_ocr_health_check()  # H2

    def _check_screen_resolution(self) -> None:
        """H4: Warn if the primary screen is not 1920×1080."""
        if not _QT_AVAILABLE:
            return
        try:
            screen = QApplication.primaryScreen()
            if screen is None:
                return
            size = screen.size()
            w, h = size.width(), size.height()
            if w != 1920 or h != 1080:
                QMessageBox.warning(
                    self,
                    "Screen Resolution Warning",
                    f"Current resolution: {w}×{h}\n"
                    "Recommended: 1920×1080\n\n"
                    "YOLO26x detection and OCR are calibrated for 1920×1080.\n"
                    "SOP step failures may occur at other resolutions.\n\n"
                    "To fix: Right-click desktop → Display settings → Resolution.",
                )
        except Exception:  # noqa: BLE001
            pass

    def _run_ocr_health_check(self) -> None:
        """H2: Quick OCR self-test and update status bar indicator."""
        if not _QT_AVAILABLE or self._ocr is None:
            return
        try:
            import cv2  # noqa: PLC0415
            import numpy as np  # noqa: PLC0415

            img = np.ones((60, 200, 3), dtype=np.uint8) * 255
            cv2.putText(
                img, "Login", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 2
            )
            regions = self._ocr.scan_all(img)
            backend = getattr(self._ocr, "_backend", "?")
            if regions:
                self._lbl_ocr.setText(f"OCR: {backend} ✓")
                self._lbl_ocr.setToolTip(
                    f"OCR health: OK — {len(regions)} region(s) detected"
                )
            else:
                self._lbl_ocr.setText(f"OCR: {backend} ⚠")
                self._lbl_ocr.setToolTip(
                    "OCR health: 0 regions — button detection may be unreliable"
                )
        except Exception as exc:  # noqa: BLE001
            backend = getattr(self._ocr, "_backend", "?")
            self._lbl_ocr.setText(f"OCR: {backend} ⚠")
            self._lbl_ocr.setToolTip(f"OCR health check failed: {exc}")
