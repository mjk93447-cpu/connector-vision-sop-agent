"""
QThread workers for Connector Vision SOP Agent GUI.

Workers run blocking backend operations off the main UI thread so the
GUI stays responsive during SOP execution and LLM inference.

Workers
-------
SopWorker         — executes the full 12-step SOP in a background thread
LLMWorker         — sends a message to the LLM and emits the response (non-streaming)
LLMStreamWorker   — streaming LLM: emits token_ready per chunk + elapsed timer
AnalysisWorker    — runs LLM log analysis
TrainingWorker    — runs YOLO fine-tuning
"""

from __future__ import annotations

import logging as _logging
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
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
# _GuiLogHandler — routes WARNING+ log records from control_engine to GUI
# ---------------------------------------------------------------------------


class _GuiLogHandler(_logging.Handler):
    """Routes WARNING+ log records from control_engine to the GUI log signal."""

    def __init__(self, signal: Any) -> None:
        super().__init__()
        self._signal = signal

    def emit(self, record: _logging.LogRecord) -> None:
        try:
            self._signal.emit(self.format(record))
        except Exception:  # noqa: BLE001
            pass


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
        _handler = _GuiLogHandler(self.log_message)
        _handler.setLevel(_logging.WARNING)
        _ctrl_logger = _logging.getLogger("src.control_engine")
        _ctrl_logger.addHandler(_handler)
        try:
            self.log_message.emit("▶ Starting SOP execution...")

            steps = self._steps or self._executor.get_steps()
            total = len(steps)

            for idx, step in enumerate(steps):
                if self._abort:
                    self.log_message.emit("⏹ Aborted by user")
                    self.sop_finished.emit(False, "User abort")
                    return

                step_id = step.get("id", f"step_{idx}")
                step_name = step.get("name", step_id)

                self.step_started.emit(idx, step_name)
                self.log_message.emit(f"  [{idx + 1}/{total}] {step_name} ...")

                try:
                    ok, msg = self._executor.run_step(step)
                    self.step_finished.emit(idx, step_name, ok, msg)
                    status = "✓" if ok else "✗"
                    self.log_message.emit(
                        f"  [{idx + 1}/{total}] {step_name} {status} — {msg}"
                    )
                except Exception as exc:  # noqa: BLE001
                    err = f"Exception: {exc}"
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

            self.log_message.emit("✅ SOP complete!")
            self.sop_finished.emit(True, f"{total} steps complete")

        except Exception as exc:  # noqa: BLE001
            tb = traceback.format_exc()
            self.log_message.emit(f"❌ SOP error:\n{tb}")
            self.sop_finished.emit(False, str(exc))
        finally:
            _ctrl_logger.removeHandler(_handler)


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
# LLMStreamWorker — streaming token-by-token (ChatGPT-style)
# ---------------------------------------------------------------------------


