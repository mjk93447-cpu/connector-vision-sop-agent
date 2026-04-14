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
    from PyQt6.QtGui import QColor, QPainter, QPen, QTextCharFormat, QTextCursor
    from PyQt6.QtWidgets import (
        QApplication,
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
# ROI Screenshot Overlay
# ---------------------------------------------------------------------------


class _RoiScreenshotOverlay(QWidget):  # type: ignore[misc]
    """Fullscreen transparent overlay for ROI screenshot selection.

    Shows a semi-transparent dark veil over the screen.
    User drags to mark a region; mouse-release emits roi_selected(x, y, w, h).
    Press Escape to cancel.
    """

    roi_selected: Any = pyqtSignal(int, int, int, int)  # x, y, w, h (screen coords)
    cancelled: Any = pyqtSignal()

    def __init__(self) -> None:
        if _QT_AVAILABLE:
            super().__init__(None)  # top-level, no parent
        self._start: Any = None
        self._end: Any = None
        self._dragging = False

        if not _QT_AVAILABLE:
            return

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setCursor(Qt.CursorShape.CrossCursor)

        screen = QApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())
        self.showFullScreen()

    def keyPressEvent(self, event: Any) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.close()

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = event.position().toPoint()
            self._end = self._start
            self._dragging = True
            self.update()

    def mouseMoveEvent(self, event: Any) -> None:
        if self._dragging:
            self._end = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self._end = event.position().toPoint()
            self.close()
            if self._start and self._end:
                x = min(self._start.x(), self._end.x())
                y = min(self._start.y(), self._end.y())
                w = abs(self._end.x() - self._start.x())
                h = abs(self._end.y() - self._start.y())
                if w > 10 and h > 10:
                    self.roi_selected.emit(x, y, w, h)
                else:
                    self.cancelled.emit()
            else:
                self.cancelled.emit()

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        # Semi-transparent dark overlay
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        if self._start and self._end:
            x = min(self._start.x(), self._end.x())
            y = min(self._start.y(), self._end.y())
            w = abs(self._end.x() - self._start.x())
            h = abs(self._end.y() - self._start.y())
            # Transparent "hole" for selected region
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(x, y, w, h, QColor(0, 0, 0, 0))
            # Yellow selection border
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceOver
            )
            painter.setPen(QPen(QColor(255, 220, 0), 2))
            painter.drawRect(x, y, w, h)
            # Size label
            painter.setPen(QPen(QColor(255, 255, 255)))
            label_y = max(y + 16, 16)  # keep inside screen
            painter.drawText(x + 4, label_y, f"{w}×{h}px — release to capture")
        painter.end()


# ---------------------------------------------------------------------------
# LLM Chat Panel
# ---------------------------------------------------------------------------


