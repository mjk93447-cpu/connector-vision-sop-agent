"""tests/unit/test_config_panel.py — ConfigPanel 툴팁 회귀 테스트."""

from __future__ import annotations


class TestConfigPanelTooltips:
    def test_all_config_keys_have_tooltip_entries(self) -> None:
        """_CONFIG_SECTIONS 의 모든 키는 _CONFIG_TOOLTIPS 에 존재해야 한다."""
        from src.gui.panels.config_panel import _CONFIG_SECTIONS, _CONFIG_TOOLTIPS

        for _section, fields in _CONFIG_SECTIONS.items():
            for key, *_ in fields:
                assert (
                    key in _CONFIG_TOOLTIPS
                ), f"Missing tooltip for config key {key!r}"

    def test_tooltips_are_non_empty(self) -> None:
        """모든 툴팁 값은 비어 있으면 안 된다."""
        from src.gui.panels.config_panel import _CONFIG_TOOLTIPS

        for key, tip in _CONFIG_TOOLTIPS.items():
            assert tip.strip(), f"Empty tooltip for {key!r}"

    def test_config_sections_key_count(self) -> None:
        """_CONFIG_SECTIONS 총 키 개수 회귀 가드 — 12개."""
        from src.gui.panels.config_panel import _CONFIG_SECTIONS

        keys = [key for fields in _CONFIG_SECTIONS.values() for key, *_ in fields]
        assert len(keys) == 12, f"Expected 12 config keys, got {len(keys)}: {keys}"
