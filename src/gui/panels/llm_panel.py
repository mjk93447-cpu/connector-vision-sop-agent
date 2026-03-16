"""
Tab 3 — LLM Chat Panel.

Provides a REPL-style chat interface with the offline LLM.
Features:
  - Chat history display (QTextEdit)
  - Message input (QLineEdit)
  - Send / Analyze buttons
  - /apply command: extract config_patch from LLM response and prompt engineer approval
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

try:
    from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
    from PyQt6.QtGui import QTextCursor
    from PyQt6.QtWidgets import (
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
    pyqtSignal = object  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Apply-dialog: username + reason
# ---------------------------------------------------------------------------


class _ApplyDialog(QDialog):  # type: ignore[misc]
    """Prompt the engineer for username + reason before applying config patch."""

    def __init__(self, patch: Dict[str, Any], parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Config 직접 적용 승인")
        self.setMinimumWidth(420)
        self._patch = patch

        layout = QVBoxLayout(self)

        # Show patch summary
        box = QGroupBox("변경 내용")
        box_layout = QVBoxLayout(box)
        patch_text = json.dumps(patch, ensure_ascii=False, indent=2)
        lbl = QLabel(patch_text)
        lbl.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box_layout.addWidget(lbl)
        layout.addWidget(box)

        # Form
        form = QFormLayout()
        self._username_edit = QLineEdit()
        self._username_edit.setPlaceholderText("예: Raj Kumar")
        form.addRow("엔지니어 이름:", self._username_edit)

        self._reason_edit = QLineEdit()
        self._reason_edit.setPlaceholderText("예: SOP 재시도 횟수 증가")
        form.addRow("변경 이유:", self._reason_edit)

        layout.addLayout(form)

        # Buttons
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_accept(self) -> None:
        username = self._username_edit.text().strip()
        if not username:
            QMessageBox.warning(self, "입력 오류", "엔지니어 이름을 입력해 주세요.")
            return
        self.accept()

    def get_values(self) -> tuple[str, str]:
        return self._username_edit.text().strip(), self._reason_edit.text().strip()


# ---------------------------------------------------------------------------
# LLM Chat Panel
# ---------------------------------------------------------------------------


class LlmPanel(QWidget):  # type: ignore[misc]
    """LLM Chat tab."""

    # Emitted when engineer approves a config patch
    apply_patch_requested: Any = pyqtSignal(
        object, str, str
    )  # patch_dict, username, reason

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._history: List[Dict[str, str]] = []
        self._worker: Any = None
        self._last_llm_text: str = ""
        self._setup_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clear_history(self) -> None:
        self._history.clear()
        if _QT_AVAILABLE:
            self._chat_display.clear()

    def set_sending(self, sending: bool) -> None:
        if not _QT_AVAILABLE:
            return
        self._btn_send.setEnabled(not sending)
        self._btn_analyze.setEnabled(not sending)
        self._input.setEnabled(not sending)
        if sending:
            self._btn_send.setText("⏳ 응답 대기 중…")
        else:
            self._btn_send.setText("📤 전송")

    # ------------------------------------------------------------------
    # Private — UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        if not _QT_AVAILABLE:
            return

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header = QLabel("💬 LLM 채팅")
        header.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(header)

        # Chat display
        self._chat_display = QTextEdit()
        self._chat_display.setReadOnly(True)
        self._chat_display.setStyleSheet(
            "font-family: Malgun Gothic, sans-serif; font-size: 12px;"
            "background: #fafafa; padding: 6px;"
        )
        layout.addWidget(self._chat_display, stretch=1)

        # Apply button (visible when LLM suggests config changes)
        self._btn_apply = QPushButton("⚙ config 직접 적용 (/apply)")
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
            "LLM에게 질문하세요… (Enter 전송, /apply 로 설정 적용)"
        )
        self._input.returnPressed.connect(self._on_send)
        input_row.addWidget(self._input)

        self._btn_send = QPushButton("📤 전송")
        self._btn_send.clicked.connect(self._on_send)
        input_row.addWidget(self._btn_send)

        self._btn_analyze = QPushButton("🔍 로그 분석")
        self._btn_analyze.setToolTip("최근 SOP 실행 로그를 LLM에 분석 요청")
        self._btn_analyze.clicked.connect(self._on_analyze)
        input_row.addWidget(self._btn_analyze)

        layout.addLayout(input_row)

    def _append_bubble(self, role: str, text: str) -> None:
        """Append a chat bubble (user / assistant) to the display."""
        if not _QT_AVAILABLE:
            return
        if role == "user":
            html = (
                f'<p style="text-align:right; margin:4px;">'
                f'<span style="background:#e3f2fd; padding:4px 8px; border-radius:8px;">'
                f"<b>나:</b> {self._escape(text)}</span></p>"
            )
        else:
            html = (
                f'<p style="text-align:left; margin:4px;">'
                f'<span style="background:#f1f8e9; padding:4px 8px; border-radius:8px;">'
                f"<b>AI:</b> {self._escape(text)}</span></p>"
            )
        self._chat_display.append(html)
        self._chat_display.moveCursor(QTextCursor.MoveOperation.End)

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
        # Also try bare JSON block
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

    # ------------------------------------------------------------------
    # Slots / event handlers
    # ------------------------------------------------------------------

    def _on_send(self) -> None:
        if not _QT_AVAILABLE:
            return
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

        # Signal MainWindow to start LLMWorker
        # MainWindow connects to _btn_send via the panel reference
        self.set_sending(True)
        # Emitted to parent — MainWindow handles worker creation
        self.findChild  # keep reference
        parent = self.parent()
        if parent and hasattr(parent, "on_llm_send"):
            parent.on_llm_send(self._history[:])  # type: ignore[union-attr]

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
                "config_patch 없음",
                "마지막 LLM 응답에서 config_patch를 찾을 수 없습니다.",
            )
            return
        dlg = _ApplyDialog(patch, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            username, reason = dlg.get_values()
            self.apply_patch_requested.emit(patch, username, reason)

    @pyqtSlot(str)
    def on_llm_response(self, text: str) -> None:
        self._last_llm_text = text
        self._history.append({"role": "assistant", "content": text})
        self._append_bubble("assistant", text)
        self.set_sending(False)
        # Enable apply button if patch detected
        if _QT_AVAILABLE:
            patch = self._extract_patch(text)
            self._btn_apply.setEnabled(patch is not None)

    @pyqtSlot(str)
    def on_llm_error(self, error: str) -> None:
        self._append_bubble("assistant", f"❌ 오류: {error}")
        self.set_sending(False)

    @pyqtSlot(object)
    def on_analysis_ready(self, result: Any) -> None:
        if not isinstance(result, dict):
            return
        raw = result.get("raw_text", "")
        if not raw:
            recs = result.get("sop_recommendations", [])
            patch = result.get("config_patch", {})
            lines = ["📊 로그 분석 결과:"]
            if patch:
                lines.append(f"  config_patch: {json.dumps(patch, ensure_ascii=False)}")
            for r in recs:
                lines.append(f"  • {r}")
            raw = "\n".join(lines)
        self.on_llm_response(raw)
