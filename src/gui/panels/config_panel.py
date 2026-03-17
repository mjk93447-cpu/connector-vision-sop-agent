"""
Tab 5 — Config Editor Panel (v3.0 — English UI + OCR Settings).

Displays config.json keys as editable controls (QDoubleSpinBox, QCheckBox, QLineEdit).
Safe-range validation via SAFE_NUMERIC_RANGES.
Writes config.proposed.json on save (never overwrites config.json directly).

New in v3.0:
  - All UI text in English for Indian line engineers
  - OCR section: backend selector, threshold slider, popup keywords editor
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    from PyQt6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDoubleSpinBox,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QSlider,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
    from PyQt6.QtCore import Qt

    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False
    QWidget = object  # type: ignore[assignment,misc]

try:
    from src.sop_advisor import SAFE_NUMERIC_RANGES
except ImportError:
    SAFE_NUMERIC_RANGES: Dict[str, Tuple[float, float]] = {}  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Editable config keys definition
# ---------------------------------------------------------------------------

_CONFIG_SECTIONS: Dict[str, list] = {
    "Vision (YOLO26x)": [
        (
            "vision.confidence_threshold",
            "Detection Confidence Threshold",
            "float",
            0.10,
            0.99,
        ),
    ],
    "Control Timing": [
        ("control.step_delay", "Step delay (seconds)", "float", 0.0, 10.0),
        ("control.move_duration", "Mouse move duration (seconds)", "float", 0.01, 5.0),
        ("control.click_pause", "Pause after click (seconds)", "float", 0.01, 5.0),
        ("control.drag_duration", "Drag duration (seconds)", "float", 0.01, 5.0),
        ("control.retry_delay", "Retry delay (seconds)", "float", 0.0, 10.0),
        ("control.retries", "Max retries per step", "int", 1, 10),
    ],
    "Pin Validation": [
        ("pin_count_min", "Minimum pin count", "int", 1, 200),
        ("pin_count_max", "Maximum pin count", "int", 1, 200),
    ],
    "LLM Settings": [
        ("llm.enabled", "LLM enabled", "bool", None, None),
        ("llm.allow_config_write", "Allow direct config write", "bool", None, None),
        ("llm.model", "Model name", "str", None, None),
    ],
}


class ConfigPanel(QWidget):  # type: ignore[misc]
    """Config Editor tab."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        config_path: Optional[Path] = None,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._config = config or {}
        self._config_path = config_path or Path("assets/config.json")
        self._widgets: Dict[str, Any] = {}
        self._setup_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_config(self, config: Dict[str, Any]) -> None:
        self._config = config
        self._populate_values()

    # ------------------------------------------------------------------
    # Private — UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        if not _QT_AVAILABLE:
            return

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        header = QLabel("⚙ Configuration Editor")
        header.setStyleSheet("font-size: 14px; font-weight: bold;")
        outer.addWidget(header)

        lbl_note = QLabel(
            "💡 Changes are saved to config.proposed.json — "
            "review and manually apply to config.json when ready."
        )
        lbl_note.setStyleSheet("color: #e65100; font-size: 11px;")
        lbl_note.setWordWrap(True)
        outer.addWidget(lbl_note)

        # Scrollable form area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setSpacing(12)

        for section_name, fields in _CONFIG_SECTIONS.items():
            group = QGroupBox(section_name)
            form = QFormLayout(group)
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

            for key, label, field_type, lo, hi in fields:
                widget = self._make_widget(key, field_type, lo, hi)
                self._widgets[key] = widget
                form.addRow(label + ":", widget)

            main_layout.addWidget(group)

        # OCR Section (additional, outside the scrollable form)
        ocr_grp = QGroupBox("OCR Settings (Button Text Detection)")
        ocr_layout = QFormLayout(ocr_grp)

        # Backend selector
        self._combo_ocr_backend = QComboBox()
        self._combo_ocr_backend.addItems(
            ["auto (WinRT → PaddleOCR)", "winrt", "paddleocr"]
        )
        self._combo_ocr_backend.setToolTip(
            "auto: Use WinRT on Windows 10 1803+ (no extra install), "
            "fall back to PaddleOCR.\n"
            "winrt: Force Windows built-in OCR.\n"
            "paddleocr: Force PaddleOCR (requires paddleocr package)."
        )
        ocr_layout.addRow("OCR Backend:", self._combo_ocr_backend)

        # Threshold slider
        thr_row = QHBoxLayout()
        self._slider_ocr_thr = QSlider(Qt.Orientation.Horizontal)
        self._slider_ocr_thr.setRange(50, 100)
        self._slider_ocr_thr.setValue(80)
        self._slider_ocr_thr.setTickInterval(5)
        self._slider_ocr_thr.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._lbl_ocr_thr = QLabel("0.80")
        self._lbl_ocr_thr.setFixedWidth(40)
        self._slider_ocr_thr.valueChanged.connect(
            lambda v: self._lbl_ocr_thr.setText(f"{v/100:.2f}")
        )
        thr_row.addWidget(self._slider_ocr_thr)
        thr_row.addWidget(self._lbl_ocr_thr)
        ocr_layout.addRow("Match Threshold (0.5-1.0):", thr_row)
        self._slider_ocr_thr.setToolTip(
            "Minimum fuzzy-match score for OCR button detection.\n"
            "Lower = more permissive (catches OCR errors but more false positives).\n"
            "Higher = stricter (safer, may miss buttons with OCR errors).\n"
            "Recommended: 0.75-0.85 for standard factory UI."
        )

        # Popup keywords editor
        ocr_layout.addRow(
            QLabel("Windows Popup Keywords (one per line):"),
        )
        self._txt_popup_keywords = QTextEdit()
        self._txt_popup_keywords.setMaximumHeight(120)
        self._txt_popup_keywords.setPlaceholderText(
            "Windows Update\nRestart now\nActivate Windows\nRun anyway\n..."
        )
        self._txt_popup_keywords.setToolTip(
            "Text patterns that trigger automatic popup dismissal.\n"
            "Add keywords for any Windows dialog that blocks SOP execution.\n"
            "One keyword per line."
        )
        ocr_layout.addRow(self._txt_popup_keywords)

        main_layout.addWidget(ocr_grp)
        main_layout.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll)

        # Buttons
        btn_row = QHBoxLayout()
        btn_reload = QPushButton("🔄 Reload from File")
        btn_reload.clicked.connect(self._populate_values)

        btn_save = QPushButton("💾 Save to config.proposed.json")
        btn_save.setStyleSheet(
            "background-color: #ff9800; color: white; font-weight: bold; padding: 8px 16px;"
        )
        btn_save.clicked.connect(self._on_save_proposed)

        btn_row.addWidget(btn_reload)
        btn_row.addStretch()
        btn_row.addWidget(btn_save)
        outer.addLayout(btn_row)

        self._populate_values()

    def _get_nested(self, key: str) -> Any:
        parts = key.split(".")
        cursor: Any = self._config
        for part in parts:
            if not isinstance(cursor, dict):
                return None
            cursor = cursor.get(part)
        return cursor

    def _populate_values(self) -> None:
        if not _QT_AVAILABLE:
            return
        for key, widget in self._widgets.items():
            val = self._get_nested(key)
            if val is None:
                continue
            try:
                if isinstance(widget, QDoubleSpinBox):
                    widget.setValue(float(val))
                elif isinstance(widget, QCheckBox):
                    widget.setChecked(bool(val))
                elif isinstance(widget, QLineEdit):
                    widget.setText(str(val))
            except Exception:  # noqa: BLE001
                pass

        # Populate OCR section from config
        ocr = self._config.get("ocr", {})
        if ocr:
            backend = ocr.get("backend", "auto")
            for i in range(self._combo_ocr_backend.count()):
                if backend in self._combo_ocr_backend.itemText(i):
                    self._combo_ocr_backend.setCurrentIndex(i)
                    break
            thr = int(float(ocr.get("threshold", 0.80)) * 100)
            self._slider_ocr_thr.setValue(thr)
            keywords = ocr.get("popup_keywords", [])
            if keywords:
                self._txt_popup_keywords.setText("\n".join(keywords))

    def _collect_patch(self) -> Dict[str, Any]:
        """Read all widget values and build a flat patch dict."""
        if not _QT_AVAILABLE:
            return {}
        patch: Dict[str, Any] = {}
        try:
            for key, widget in self._widgets.items():
                if isinstance(widget, QDoubleSpinBox):
                    patch[key] = widget.value()
                elif isinstance(widget, QCheckBox):
                    patch[key] = widget.isChecked()
                elif isinstance(widget, QLineEdit):
                    patch[key] = widget.text()
        except Exception:  # noqa: BLE001
            pass

        # Collect OCR section
        backend_text = self._combo_ocr_backend.currentText()
        backend_key = "auto"
        if "winrt" in backend_text and "auto" not in backend_text:
            backend_key = "winrt"
        elif "paddleocr" in backend_text and "auto" not in backend_text:
            backend_key = "paddleocr"
        thr = self._slider_ocr_thr.value() / 100.0
        keywords_raw = self._txt_popup_keywords.toPlainText()
        keywords = [k.strip() for k in keywords_raw.splitlines() if k.strip()]

        patch["ocr.backend"] = backend_key
        patch["ocr.threshold"] = thr
        patch["ocr.popup_keywords"] = keywords
        patch["ocr.enabled"] = True
        patch["ocr.fuzzy_match"] = True

        return patch

    def _on_save_proposed(self) -> None:
        if not _QT_AVAILABLE:
            return
        try:
            from src.sop_advisor import (
                apply_config_patch,
                write_proposed_config,
            )  # noqa: PLC0415

            patch = self._collect_patch()
            new_cfg, warnings = apply_config_patch(self._config, patch)
            proposed = write_proposed_config(self._config_path, new_cfg)
            msg = f"Saved: {proposed}"
            if warnings:
                msg += "\n\n⚠ Warnings:\n" + "\n".join(warnings)
            QMessageBox.information(self, "Saved", msg)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Save Error", str(exc))

    def _make_widget(self, key: str, field_type: str, lo: Any, hi: Any) -> Any:
        if not _QT_AVAILABLE:
            return None
        if field_type in ("float", "int"):
            spin = QDoubleSpinBox()
            spin.setDecimals(0 if field_type == "int" else 3)
            spin.setMinimum(float(lo) if lo is not None else 0.0)
            spin.setMaximum(float(hi) if hi is not None else 9999.0)
            spin.setSingleStep(1.0 if field_type == "int" else 0.05)
            return spin
        elif field_type == "bool":
            return QCheckBox()
        else:
            return QLineEdit()
