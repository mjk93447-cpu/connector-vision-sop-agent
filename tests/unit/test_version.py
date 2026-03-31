"""tests/unit/test_version.py — Central version module (v4.1.1) unit tests.

Tests:
  TestVersionConstants       — APP_VERSION semver, APP_NAME, FULL_TITLE
  TestBumpLogic              — _bump() patch/minor/major
  TestMainWindowImportsVersion — main_window._APP_VERSION == APP_VERSION
"""

from __future__ import annotations

import re


class TestVersionConstants:
    def test_version_is_semver_format(self) -> None:
        """APP_VERSION must follow strict X.Y.Z semver."""
        from src.version import APP_VERSION

        assert re.fullmatch(
            r"\d+\.\d+\.\d+", APP_VERSION
        ), f"APP_VERSION {APP_VERSION!r} is not semver X.Y.Z"

    def test_app_name_not_empty(self) -> None:
        from src.version import APP_NAME

        assert (
            isinstance(APP_NAME, str) and APP_NAME.strip()
        ), "APP_NAME must be a non-empty string"

    def test_full_title_contains_version(self) -> None:
        from src.version import APP_VERSION, FULL_TITLE

        assert (
            APP_VERSION in FULL_TITLE
        ), f"FULL_TITLE {FULL_TITLE!r} must contain APP_VERSION {APP_VERSION!r}"


class TestBumpLogic:
    """Tests for _bump() helper — filesystem-safe (no file I/O)."""

    def test_bump_patch(self) -> None:
        from src.version import _bump

        assert _bump("4.1.0", "patch") == "4.1.1"

    def test_bump_minor(self) -> None:
        from src.version import _bump

        assert _bump("4.1.1", "minor") == "4.2.0"

    def test_bump_major(self) -> None:
        from src.version import _bump

        assert _bump("4.2.0", "major") == "5.0.0"


class TestMainWindowImportsVersion:
    def test_main_window_imports_version(self) -> None:
        """_APP_VERSION in main_window must equal APP_VERSION from version.py.

        Imports the module without instantiating Qt objects — works headless.
        """
        import src.gui.main_window as mw

        from src.version import APP_VERSION

        assert mw._APP_VERSION == APP_VERSION, (
            f"main_window._APP_VERSION {mw._APP_VERSION!r} != "
            f"APP_VERSION {APP_VERSION!r}"
        )
