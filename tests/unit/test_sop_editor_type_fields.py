"""
SOP Editor type-specific field 단위 테스트 (v3.10.3).

검증 범위:
  1. _STEP_TYPES — type_text / press_key / wait_ms / auth_sequence 포함 확인
  2. _StepEditDialog — type-specific 위젯 존재 확인 (소스 검사)
  3. _on_type_changed — 메서드 존재 및 소스 확인
  4. get_step() — type-specific 필드 저장 로직 확인
"""

from __future__ import annotations

import importlib
import inspect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_module():
    return importlib.import_module("src.gui.panels.sop_editor_panel")


# ---------------------------------------------------------------------------
# 1. _STEP_TYPES 포함 검증
# ---------------------------------------------------------------------------


class TestStepTypes:
    def test_type_text_in_step_types(self) -> None:
        mod = _load_module()
        assert "type_text" in mod._STEP_TYPES, "type_text must be in _STEP_TYPES"

    def test_press_key_in_step_types(self) -> None:
        mod = _load_module()
        assert "press_key" in mod._STEP_TYPES, "press_key must be in _STEP_TYPES"

    def test_wait_ms_in_step_types(self) -> None:
        mod = _load_module()
        assert "wait_ms" in mod._STEP_TYPES, "wait_ms must be in _STEP_TYPES"

    def test_auth_sequence_in_step_types(self) -> None:
        mod = _load_module()
        assert (
            "auth_sequence" in mod._STEP_TYPES
        ), "auth_sequence must be in _STEP_TYPES"

    def test_click_still_in_step_types(self) -> None:
        mod = _load_module()
        assert "click" in mod._STEP_TYPES

    def test_drag_still_in_step_types(self) -> None:
        mod = _load_module()
        assert "drag" in mod._STEP_TYPES


# ---------------------------------------------------------------------------
# 2. _StepEditDialog — type-specific 위젯 소스 검증
# ---------------------------------------------------------------------------


class TestStepEditDialogTypeWidgets:
    def test_type_text_widget_in_setup_ui(self) -> None:
        mod = _load_module()
        src = inspect.getsource(mod._StepEditDialog._setup_ui)
        assert (
            "_type_text_widget" in src
        ), "_type_text_widget must be created in _setup_ui"

    def test_text_edit_in_setup_ui(self) -> None:
        mod = _load_module()
        src = inspect.getsource(mod._StepEditDialog._setup_ui)
        assert "_text_edit" in src, "_text_edit (QLineEdit) must be in _setup_ui"

    def test_clear_first_chk_in_setup_ui(self) -> None:
        mod = _load_module()
        src = inspect.getsource(mod._StepEditDialog._setup_ui)
        assert (
            "_clear_first_chk" in src
        ), "_clear_first_chk (QCheckBox) must be in _setup_ui"

    def test_press_key_widget_in_setup_ui(self) -> None:
        mod = _load_module()
        src = inspect.getsource(mod._StepEditDialog._setup_ui)
        assert "_press_key_widget" in src, "_press_key_widget must be in _setup_ui"

    def test_key_edit_in_setup_ui(self) -> None:
        mod = _load_module()
        src = inspect.getsource(mod._StepEditDialog._setup_ui)
        assert (
            "_key_edit" in src
        ), "_key_edit (QLineEdit for key name) must be in _setup_ui"

    def test_wait_ms_widget_in_setup_ui(self) -> None:
        mod = _load_module()
        src = inspect.getsource(mod._StepEditDialog._setup_ui)
        assert "_wait_ms_widget" in src, "_wait_ms_widget must be in _setup_ui"

    def test_ms_spin_in_setup_ui(self) -> None:
        mod = _load_module()
        src = inspect.getsource(mod._StepEditDialog._setup_ui)
        assert "_ms_spin" in src, "_ms_spin (QSpinBox) must be in _setup_ui"

    def test_on_type_changed_connected_in_setup_ui(self) -> None:
        mod = _load_module()
        src = inspect.getsource(mod._StepEditDialog._setup_ui)
        assert (
            "_on_type_changed" in src
        ), "_on_type_changed must be connected in _setup_ui"

    def test_on_type_changed_called_for_init(self) -> None:
        """_setup_ui() must call _on_type_changed() to set initial visibility."""
        mod = _load_module()
        src = inspect.getsource(mod._StepEditDialog._setup_ui)
        # Must appear as a call (not just a connect)
        assert (
            src.count("_on_type_changed") >= 2
        ), "_on_type_changed must be both connected AND called in _setup_ui"


