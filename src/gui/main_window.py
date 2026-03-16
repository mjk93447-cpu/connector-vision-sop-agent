"""
MainWindow — PyQt6 QMainWindow for Connector Vision SOP Agent.

Six-tab layout:
  Tab 1 (▶ Run SOP)   — SopPanel
  Tab 2 (👁 Vision)   — VisionPanel
  Tab 3 (💬 LLM Chat) — LlmPanel
  Tab 4 (📋 SOP Edit) — SopEditorPanel
  Tab 5 (⚙ Config)   — ConfigPanel
  Tab 6 (📊 Audit)    — AuditPanel

The window wires QThread workers (SopWorker, LLMWorker) so all
heavy computation runs off the main thread.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from PyQt6.QtWidgets import (
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
from src.gui.panels.vision_panel import VisionPanel
from src.gui.workers import AnalysisWorker, LLMWorker, SopWorker

_APP_VERSION = "3.0.0"


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
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._config = config or {}
        self._config_path = config_path or Path("assets/config.json")
        self._sop_steps_path = sop_steps_path or Path("assets/sop_steps.json")
        self._sop_executor = sop_executor
        self._llm = llm
        self._audit_log = audit_log
        self._steps: List[Dict[str, Any]] = []
        self._worker: Optional[Any] = None
        self._llm_worker: Optional[Any] = None

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

    def on_llm_send(self, history: List[Dict[str, str]]) -> None:
        """Start LLMWorker for a chat turn."""
        if self._llm is None:
            self._llm_panel.on_llm_error(
                "LLM이 설정되지 않았습니다. config.json의 llm 설정을 확인하세요."
            )
            return
        system = (
            "당신은 삼성 OLED 커넥터 라인 SOP 전문가입니다. "
            "엔지니어가 SOP 실행 문제를 해결할 수 있도록 친절하고 정확하게 도와주세요. "
            "한국어로 응답하되, 필요하면 영어 기술 용어를 사용하세요."
        )
        self._llm_worker = LLMWorker(self._llm, system_prompt=system, history=history)
        self._llm_worker.response_ready.connect(self._llm_panel.on_llm_response)
        self._llm_worker.error_occurred.connect(self._llm_panel.on_llm_error)
        self._llm_worker.start()

    def on_llm_analyze(self) -> None:
        """Start AnalysisWorker using the latest log payload."""
        if self._llm is None:
            self._llm_panel.on_llm_error("LLM이 설정되지 않았습니다.")
            return
        # Build a basic payload — in Phase 2 we'll use LogManager.build_llm_payload()
        payload: Dict[str, Any] = {
            "summary": "최근 SOP 실행 로그 분석 요청",
            "config": self._config,
        }
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
        self._sop_panel = SopPanel(steps=self._steps)
        self._vision_panel = VisionPanel()
        self._llm_panel = LlmPanel()
        self._sop_editor_panel = SopEditorPanel(sop_path=self._sop_steps_path)
        self._config_panel = ConfigPanel(
            config=self._config, config_path=self._config_path
        )
        self._audit_panel = AuditPanel(audit_log=self._audit_log)

        self._tabs.addTab(self._sop_panel, "▶ Run SOP")
        self._tabs.addTab(self._vision_panel, "👁 Vision")
        self._tabs.addTab(self._llm_panel, "💬 LLM Chat")
        self._tabs.addTab(self._sop_editor_panel, "📋 SOP Editor")
        self._tabs.addTab(self._config_panel, "⚙ Config")
        self._tabs.addTab(self._audit_panel, "📊 Audit")

        self.setCentralWidget(self._tabs)

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._lbl_status = QLabel("Status: READY")
        self._lbl_steps = QLabel("0 steps")
        self._lbl_pins = QLabel("Pins: –/–")
        self._lbl_llm = QLabel("LLM: –")

        for lbl in [self._lbl_status, self._lbl_steps, self._lbl_pins, self._lbl_llm]:
            self._status_bar.addPermanentWidget(lbl)

        # Refresh audit every time the Audit tab is shown
        self._tabs.currentChanged.connect(self._on_tab_changed)

    def _connect_signals(self) -> None:
        if not _QT_AVAILABLE:
            return

        # Run SOP buttons
        self._sop_panel._btn_run.clicked.connect(self._on_run_sop)
        self._sop_panel._btn_stop.clicked.connect(self._on_stop_sop)

        # LLM apply patch
        self._llm_panel.apply_patch_requested.connect(self._on_apply_patch)

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

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_run_sop(self) -> None:
        if self._sop_executor is None:
            if _QT_AVAILABLE:
                QMessageBox.warning(
                    self, "SOP 실행 불가", "SopExecutor가 초기화되지 않았습니다."
                )
            return

        self._sop_panel.set_running(True)
        self._sop_panel.append_log("=" * 60)
        self._lbl_status.setText("Status: RUNNING")

        self._worker = SopWorker(self._sop_executor, steps=self._steps)
        self._worker.step_started.connect(self._sop_panel.on_step_started)
        self._worker.step_finished.connect(self._sop_panel.on_step_finished)
        self._worker.log_message.connect(self._sop_panel.on_log_message)
        self._worker.sop_finished.connect(self._on_sop_finished)
        self._worker.start()

    def _on_stop_sop(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.abort()

    def _on_sop_finished(self, success: bool, summary: str) -> None:
        self._sop_panel.on_sop_finished(success, summary)
        status = "DONE" if success else "FAILED"
        self._lbl_status.setText(f"Status: {status}")
        if self._audit_panel:
            self._audit_panel.refresh()

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
                "직접 수정 비활성화",
                "config.json의 llm.allow_config_write가 false입니다.\n"
                "대신 config.proposed.json으로 저장합니다.",
            )
            try:
                from src.sop_advisor import apply_config_patch, write_proposed_config

                new_cfg, warnings = apply_config_patch(self._config, patch)
                proposed = write_proposed_config(self._config_path, new_cfg)
                msg = f"config.proposed.json 저장 완료:\n{proposed}"
                if warnings:
                    msg += "\n\n경고:\n" + "\n".join(warnings)
                QMessageBox.information(self, "저장 완료", msg)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "저장 오류", str(exc))
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
            msg = "config.json 직접 수정 완료!"
            if warnings:
                msg += "\n\n경고:\n" + "\n".join(warnings)
            QMessageBox.information(self, "적용 완료", msg)
            self._audit_panel.refresh()
            self._update_status()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "적용 오류", str(exc))

    def _on_tab_changed(self, index: int) -> None:
        # Refresh audit log when Audit tab (index 5) is shown
        if index == 5 and self._audit_panel:
            self._audit_panel.refresh()
