"""
Tab 5 — Config Editor Panel.

Displays config.json keys as editable controls (QDoubleSpinBox, QCheckBox, QLineEdit).
Safe-range validation via SAFE_NUMERIC_RANGES.
Writes config.proposed.json on save (never overwrites config.json directly).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    from PyQt6.QtWidgets import (
        QDoubleSpinBox,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QVBoxLayout,
        QWidget,
    )

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
    "비전 (vision)": [
        ("vision.confidence_threshold", "신뢰도 임계값", "float", 0.10, 0.99),
    ],
    "제어 타이밍 (control)": [
        ("control.step_delay", "단계 간 지연 (초)", "float", 0.0, 10.0),
        ("control.move_duration", "마우스 이동 시간 (초)", "float", 0.01, 5.0),
        ("control.click_pause", "클릭 후 대기 (초)", "float", 0.01, 5.0),
        ("control.drag_duration", "드래그 시간 (초)", "float", 0.01, 5.0),
        ("control.retry_delay", "재시도 대기 (초)", "float", 0.0, 10.0),
        ("control.retries", "최대 재시도 횟수", "int", 1, 10),
    ],
    "핀 검증 (pin)": [
        ("pin_count_min", "최소 핀 개수", "int", 1, 200),
        ("pin_count_max", "최대 핀 개수", "int", 1, 200),
    ],
    "LLM 설정 (llm)": [
        ("llm.enabled", "LLM 활성화", "bool", None, None),
        ("llm.allow_config_write", "직접 수정 허용", "bool", None, None),
        ("llm.model", "모델 이름", "str", None, None),
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

        header = QLabel("⚙ Config 편집기")
        header.setStyleSheet("font-size: 14px; font-weight: bold;")
        outer.addWidget(header)

        lbl_note = QLabel(
            "💡 변경사항은 config.proposed.json으로 저장됩니다. "
            "엔지니어 검토 후 수동으로 config.json에 반영하세요."
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

        main_layout.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll)

        # Buttons
        btn_row = QHBoxLayout()
        btn_reload = QPushButton("🔄 다시 불러오기")
        btn_reload.clicked.connect(self._populate_values)

        btn_save = QPushButton("💾 config.proposed.json 저장")
        btn_save.setStyleSheet(
            "background-color: #ff9800; color: white; font-weight: bold; padding: 8px 16px;"
        )
        btn_save.clicked.connect(self._on_save_proposed)

        btn_row.addWidget(btn_reload)
        btn_row.addStretch()
        btn_row.addWidget(btn_save)
        outer.addLayout(btn_row)

        self._populate_values()

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
            from PyQt6.QtWidgets import QCheckBox

            return QCheckBox()
        else:
            edit = QLineEdit()
            return edit

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
                from PyQt6.QtWidgets import QCheckBox, QDoubleSpinBox, QLineEdit

                if isinstance(widget, QDoubleSpinBox):
                    widget.setValue(float(val))
                elif isinstance(widget, QCheckBox):
                    widget.setChecked(bool(val))
                elif isinstance(widget, QLineEdit):
                    widget.setText(str(val))
            except Exception:  # noqa: BLE001
                pass

    def _collect_patch(self) -> Dict[str, Any]:
        """Read all widget values and build a flat patch dict."""
        if not _QT_AVAILABLE:
            return {}
        patch: Dict[str, Any] = {}
        try:
            from PyQt6.QtWidgets import QCheckBox, QDoubleSpinBox, QLineEdit

            for key, widget in self._widgets.items():
                if isinstance(widget, QDoubleSpinBox):
                    patch[key] = widget.value()
                elif isinstance(widget, QCheckBox):
                    patch[key] = widget.isChecked()
                elif isinstance(widget, QLineEdit):
                    patch[key] = widget.text()
        except Exception:  # noqa: BLE001
            pass
        return patch

    def _on_save_proposed(self) -> None:
        if not _QT_AVAILABLE:
            return
        try:
            from src.sop_advisor import apply_config_patch, write_proposed_config

            patch = self._collect_patch()
            new_cfg, warnings = apply_config_patch(self._config, patch)
            proposed = write_proposed_config(self._config_path, new_cfg)
            msg = f"저장 완료: {proposed}"
            if warnings:
                msg += "\n\n⚠ 경고:\n" + "\n".join(warnings)
            QMessageBox.information(self, "저장 완료", msg)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "저장 오류", str(exc))