# ---------------------------------------------------------------------------
# 3. _on_type_changed 메서드 검증
# ---------------------------------------------------------------------------


class TestOnTypeChangedMethod:
    def test_method_exists(self) -> None:
        mod = _load_module()
        assert hasattr(
            mod._StepEditDialog, "_on_type_changed"
        ), "_on_type_changed method must exist on _StepEditDialog"

    def test_shows_type_text_widget(self) -> None:
        mod = _load_module()
        src = inspect.getsource(mod._StepEditDialog._on_type_changed)
        assert "_type_text_widget" in src

    def test_shows_press_key_widget(self) -> None:
        mod = _load_module()
        src = inspect.getsource(mod._StepEditDialog._on_type_changed)
        assert "_press_key_widget" in src

    def test_shows_wait_ms_widget(self) -> None:
        mod = _load_module()
        src = inspect.getsource(mod._StepEditDialog._on_type_changed)
        assert "_wait_ms_widget" in src

    def test_calls_adjust_size(self) -> None:
        mod = _load_module()
        src = inspect.getsource(mod._StepEditDialog._on_type_changed)
        assert (
            "adjustSize" in src
        ), "_on_type_changed must call adjustSize() to resize dialog"

    def test_guards_qt_available(self) -> None:
        mod = _load_module()
        src = inspect.getsource(mod._StepEditDialog._on_type_changed)
        assert "_QT_AVAILABLE" in src, "_on_type_changed must check _QT_AVAILABLE"


# ---------------------------------------------------------------------------
# 4. get_step() — type-specific 필드 저장 로직 검증
# ---------------------------------------------------------------------------


class TestGetStepTypeSpecificFields:
    def test_get_step_handles_type_text(self) -> None:
        mod = _load_module()
        src = inspect.getsource(mod._StepEditDialog.get_step)
        assert "type_text" in src, "get_step must handle type_text"

    def test_get_step_saves_text_field(self) -> None:
        mod = _load_module()
        src = inspect.getsource(mod._StepEditDialog.get_step)
        assert (
            '"text"' in src or '"text"' in src or "'text'" in src
        ), "get_step must save 'text' field for type_text steps"

    def test_get_step_saves_clear_first_field(self) -> None:
        mod = _load_module()
        src = inspect.getsource(mod._StepEditDialog.get_step)
        assert (
            "clear_first" in src
        ), "get_step must save clear_first for type_text steps"

    def test_get_step_handles_press_key(self) -> None:
        mod = _load_module()
        src = inspect.getsource(mod._StepEditDialog.get_step)
        assert "press_key" in src, "get_step must handle press_key"

    def test_get_step_saves_key_field(self) -> None:
        mod = _load_module()
        src = inspect.getsource(mod._StepEditDialog.get_step)
        assert (
            '"key"' in src or "'key'" in src
        ), "get_step must save 'key' field for press_key steps"

    def test_get_step_handles_wait_ms(self) -> None:
        mod = _load_module()
        src = inspect.getsource(mod._StepEditDialog.get_step)
        assert "wait_ms" in src, "get_step must handle wait_ms"

    def test_get_step_saves_ms_field(self) -> None:
        mod = _load_module()
        src = inspect.getsource(mod._StepEditDialog.get_step)
        assert (
            '"ms"' in src or "'ms'" in src
        ), "get_step must save 'ms' field for wait_ms steps"

    def test_get_step_cleans_irrelevant_fields_for_type_text(self) -> None:
        """type_text step should not carry key or ms fields."""
        mod = _load_module()
        src = inspect.getsource(mod._StepEditDialog.get_step)
        # After type_text block, key and ms must be popped
        assert (
            src.index("type_text") < src.index('"key"') or "pop" in src
        ), "get_step must remove incompatible fields (key, ms) for type_text"

    def test_get_step_reads_text_from_text_edit(self) -> None:
        mod = _load_module()
        src = inspect.getsource(mod._StepEditDialog.get_step)
        assert "_text_edit" in src, "get_step must read from self._text_edit"

    def test_get_step_reads_key_from_key_edit(self) -> None:
        mod = _load_module()
        src = inspect.getsource(mod._StepEditDialog.get_step)
        assert "_key_edit" in src, "get_step must read from self._key_edit"

    def test_get_step_reads_ms_from_ms_spin(self) -> None:
        mod = _load_module()
        src = inspect.getsource(mod._StepEditDialog.get_step)
        assert "_ms_spin" in src, "get_step must read from self._ms_spin"
