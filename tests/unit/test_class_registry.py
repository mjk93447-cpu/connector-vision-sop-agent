from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_registry_at(tmp_path: Path, entries: list) -> Path:
    """Write a class_registry.json into tmp_path and return the file path."""
    data = {"version": "1.0", "classes": entries}
    p = tmp_path / "assets" / "class_registry.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _patch_registry_path(monkeypatch, path: Path):
    """Patch _get_registry_path inside class_registry to return *path*."""
    import src.class_registry as cr

    monkeypatch.setattr(cr, "_get_registry_path", lambda: path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


_FULL_REGISTRY_ENTRIES = [
    {"name": "login_button", "type": "TEXT"},
    {"name": "recipe_button", "type": "TEXT"},
    {"name": "register_button", "type": "TEXT"},
    {"name": "open_icon", "type": "TEXT"},
    {"name": "image_source", "type": "TEXT"},
    {"name": "mold_left_label", "type": "NON_TEXT"},
    {"name": "mold_right_label", "type": "NON_TEXT"},
    {"name": "pin_cluster", "type": "NON_TEXT"},
    {"name": "apply_button", "type": "TEXT"},
    {"name": "save_button", "type": "TEXT"},
    {"name": "axis_mark", "type": "TEXT"},
    {"name": "connector_pin", "type": "NON_TEXT"},
]


class TestLoadFromJson:
    def test_load_from_json(self, tmp_path, monkeypatch):
        """Load from actual-style class_registry.json — verify 12 classes."""
        registry_path = _make_registry_at(tmp_path, _FULL_REGISTRY_ENTRIES)
        _patch_registry_path(monkeypatch, registry_path)
        from src.class_registry import ClassRegistry

        registry = ClassRegistry.load()

        assert len(registry.all_classes()) == 12

    def test_class_names_present(self, tmp_path, monkeypatch):
        """All 12 expected names should be present."""
        registry_path = _make_registry_at(tmp_path, _FULL_REGISTRY_ENTRIES)
        _patch_registry_path(monkeypatch, registry_path)
        from src.class_registry import ClassRegistry

        registry = ClassRegistry.load()

        names = registry.class_names()
        expected = [
            "login_button",
            "recipe_button",
            "register_button",
            "open_icon",
            "image_source",
            "mold_left_label",
            "mold_right_label",
            "pin_cluster",
            "apply_button",
            "save_button",
            "axis_mark",
            "connector_pin",
        ]
        for name in expected:
            assert name in names, f"{name!r} missing from loaded registry"


class TestLoadMissingFile:
    def test_load_missing_file_creates_default(self, tmp_path, monkeypatch):
        """When JSON is absent auto-create from DEFAULT_TARGET_LABELS."""
        missing = tmp_path / "assets" / "class_registry.json"
        # Do NOT create the file
        _patch_registry_path(monkeypatch, missing)

        from src.class_registry import ClassRegistry, _DEFAULT_TARGET_LABELS

        registry = ClassRegistry.load()

        assert registry.class_names() == _DEFAULT_TARGET_LABELS
        # File should have been auto-saved
        assert missing.exists()

    def test_load_missing_file_non_text_defaults(self, tmp_path, monkeypatch):
        """Auto-created registry assigns NON_TEXT to the 4 known non-text labels."""
        missing = tmp_path / "assets" / "class_registry.json"
        _patch_registry_path(monkeypatch, missing)

        from src.class_registry import ClassRegistry, _NON_TEXT_DEFAULTS

        registry = ClassRegistry.load()

        for name in _NON_TEXT_DEFAULTS:
            assert registry.is_non_text(name), f"{name!r} should be NON_TEXT"


class TestIsNonText:
    @pytest.fixture()
    def registry(self, tmp_path, monkeypatch):
        path = _make_registry_at(
            tmp_path,
            [
                {"name": "login_button", "type": "TEXT"},
                {"name": "mold_left_label", "type": "NON_TEXT"},
                {"name": "connector_pin", "type": "NON_TEXT"},
                {"name": "save_button", "type": "TEXT"},
            ],
        )
        _patch_registry_path(monkeypatch, path)
        from src.class_registry import ClassRegistry

        return ClassRegistry.load()

    def test_is_non_text_for_non_text_class(self, registry):
        assert registry.is_non_text("mold_left_label") is True

    def test_is_non_text_for_text_class(self, registry):
        assert registry.is_non_text("login_button") is False

    def test_is_non_text_unknown_class(self, registry):
        assert registry.is_non_text("unknown_class") is False


class TestGetType:
    @pytest.fixture()
    def registry(self, tmp_path, monkeypatch):
        path = _make_registry_at(
            tmp_path,
            [
                {"name": "connector_pin", "type": "NON_TEXT"},
                {"name": "save_button", "type": "TEXT"},
            ],
        )
        _patch_registry_path(monkeypatch, path)
        from src.class_registry import ClassRegistry

        return ClassRegistry.load()

    def test_get_type_non_text(self, registry):
        assert registry.get_type("connector_pin") == "NON_TEXT"

    def test_get_type_text(self, registry):
        assert registry.get_type("save_button") == "TEXT"

    def test_get_type_missing(self, registry):
        assert registry.get_type("unknown") is None


class TestAddClass:
    @pytest.fixture()
    def registry(self, tmp_path, monkeypatch):
        path = _make_registry_at(
            tmp_path,
            [{"name": "login_button", "type": "TEXT"}],
        )
        _patch_registry_path(monkeypatch, path)
        from src.class_registry import ClassRegistry

        return ClassRegistry.load()

    def test_add_class(self, registry):
        registry.add_class("new_widget", "TEXT")
        names = registry.class_names()
        assert "new_widget" in names

    def test_add_class_duplicate_raises(self, registry):
        with pytest.raises(ValueError, match="already exists"):
            registry.add_class("login_button", "TEXT")


class TestRemoveClass:
    @pytest.fixture()
    def registry(self, tmp_path, monkeypatch):
        path = _make_registry_at(
            tmp_path,
            [
                {"name": "login_button", "type": "TEXT"},
                {"name": "save_button", "type": "TEXT"},
            ],
        )
        _patch_registry_path(monkeypatch, path)
        from src.class_registry import ClassRegistry

        return ClassRegistry.load()

    def test_remove_class(self, registry):
        registry.remove_class("login_button")
        assert "login_button" not in registry.class_names()

    def test_remove_class_missing_raises(self, registry):
        with pytest.raises(KeyError):
            registry.remove_class("nonexistent_class")


class TestSetType:
    @pytest.fixture()
    def registry(self, tmp_path, monkeypatch):
        path = _make_registry_at(
            tmp_path,
            [{"name": "login_button", "type": "TEXT"}],
        )
        _patch_registry_path(monkeypatch, path)
        from src.class_registry import ClassRegistry

        return ClassRegistry.load()

    def test_set_type(self, registry):
        registry.set_type("login_button", "NON_TEXT")
        assert registry.get_type("login_button") == "NON_TEXT"
        assert registry.is_non_text("login_button") is True

    def test_set_type_missing_raises(self, registry):
        with pytest.raises(KeyError):
            registry.set_type("ghost_class", "NON_TEXT")


class TestSaveAndReload:
    def test_save_and_reload(self, tmp_path, monkeypatch):
        """Save to tmpdir, reload, verify round-trip."""
        path = tmp_path / "assets" / "class_registry.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        _patch_registry_path(monkeypatch, path)

        from src.class_registry import ClassEntry, ClassRegistry

        # Build a registry manually and save
        entries = [
            ClassEntry(name="alpha", type="TEXT"),
            ClassEntry(name="beta", type="NON_TEXT"),
        ]
        reg = ClassRegistry(entries, path)
        reg.save()

        assert path.exists()

        # Reload
        reg2 = ClassRegistry.load()
        assert reg2.class_names() == ["alpha", "beta"]
        assert reg2.get_type("alpha") == "TEXT"
        assert reg2.get_type("beta") == "NON_TEXT"
