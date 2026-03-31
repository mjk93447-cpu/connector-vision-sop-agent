"""tests/unit/test_epoch_chart.py — EpochChartWidget 단위 테스트 (헤드리스)."""

from __future__ import annotations

import pytest

# PyQt6 없으면 건너뜀
pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication  # noqa: E402

import sys  # noqa: E402

_app = QApplication.instance() or QApplication(sys.argv)


class TestEpochChartWidget:
    """EpochChartWidget add_point / reset / negative map50 무시 검증."""

    def _make_widget(self):
        from src.gui.panels.training_panel import EpochChartWidget

        return EpochChartWidget()

    def test_add_point_stores_positive_map50(self) -> None:
        """add_point() — map50 >= 0 이면 _points에 추가된다."""
        w = self._make_widget()
        w.add_point(1, 0.5)
        w.add_point(2, 0.7)
        assert len(w._points) == 2
        assert w._points[0] == (1, 0.5)
        assert w._points[1] == (2, 0.7)

    def test_negative_map50_is_ignored(self) -> None:
        """add_point() — map50 < 0 이면 포인트 추가 안 됨."""
        w = self._make_widget()
        w.add_point(1, -1.0)
        assert len(w._points) == 0

    def test_reset_clears_points(self) -> None:
        """reset() 호출 후 _points 비어야 한다."""
        w = self._make_widget()
        w.add_point(1, 0.3)
        w.add_point(2, 0.4)
        w.reset()
        assert len(w._points) == 0
