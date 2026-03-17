"""
QThread workers for Connector Vision SOP Agent GUI.

Workers run blocking backend operations off the main UI thread so the
GUI stays responsive during SOP execution and LLM inference.

Workers
-------
SopWorker   — executes the full 12-step SOP in a background thread
LLMWorker   — sends a message to the LLM and emits the response
"""

from __future__ import annotations

import traceback
from typing import Any, Dict, List, Optional

try:
    from PyQt6.QtCore import QThread, pyqtSignal
except ImportError:  # pragma: no cover — GUI not required in CI
    QThread = object  # type: ignore[assignment,misc]

    class _FakeSig:  # type: ignore[no-redef]
        def __init__(self, *a: Any) -> None:
            pass

        def emit(self, *a: Any) -> None:
            pass

        def connect(self, *a: Any) -> None:
            pass

    pyqtSignal = _FakeSig  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# SopWorker
# ---------------------------------------------------------------------------


class SopWorker(QThread):  # type: ignore[misc]
    """Execute the SOP in a background thread.

    Signals
    -------
    step_started(step_index, step_name)
    step_finished(step_index, step_name, success, message)
    sop_finished(success, summary)
    log_message(text)
    screenshot_ready(numpy_ndarray)  — BGR image captured after each step
    """

    step_started: Any = pyqtSignal(int, str)
    step_finished: Any = pyqtSignal(int, str, bool, str)
    sop_finished: Any = pyqtSignal(bool, str)
    log_message: Any = pyqtSignal(str)
    screenshot_ready: Any = pyqtSignal(object)  # emits numpy ndarray (BGR)

    def __init__(
        self,
        sop_executor: Any,
        steps: Optional[List[Dict[str, Any]]] = None,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._executor = sop_executor
        self._steps = steps  # optional override (enabled steps only)
        self._abort = False

    def abort(self) -> None:
        """Request graceful abort."""
        self._abort = True

    def run(self) -> None:  # noqa: C901
        """Thread entry point — called by QThread.start()."""
        try:
            self.log_message.emit("▶ SOP 실행 시작...")

            steps = self._steps or self._executor.get_steps()
            total = len(steps)

            for idx, step in enumerate(steps):
                if self._abort:
                    self.log_message.emit("⏹ 사용자에 의해 중단됨")
                    self.sop_finished.emit(False, "사용자 중단")
                    return

                step_id = step.get("id", f"step_{idx}")
                step_name = step.get("name", step_id)

                self.step_started.emit(idx, step_name)
                self.log_message.emit(f"  [{idx + 1}/{total}] {step_name} …")

                try:
                    ok, msg = self._executor.run_step(step)
                    self.step_finished.emit(idx, step_name, ok, msg)
                    status = "✓" if ok else "✗"
                    self.log_message.emit(
                        f"  [{idx + 1}/{total}] {step_name} {status} — {msg}"
                    )
                except Exception as exc:  # noqa: BLE001
                    err = f"예외 발생: {exc}"
                    self.step_finished.emit(idx, step_name, False, err)
                    self.log_message.emit(
                        f"  [{idx + 1}/{total}] {step_name} ✗ — {err}"
                    )

                # Capture screenshot for Vision Panel (best-effort; silent fail)
                try:
                    vision = getattr(self._executor, "vision", None)
                    if vision is not None:
                        img = vision.capture_screen()
                        self.screenshot_ready.emit(img)
                except Exception:  # noqa: BLE001
                    pass  # headless / no display — skip silently

            self.log_message.emit("✅ SOP 완료!")
            self.sop_finished.emit(True, f"{total}단계 완료")

        except Exception as exc:  # noqa: BLE001
            tb = traceback.format_exc()
            self.log_message.emit(f"❌ SOP 오류:\n{tb}")
            self.sop_finished.emit(False, str(exc))


# ---------------------------------------------------------------------------
# LLMWorker
# ---------------------------------------------------------------------------


class LLMWorker(QThread):  # type: ignore[misc]
    """Send a message to the offline LLM and emit the response.

    Signals
    -------
    response_ready(text)
    error_occurred(error_text)
    """

    response_ready: Any = pyqtSignal(str)
    error_occurred: Any = pyqtSignal(str)

    def __init__(
        self,
        llm: Any,
        system_prompt: str,
        history: List[Dict[str, str]],
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._llm = llm
        self._system = system_prompt
        self._history = history

    def run(self) -> None:
        """Thread entry point."""
        try:
            reply = self._llm.chat(system=self._system, history=self._history)
            self.response_ready.emit(reply)
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(str(exc))


# ---------------------------------------------------------------------------
# AnalysisWorker
# ---------------------------------------------------------------------------


class AnalysisWorker(QThread):  # type: ignore[misc]
    """Run LLM log analysis in a background thread.

    Signals
    -------
    analysis_ready(result_dict)
    error_occurred(error_text)
    """

    analysis_ready: Any = pyqtSignal(object)
    error_occurred: Any = pyqtSignal(str)

    def __init__(
        self,
        llm: Any,
        payload: Dict[str, Any],
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._llm = llm
        self._payload = payload

    def run(self) -> None:
        """Thread entry point."""
        try:
            result = self._llm.analyze_logs(self._payload)
            self.analysis_ready.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(str(exc))
