"""
Tab 3 — LLM Chat Panel (v3.0 — Streaming + English UI).

Features:
  - ChatGPT-style streaming: tokens appear one by one as LLM generates them
  - Elapsed timer: shows "Thinking... 12.4s" while waiting
  - Brief mode: shorter token limit for faster answers (toggle button)
  - Log analysis: send recent SOP run logs to LLM for diagnosis
  - /apply command: extract config_patch and prompt engineer approval
  - All UI text in English for Indian line engineers
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional

try:
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
    from PyQt6.QtGui import QTextCursor
    from PyQt6.QtWidgets import (
        QCheckBox,
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False
    QWidget = object  # type: ignore[assignment,misc]
    QDialog = object  # type: ignore[assignment,misc]

    class _FakeSig:  # type: ignore[no-redef]
        def __init__(self, *a: Any) -> None:
            pass

        def emit(self, *a: Any) -> None:
            pass

        def connect(self, *a: Any) -> None:
            pass

    pyqtSignal = _FakeSig  # type: ignore[assignment]
    pyqtSlot = lambda *a, **kw: (lambda f: f)  # type: ignore[assignment]  # noqa: E731


# ---------------------------------------------------------------------------
# Apply dialog (English UI)
# ---------------------------------------------------------------------------


class _ApplyDialog(QDialog):  # type: ignore[misc]
    """Prompt the engineer for username + reason before applying config patch."""

    def __init__(self, patch: Dict[str, Any], parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Approve Config Change")
        self.setMinimumWidth(440)
        self._patch = patch

        layout = QVBoxLayout(self)

        box = QGroupBox("Changes to apply")
        box_layout = QVBoxLayout(box)
        patch_text = json.dumps(patch, ensure_ascii=False, indent=2)
        lbl = QLabel(patch_text)
        lbl.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box_layout.addWidget(lbl)
        layout.addWidget(box)

        form = QFormLayout()
        self._username_edit = QLineEdit()
        self._username_edit.setPlaceholderText("e.g. Raj Kumar")
        form.addRow("Engineer name:", self._username_edit)

        self._reason_edit = QLineEdit()
        self._reason_edit.setPlaceholderText("e.g. Increase SOP retry count")
        form.addRow("Reason for change:", self._reason_edit)

        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_accept(self) -> None:
        username = self._username_edit.text().strip()
        if not username:
            QMessageBox.warning(
                self, "Input Required", "Please enter your engineer name."
            )
            return
        self.accept()

    def get_values(self) -> tuple[str, str]:
        return self._username_edit.text().strip(), self._reason_edit.text().strip()


# ---------------------------------------------------------------------------
# LLM Chat Panel
# ---------------------------------------------------------------------------


class LlmPanel(QWidget):  # type: ignore[misc]
    """LLM Chat tab — streaming, English UI, elapsed timer."""

    apply_patch_requested: Any = pyqtSignal(object, str, str)  # patch, username, reason

    # System prompt for line PC context
    _SYSTEM_PROMPT = (
        "You are an expert OLED connector SOP assistant for a factory line PC. "
        "You help Indian line engineers diagnose vision detection failures, "
        "interpret SOP logs, and suggest configuration improvements. "
        "Always respond in clear, concise English."
    )

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._history: List[Dict[str, str]] = []
        self._worker: Any = None
        self._last_llm_text: str = ""
        self._brief_mode: bool = True  # Step 2-B: Brief ON by default
        self._t0: float = 0.0
        self._streaming_buffer: str = ""
        self._timer: Optional[Any] = None
        # Step 2-C: token buffer for batched QTextEdit rendering
        self._token_buf: List[str] = []
        self._flush_timer: Optional[Any] = None
        self._setup_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clear_history(self) -> None:
        self._history.clear()
        if _QT_AVAILABLE:
            self._chat_display.clear()

    def set_brief_mode(self, enabled: bool) -> None:
        self._brief_mode = enabled

    def set_sending(self, sending: bool) -> None:
        if not _QT_AVAILABLE:
            return
        self._btn_analyze.setEnabled(not sending)
        self._input.setEnabled(not sending)
        if sending:
            # Step 2-D: show Stop button during generation
            self._btn_send.setText("⏹ Stop")
            self._btn_send.setEnabled(True)  # keep enabled so user can stop
            self._t0 = time.perf_counter()
            self._start_timer()
            self._start_flush_timer()
        else:
            self._btn_send.setText("📤 Send")
            self._btn_send.setEnabled(True)
            self._stop_timer()
            self._stop_flush_timer()
            self._flush_token_buf()  # flush any remaining buffered tokens
            self._lbl_elapsed.setText("")

    # ------------------------------------------------------------------
    # Private — UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        if not _QT_AVAILABLE:
            return

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header row
        hdr_row = QHBoxLayout()
        header = QLabel("💬 AI Assistant")
        header.setStyleSheet("font-size: 14px; font-weight: bold;")
        hdr_row.addWidget(header)
        hdr_row.addStretch()

        # Brief mode checkbox — Step 2-B: default ON to reduce worst-case wait
        self._chk_brief = QCheckBox("⚡ Brief mode (faster)")
        self._chk_brief.setToolTip(
            "Shorter response — fewer tokens, faster answer.\n"
            "Best for quick yes/no or status questions."
        )
        self._chk_brief.setChecked(True)  # ON by default (256 tokens vs 1024)
        self._chk_brief.toggled.connect(self.set_brief_mode)
        hdr_row.addWidget(self._chk_brief)

        layout.addLayout(hdr_row)

        # Elapsed timer label
        self._lbl_elapsed = QLabel("")
        self._lbl_elapsed.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._lbl_elapsed)

        # Chat display
        self._chat_display = QTextEdit()
        self._chat_display.setReadOnly(True)
        self._chat_display.setStyleSheet(
            "font-family: Segoe UI, Arial, sans-serif; font-size: 12px;"
            "background: #fafafa; padding: 6px;"
        )
        layout.addWidget(self._chat_display, stretch=1)

        # Apply button
        self._btn_apply = QPushButton("⚙ Apply config patch (/apply)")
        self._btn_apply.setStyleSheet(
            "background-color: #ff9800; color: white; font-weight: bold; padding: 6px;"
        )
        self._btn_apply.setEnabled(False)
        self._btn_apply.clicked.connect(self._on_apply_clicked)
        layout.addWidget(self._btn_apply)

        # Input row
        input_row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText(
            "Ask AI assistant... (Enter to send, /apply to apply config)"
        )
        self._input.returnPressed.connect(self._on_send)
        input_row.addWidget(self._input)

        self._btn_send = QPushButton("📤 Send")
        self._btn_send.clicked.connect(self._on_send)
        input_row.addWidget(self._btn_send)

        self._btn_analyze = QPushButton("🔍 Analyze Logs")
        self._btn_analyze.setToolTip("Send recent SOP run logs to AI for analysis")
        self._btn_analyze.clicked.connect(self._on_analyze)
        input_row.addWidget(self._btn_analyze)

        layout.addLayout(input_row)

        # Welcome message
        self._append_system(
            "AI Assistant ready. Ask about SOP failures, vision detection, "
            "or connector pin issues. Type /apply to apply a suggested config change."
        )

    def _append_bubble(self, role: str, text: str) -> None:
        if not _QT_AVAILABLE:
            return
        if role == "user":
            html = (
                f'<p style="text-align:right; margin:4px;">'
                f'<span style="background:#e3f2fd; padding:4px 8px; border-radius:8px;">'
                f"<b>You:</b> {self._escape(text)}</span></p>"
            )
        else:
            html = (
                f'<p style="text-align:left; margin:4px;">'
                f'<span style="background:#f1f8e9; padding:4px 8px; border-radius:8px;">'
                f"<b>AI:</b> {self._escape(text)}</span></p>"
            )
        self._chat_display.append(html)
        self._chat_display.moveCursor(QTextCursor.MoveOperation.End)

    def _append_system(self, text: str) -> None:
        if not _QT_AVAILABLE:
            return
        html = (
            f'<p style="text-align:center; margin:4px;">'
            f'<span style="color:#888; font-size:11px; font-style:italic;">'
            f"{self._escape(text)}</span></p>"
        )
        self._chat_display.append(html)
        self._chat_display.moveCursor(QTextCursor.MoveOperation.End)

    def _begin_streaming_bubble(self) -> None:
        """Insert an empty AI bubble that will be filled with streaming tokens."""
        if not _QT_AVAILABLE:
            return
        self._streaming_buffer = ""
        html = (
            '<p style="text-align:left; margin:4px;" id="stream_bubble">'
            '<span style="background:#f1f8e9; padding:4px 8px; border-radius:8px;">'
            "<b>AI:</b> <span id='stream_content'></span></span></p>"
        )
        self._chat_display.append(html)
        self._chat_display.moveCursor(QTextCursor.MoveOperation.End)

    @pyqtSlot(str)
    def on_token_ready(self, token: str) -> None:
        """Buffer a streaming token — rendered every 50ms by flush timer (Step 2-C)."""
        if not _QT_AVAILABLE:
            return
        self._token_buf.append(token)

    @pyqtSlot(str)
    def on_think_token_ready(self, token: str) -> None:
        """Handle a <think> reasoning token — update elapsed label with thinking hint."""
        if not _QT_AVAILABLE:
            return
        # Show a brief "thinking…" hint in elapsed label rather than cluttering chat
        elapsed = time.perf_counter() - self._t0 if self._t0 > 0 else 0
        self._lbl_elapsed.setText(f"🤔 Reasoning... {elapsed:.1f}s")

    def _flush_token_buf(self) -> None:
        """Flush the token buffer to QTextEdit in one repaint (Step 2-C)."""
        if not _QT_AVAILABLE or not self._token_buf:
            return
        chunk = "".join(self._token_buf)
        self._token_buf.clear()
        self._streaming_buffer += chunk
        # Replace entire last block with updated content
        cursor = self._chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
        escaped = self._escape(self._streaming_buffer)
        html = (
            f'<span style="background:#f1f8e9; padding:4px 8px; border-radius:8px;">'
            f"<b>AI:</b> {escaped}</span>"
        )
        cursor.insertHtml(html)
        self._chat_display.moveCursor(QTextCursor.MoveOperation.End)

    def _start_flush_timer(self) -> None:
        """Start the 50ms flush timer for batched token rendering."""
        if not _QT_AVAILABLE:
            return
        if self._flush_timer is None:
            self._flush_timer = QTimer(self)
            self._flush_timer.timeout.connect(self._flush_token_buf)
        self._flush_timer.start(50)

    def _stop_flush_timer(self) -> None:
        if self._flush_timer is not None:
            self._flush_timer.stop()

    @pyqtSlot(float)
    def on_elapsed_tick(self, elapsed: float) -> None:
        if _QT_AVAILABLE:
            self._lbl_elapsed.setText(f"Thinking... {elapsed:.1f}s")

    @staticmethod
    def _escape(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )

    def _extract_patch(self, text: str) -> Optional[Dict[str, Any]]:
        """Try to extract a JSON config_patch block from LLM response text."""
        pattern = r"config[_\s]*patch\s*[:\-]?\s*(\{[^}]+\})"
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        json_pattern = r"```(?:json)?\s*(\{[^`]+\})\s*```"
        m2 = re.search(json_pattern, text, re.DOTALL)
        if m2:
            try:
                obj = json.loads(m2.group(1))
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass
        return None

    def _start_timer(self) -> None:
        if not _QT_AVAILABLE:
            return
        if self._timer is None:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._tick_timer)
        self._timer.start(500)  # update every 500ms

    def _stop_timer(self) -> None:
        if self._timer is not None:
            self._timer.stop()

    def _tick_timer(self) -> None:
        if self._t0 > 0:
            elapsed = time.perf_counter() - self._t0
            self._lbl_elapsed.setText(f"Thinking... {elapsed:.1f}s")

    # ------------------------------------------------------------------
    # Slots / event handlers
    # ------------------------------------------------------------------

    def _on_send(self) -> None:
        if not _QT_AVAILABLE:
            return

        # Step 2-D: if we're already sending, this acts as Stop
        if self._worker is not None and hasattr(self._worker, "isRunning"):
            try:
                if self._worker.isRunning():
                    self._worker.stop()
                    self.set_sending(False)
                    self._append_system("⏹ Generation stopped by user.")
                    return
            except Exception:  # noqa: BLE001
                pass

        text = self._input.text().strip()
        if not text:
            return

        if text.lower() == "/apply":
            self._on_apply_clicked()
            self._input.clear()
            return

        self._input.clear()
        self._append_bubble("user", text)
        self._history.append({"role": "user", "content": text})

        self.set_sending(True)
        self._begin_streaming_bubble()

        parent = self.parent()
        if parent and hasattr(parent, "on_llm_send"):
            parent.on_llm_send(  # type: ignore[union-attr]
                self._history[:],
                system=self._SYSTEM_PROMPT,
                brief=self._brief_mode,
                streaming=True,
            )

    def _on_analyze(self) -> None:
        parent = self.parent()
        if parent and hasattr(parent, "on_llm_analyze"):
            parent.on_llm_analyze()  # type: ignore[union-attr]

    def _on_apply_clicked(self) -> None:
        if not _QT_AVAILABLE:
            return
        patch = self._extract_patch(self._last_llm_text)
        if not patch:
            QMessageBox.information(
                self,
                "No config_patch found",
                "No config_patch was found in the last AI response.",
            )
            return
        dlg = _ApplyDialog(patch, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            username, reason = dlg.get_values()
            self.apply_patch_requested.emit(patch, username, reason)

    @pyqtSlot(str)
    def on_llm_response(self, text: str) -> None:
        """Called when non-streaming LLM response is complete."""
        self._last_llm_text = text
        self._history.append({"role": "assistant", "content": text})
        self._append_bubble("assistant", text)
        self.set_sending(False)
        if _QT_AVAILABLE:
            patch = self._extract_patch(text)
            self._btn_apply.setEnabled(patch is not None)

    @pyqtSlot(str)
    def on_streaming_done(self, full_text: str) -> None:
        """Called when streaming response is fully assembled."""
        self._last_llm_text = full_text
        self._history.append({"role": "assistant", "content": full_text})
        self.set_sending(False)
        elapsed = time.perf_counter() - self._t0 if self._t0 > 0 else 0
        self._lbl_elapsed.setText(f"Response complete ({elapsed:.1f}s)")
        if _QT_AVAILABLE:
            patch = self._extract_patch(full_text)
            self._btn_apply.setEnabled(patch is not None)

    @pyqtSlot(str)
    def on_llm_error(self, error: str) -> None:
        self._append_bubble("assistant", f"❌ Error: {error}")
        self._append_system(
            "Tip: Check that Ollama is running (start_agent.bat) "
            "and LLM settings are correct in Tab 5 Config."
        )
        self.set_sending(False)

    @pyqtSlot(object)
    def on_analysis_ready(self, result: Any) -> None:
        if not isinstance(result, dict):
            return
        raw = result.get("raw_text", "")
        if not raw:
            recs = result.get("sop_recommendations", [])
            patch = result.get("config_patch", {})
            lines = ["📊 Log Analysis Results:"]
            if patch:
                lines.append(f"  config_patch: {json.dumps(patch, ensure_ascii=False)}")
            for r in recs:
                lines.append(f"  • {r}")
            raw = "\n".join(lines)
        self.on_llm_response(raw)