class LLMStreamWorker(QThread):  # type: ignore[misc]
    """Streaming LLM worker — emits each token as it arrives.

    Signals
    -------
    token_ready(token_str)       — partial visible answer token
    think_token_ready(token_str) — reasoning token inside <think>…</think>
    elapsed_tick(elapsed_sec)    — progress tick every 0.5s
    response_done(full_text)     — complete response assembled
    error_occurred(error_text)   — exception during streaming
    """

    token_ready: Any = pyqtSignal(str)
    think_token_ready: Any = pyqtSignal(str)
    elapsed_tick: Any = pyqtSignal(float)
    response_done: Any = pyqtSignal(str)
    error_occurred: Any = pyqtSignal(str)

    def __init__(
        self,
        llm: Any,
        system_prompt: str,
        history: List[Dict[str, str]],
        brief: bool = False,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._llm = llm
        self._system = system_prompt
        self._history = history
        self._brief = brief
        self._t0: float = 0.0
        self._running = True

    def stop(self) -> None:
        """Request cancellation — closes the underlying HTTP session immediately."""
        self._running = False
        # Cancel in-flight HTTP request via session.close()
        cancel = getattr(self._llm, "cancel", None)
        if callable(cancel):
            try:
                cancel()
            except Exception:  # noqa: BLE001
                pass

    # Hard cutoff for streaming LLM requests (seconds).
    # concurrent.futures.future.result(timeout=...) guarantees the UI thread
    # is unblocked after this duration even if iter_lines() is still blocking.
    # 300s: SmolLM3-3B CPU cold-start ~30-90s 첫 토큰 + 생성 완료 버퍼
    _STREAM_TIMEOUT_SECS: int = 300

    def run(self) -> None:
        """Thread entry point — streams tokens and emits signals.

        Uses concurrent.futures so the 300s wall-clock timeout is guaranteed:
        future.result(timeout=300) raises FuturesTimeoutError regardless of
        whether the underlying requests.iter_lines() is still blocked.
        The background executor thread continues until Ollama finishes or the
        session is closed by self._llm.cancel().
        """
        self._t0 = time.perf_counter()
        self._running = True

        def _on_token(chunk: str) -> None:
            if not self._running:
                return
            self.token_ready.emit(chunk)
            self.elapsed_tick.emit(time.perf_counter() - self._t0)

        def _on_think_token(chunk: str) -> None:
            if not self._running:
                return
            self.think_token_ready.emit(chunk)
            self.elapsed_tick.emit(time.perf_counter() - self._t0)

        def _on_done(full_text: str, elapsed: float) -> None:
            # Guard: don't emit if already timed out / cancelled
            if self._running:
                self.response_done.emit(full_text)

        def _stream_fn() -> str:
            return self._llm.stream_chat(  # type: ignore[no-any-return]
                system=self._system,
                history=self._history,
                on_token=_on_token,
                on_done=_on_done,
                brief=self._brief,
                on_think_token=_on_think_token,
            )

        # executor.shutdown(wait=False): background thread is not joined —
        # the UI thread is freed immediately on timeout without waiting for
        # Ollama to finish generating.
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(_stream_fn)
        executor.shutdown(wait=False)

        try:
            future.result(timeout=self._STREAM_TIMEOUT_SECS)
        except FuturesTimeoutError:
            # UI unblocked after 300s — suppress any late signals from the
            # background thread, then try to close the HTTP session.
            self._running = False
            cancel = getattr(self._llm, "cancel", None)
            if callable(cancel):
                try:
                    cancel()
                except Exception:  # noqa: BLE001
                    pass
            self.error_occurred.emit(
                f"LLM request timed out ({self._STREAM_TIMEOUT_SECS}s limit reached)"
            )
        except Exception as exc:  # noqa: BLE001
            err_msg = str(exc)
            # session.close() (user Stop) 에 의한 종료인지 판별
            is_cancel = any(
                k in err_msg.lower()
                for k in ("cancel", "connection aborted", "connection reset", "closed")
            )
            if is_cancel and not self._running:
                return  # 사용자 ⏹ Stop — 에러 메시지 불필요
            elif is_cancel:
                self.error_occurred.emit(
                    f"LLM request timed out ({self._STREAM_TIMEOUT_SECS}s limit reached)"
                )
            else:
                self.error_occurred.emit(err_msg)


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


# ---------------------------------------------------------------------------
# TrainingWorker
# ---------------------------------------------------------------------------


class TrainingWorker(QThread):  # type: ignore[misc]
    """Run YOLO fine-tuning in a background thread.

    Signals
    -------
    progress(epoch, total)     — epoch progress update
    finished_ok(weights_path)  — training completed; path to saved .pt
    error_occurred(error_text) — training failed
    """

    progress: Any = pyqtSignal(int, int)
    finished_ok: Any = pyqtSignal(str)
    log_ready: Any = pyqtSignal(str)  # path to training.log after completion
    error_occurred: Any = pyqtSignal(str)

    def __init__(
        self,
        dataset_yaml: str,
        epochs: int = 10,
        batch: int = 4,
        base_model: Optional[str] = None,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._dataset_yaml = dataset_yaml
        self._epochs = epochs
        self._batch = batch
        self._base_model = base_model

    def run(self) -> None:
        """Thread entry point."""
        try:
            from src.training.training_manager import TrainingManager  # noqa: PLC0415

            tm = TrainingManager()

            def _progress_cb(epoch: int, total: int) -> None:
                self.progress.emit(epoch, total)

            weights = tm.train(
                dataset_yaml=self._dataset_yaml,
                epochs=self._epochs,
                batch=self._batch,
                base_model=self._base_model,
                progress_cb=_progress_cb,
            )
            self.finished_ok.emit(str(weights))
            if tm.last_training_log is not None:
                self.log_ready.emit(str(tm.last_training_log))
        except Exception as exc:  # noqa: BLE001
            tb = traceback.format_exc()
            self.error_occurred.emit(f"{exc}\n{tb}")