class LlmPanel(QWidget):  # type: ignore[misc]
    """LLM Chat tab — streaming, English UI, elapsed timer."""

    apply_patch_requested: Any = pyqtSignal(object, str, str)  # patch, username, reason

    # System prompt for line PC context — SmolLM3 specialised
    _SYSTEM_PROMPT = (
        "You are an embedded AI assistant for 'Connector Vision SOP Agent' — "
        "an OFFLINE factory automation tool for Samsung OLED connector line PCs.\n\n"
        "PROGRAM FEATURES:\n"
        "- Tab 1 Run SOP: 12 automated steps: login→recipe→image_source→"
        "mold_left_roi→mold_right_roi→axis→in_pin_up→in_pin_down→save→apply\n"
        "- Tab 2 Vision: YOLO26x detects connector_pins and GUI elements on screen\n"
        "- Tab 3 LLM Chat: You are here\n"
        "- Tab 4 SOP Editor: Enable/disable steps, edit button targets\n"
        "- Tab 5 Config: confidence_threshold (default 0.6), pin_count_min, LLM settings\n"
        "- Tab 6 Audit: Review historical SOP run logs\n"
        "- Tab 7 Training: Annotate YOLO26x dataset, finetune on GUI classes\n\n"
        "YOUR ROLE:\n"
        "1. Diagnose SOP step failures (OCR button not found, YOLO low confidence, "
        "pin count mismatch)\n"
        "2. Suggest config fixes — always include config_patch JSON block for /apply\n"
        "3. Interpret vision results (if detection missing, try confidence_threshold: 0.5)\n"
        "4. Explain pin validation failures (steps in_pin_up/in_pin_down, pin_count_min)\n\n"
        "OUTPUT: Brief English only. Config changes → config_patch: {...} JSON block.\n"
        "/no_think"
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
        self._stop_requested: bool = False
        self._pending_prompt: Optional[str] = None  # queued prompt during generation
        self._pending_image_b64: Optional[str] = (
            None  # screenshot attached to next send
        )
        self._last_think_t: float = 0.0  # 마지막 think 토큰 수신 시각
        self._stream_cursor: Any = None  # QTextCursor anchor for streaming block
        self._think_cursor: Any = None  # QTextCursor anchor for think text in main chat
        self._first_token: bool = False  # True until first answer token arrives
        self._token_count: int = 0  # tokens received in current response
        self._has_warm_llm: bool = False  # True after first successful response
        self._bubble_start_pos: int = 0  # doc position before AI bubble (for Stop)
        self._roi_overlay: Any = None  # active ROI overlay (keep reference)
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
            self._btn_send.setText("⏹ Stop")
            self._btn_send.setEnabled(True)  # keep enabled so user can stop
            self._t0 = time.perf_counter()
            self._token_count = 0  # reset token counter
            if self._has_warm_llm:
                self._lbl_elapsed.setText("⏳ Sending... (~10-30s expected)")
            else:
                self._lbl_elapsed.setText(
                    "⏳ Sending... (cold start ~30-90s, please wait)"
                )
            self._start_timer()
            self._start_flush_timer()
        else:
            self._btn_send.setText("📤 Send")
            self._btn_send.setEnabled(True)
            self._stop_timer()
            self._stop_flush_and_finalize()  # drain buffer then stop timer
            self._lbl_elapsed.setText("")
            self._stop_requested = False

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
        self._lbl_elapsed.setStyleSheet("color: #555555; font-size: 11px;")
        layout.addWidget(self._lbl_elapsed)

        # Thinking real-time panel — shows <think> tokens as they arrive
        self._txt_think = QTextEdit()
        self._txt_think.setReadOnly(True)
        self._txt_think.setMaximumHeight(80)
        self._txt_think.setStyleSheet(
            "color: #333333; font-size: 10px; font-style: italic;"
            "background: #f0f0f0; border: 1px solid #cccccc; padding: 2px;"
        )
        self._txt_think.setPlaceholderText("Model reasoning will appear here...")
        self._txt_think.hide()
        layout.addWidget(self._txt_think)

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

        self._btn_screenshot = QPushButton("📸")
        self._btn_screenshot.setToolTip("Capture screen and attach to next message")
        self._btn_screenshot.clicked.connect(self._on_attach_screenshot)
        input_row.addWidget(self._btn_screenshot)

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
            f'<span style="color:#555555; font-size:11px; font-style:italic;">'
            f"{self._escape(text)}</span></p>"
        )
        self._chat_display.append(html)
        self._chat_display.moveCursor(QTextCursor.MoveOperation.End)

    def _begin_streaming_bubble(self) -> None:
        """Insert an AI bubble header and save a cursor anchor for streaming tokens.

        Replaces the old BlockUnderCursor + insertHtml approach which caused tokens
        to be inserted at the wrong position (invisible) on first flush.
        The saved _stream_cursor is repositioned to just before the closing </p>
        so that subsequent insertText() calls append text inside the bubble.
        """
        if not _QT_AVAILABLE:
            return
        self._streaming_buffer = ""
        self._first_token = True
        self._think_cursor = None  # reset per-message think anchor
        # Reset think panel for new message
        self._txt_think.clear()
        self._txt_think.hide()
        # Save document position BEFORE inserting bubble (used by _remove_partial_bubble)
        _end_cur = self._chat_display.textCursor()
        _end_cur.movePosition(QTextCursor.MoveOperation.End)
        self._bubble_start_pos = _end_cur.position()
        # Insert the AI bubble header — cursor lands at End after append
        self._chat_display.append(
            '<p style="text-align:left; margin:4px;">'
            '<span style="background:#f1f8e9; padding:4px 8px; border-radius:8px;">'
            "<b>AI:</b> </span></p>"
        )
        # Move cursor to End, then back one character to be INSIDE the paragraph
        # (before the implicit closing newline that Qt inserts after append()).
        # All subsequent insertText() calls on this cursor will append text
        # at this anchor position, growing the bubble content in place.
        cursor = self._chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.movePosition(QTextCursor.MoveOperation.PreviousCharacter)
        self._stream_cursor = QTextCursor(cursor)
        self._chat_display.moveCursor(QTextCursor.MoveOperation.End)

    @pyqtSlot(str)
    def on_token_ready(self, token: str) -> None:
        """Buffer a streaming token — rendered every 16ms by flush timer."""
        if not _QT_AVAILABLE:
            return
        self._token_buf.append(token)
        self._token_count += 1

    @pyqtSlot(str)
    def on_think_token_ready(self, token: str) -> None:
        """Handle a <think> reasoning token — show in think panel + main chat + label."""
        if not _QT_AVAILABLE:
            return
        self._last_think_t = time.perf_counter()
        elapsed = self._last_think_t - self._t0 if self._t0 > 0 else 0
        # Show think panel on first token
        if not self._txt_think.isVisible():
            self._txt_think.show()
            self._txt_think.clear()
        # Append token to small think panel (no buffering)
        self._txt_think.moveCursor(QTextCursor.MoveOperation.End)
        self._txt_think.insertPlainText(token)
        self._txt_think.moveCursor(QTextCursor.MoveOperation.End)
        think_len = len(self._txt_think.toPlainText())
        self._lbl_elapsed.setText(
            f"\U0001f914 Reasoning... {elapsed:.1f}s | {think_len} chars"
        )
        # Also render in main chat as grey italic — eliminates the "silent" gap
        # before answer tokens arrive (first think token triggers immediate output)
        fmt_think = QTextCharFormat()
        fmt_think.setForeground(QColor("#444444"))
        fmt_think.setFontItalic(True)
        if self._think_cursor is None:
            # First think token: insert "💭 " header in main chat at current end
            cursor = self._chat_display.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            fmt_hdr = QTextCharFormat()
            fmt_hdr.setForeground(QColor("#555555"))
            fmt_hdr.setFontItalic(True)
            cursor.insertText("\U0001f4ad ", fmt_hdr)
            self._think_cursor = QTextCursor(cursor)
        self._think_cursor.insertText(token, fmt_think)
        self._chat_display.moveCursor(QTextCursor.MoveOperation.End)

    def _flush_token_buf(self) -> None:
        """Flush the token buffer to QTextEdit via the saved cursor anchor (Step 2-C).

        Uses self._stream_cursor.insertText() instead of the old
        BlockUnderCursor + insertHtml() approach, which would select the wrong
        block and render tokens invisibly on the first flush.
        """
        if not _QT_AVAILABLE or not self._token_buf:
            return
        chunk = "".join(self._token_buf)
        self._token_buf.clear()
        if self._first_token:
            # First answer token arrived: clear cold-start label, hide think panel
            self._first_token = False
            self._txt_think.hide()
            self._lbl_elapsed.setText("")
            # If think tokens were written to main chat, insert a line break
            # between the grey reasoning text and the normal answer text,
            # then re-anchor _stream_cursor at the new end position.
            if self._think_cursor is not None:
                cursor = self._chat_display.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                cursor.insertText("\n")
                self._stream_cursor = cursor  # cursor already at End after insertText
        if self._stream_cursor is None:
            return
        # insertText() handles \n natively in QTextEdit rich-text documents.
        # The cursor is anchored inside the AI bubble <p> from _begin_streaming_bubble().
        self._stream_cursor.insertText(chunk)
        self._chat_display.moveCursor(QTextCursor.MoveOperation.End)

    def _start_flush_timer(self) -> None:
        """Start the 16ms flush timer for batched token rendering (~60 fps)."""
        if not _QT_AVAILABLE:
            return
        if self._flush_timer is None:
            self._flush_timer = QTimer(self)
            self._flush_timer.timeout.connect(self._flush_token_buf)
        self._flush_timer.start(16)

    def _stop_flush_timer(self) -> None:
        if self._flush_timer is not None:
            self._flush_timer.stop()

    def _stop_flush_and_finalize(self) -> None:
        """Drain token buffer completely before stopping timer — prevents burst output."""
        self._flush_token_buf()  # ① render all buffered tokens
        self._token_buf.clear()  # ② clear any residual
        if self._flush_timer is not None and self._flush_timer.isActive():
            self._flush_timer.stop()  # ③ stop timer

    def _process_pending_prompt(self) -> None:
        """Auto-send queued prompt after current generation finishes."""
        if self._pending_prompt:
            prompt, self._pending_prompt = self._pending_prompt, None
            self._input.setText(prompt)
            self._on_send()

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
            now = time.perf_counter()
            elapsed = now - self._t0
            token_info = (
                f" | {self._token_count} tokens" if self._token_count > 0 else ""
            )
            if self._last_think_t > 0 and (now - self._last_think_t) < 2.0:
                self._lbl_elapsed.setText(f"🤔 Reasoning... {elapsed:.1f}s{token_info}")
            else:
                self._lbl_elapsed.setText(f"🤖 {elapsed:.1f}s{token_info}")

    # ------------------------------------------------------------------
    # Slots / event handlers
    # ------------------------------------------------------------------

    def _on_send(self) -> None:
        if not _QT_AVAILABLE:
            return

        # "⏹ Stop" mode — cancel active generation
        if self._btn_send.text() == "⏹ Stop":
            self._on_stop_requested()
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

        image_b64, self._pending_image_b64 = self._pending_image_b64, None
        if image_b64:
            self._btn_screenshot.setText("📸")

        self.set_sending(True)
        self._begin_streaming_bubble()

        # self.parent() returns the internal QStackedWidget inside QTabWidget,
        # NOT MainWindow.  self.window() always returns the top-level QMainWindow
        # regardless of how many intermediate container widgets exist.
        parent = self.window()
        if parent and hasattr(parent, "on_llm_send"):
            parent.on_llm_send(  # type: ignore[union-attr]
                self._history[:],
                system=self._SYSTEM_PROMPT,
                brief=self._brief_mode,
                streaming=True,
                image_b64=image_b64,
            )
        else:
            # Defensive fallback: window not reachable yet (e.g. unit test env)
            self.set_sending(False)
            self._append_system("❌ Internal error: MainWindow not reachable.")

    def _on_attach_screenshot(self) -> None:
        """Show ROI overlay so user can select a region to capture."""
        if not _QT_AVAILABLE:
            return
        # Hide main window so the desktop is fully visible for ROI selection
        main_win = self.window()
        if main_win:
            main_win.hide()
        # Short delay to ensure window is fully gone before overlay appears
        QTimer.singleShot(150, self._show_roi_overlay)

    def _show_roi_overlay(self) -> None:
        """Create and display the ROI selection overlay."""
        self._roi_overlay = _RoiScreenshotOverlay()
        self._roi_overlay.roi_selected.connect(self._on_roi_selected)
        self._roi_overlay.cancelled.connect(self._on_roi_cancelled)

    def _on_roi_cancelled(self) -> None:
        """Restore main window when user cancels ROI selection."""
        main_win = self.window()
        if main_win:
            main_win.show()

    def _on_roi_selected(self, x: int, y: int, w: int, h: int) -> None:
        """Capture the selected region, resize + JPEG-compress, store as base64."""
        main_win = self.window()
        if main_win:
            main_win.show()
        try:
            import base64
            import io

            import mss
            from PIL import Image  # noqa: PLC0415

            with mss.mss() as sct:
                region = {"left": x, "top": y, "width": w, "height": h}
                raw = sct.grab(region)
                pil_img = Image.frombytes("RGB", raw.size, raw.rgb)

            # Resize to max 800px on longest side for fewer LLM tokens
            max_dim = 800
            if max(pil_img.size) > max_dim:
                ratio = max_dim / max(pil_img.size)
                new_w = max(1, int(pil_img.width * ratio))
                new_h = max(1, int(pil_img.height * ratio))
                pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)

            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG", quality=80)
            self._pending_image_b64 = base64.b64encode(buf.getvalue()).decode()
            self._btn_screenshot.setText("📸✓")
            self._append_system(
                f"📸 Region captured: {pil_img.width}×{pil_img.height}px "
                f"(JPEG q80, ~{len(buf.getvalue()) // 1024}KB)"
            )
        except Exception as exc:  # noqa: BLE001
            self._append_system(f"❌ Screenshot failed: {exc}")

    def _on_stop_requested(self) -> None:
        """Cancel active LLM generation and restore chat to pre-request state."""
        self._stop_requested = True
        # Remove partial AI bubble inserted by _begin_streaming_bubble()
        self._remove_partial_bubble()
        # Stop the worker (closes HTTP session immediately)
        if self._worker is not None:
            stop_fn = getattr(self._worker, "stop", None)
            if callable(stop_fn):
                try:
                    stop_fn()
                except Exception:  # noqa: BLE001
                    pass
        self._pending_prompt = None
        self.set_sending(False)
        self._append_system("⏹ Generation stopped — you can continue chatting.")

    def _remove_partial_bubble(self) -> None:
        """Truncate chat display back to the position before the current AI bubble."""
        if not _QT_AVAILABLE:
            return
        self._stop_flush_and_finalize()  # drain buffer first
        doc = self._chat_display.document()
        cursor = QTextCursor(doc)
        cursor.setPosition(self._bubble_start_pos)
        cursor.movePosition(
            QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor
        )
        cursor.removeSelectedText()
        self._chat_display.moveCursor(QTextCursor.MoveOperation.End)
        self._stream_cursor = None
        self._token_buf.clear()

    def _on_analyze(self) -> None:
        parent = self.window()
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
        self._has_warm_llm = True  # model is warmed up — next ETA shows ~10-30s
        self.set_sending(False)
        elapsed = time.perf_counter() - self._t0 if self._t0 > 0 else 0
        token_info = f" | {self._token_count} tokens" if self._token_count > 0 else ""
        self._lbl_elapsed.setText(f"✅ {elapsed:.1f}s{token_info}")
        # Detect empty response — typically caused by <think> block consuming
        # the entire token budget (max_output_tokens), leaving no answer tokens.
        if not full_text.strip():
            self._append_system(
                "\u26a0 No visible response generated. "
                "The model may have used all tokens for reasoning (<think> block). "
                "Try: 1) Turn OFF Brief mode for more tokens  "
                "2) Rephrase as a shorter question  "
                "3) Ask again (second request is faster after warm-up)"
            )
            self._process_pending_prompt()
            return
        if _QT_AVAILABLE:
            patch = self._extract_patch(full_text)
            self._btn_apply.setEnabled(patch is not None)
        self._process_pending_prompt()

    @pyqtSlot(str)
    def on_llm_error(self, error: str) -> None:
        if self._stop_requested:
            # User-initiated stop — suppress error bubble, just reset state
            self.set_sending(False)
            return
        # timeout / connection cancel 에러 구분
        is_timeout = (
            "timed out" in error.lower()
            or "600s" in error
            or "300s" in error
            or "120s" in error
        )
        if is_timeout:
            self._append_system(
                "⏱ Request timed out (600s limit). "
                "CPU-only mode: Gemma 4 26B local inference may be slow without a GPU. "
                "Solutions: 1) Install GPU (recommended) "
                "2) Ensure Brief mode is ON "
                "3) Check Ollama is running (start_agent.bat)"
            )
        else:
            self._append_bubble("assistant", f"❌ Error: {error}")
            self._append_system(
                "Tip: Check that Ollama is running (start_agent.bat) "
                "and LLM settings are correct in Tab 5 Config."
            )
        self.set_sending(False)
        self._process_pending_prompt()

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
