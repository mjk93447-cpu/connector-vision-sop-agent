from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

_NON_TEXT_DEFAULTS = {
    "mold_left_label",
    "mold_right_label",
    "pin_cluster",
    "connector_pin",
}

_DEFAULT_TARGET_LABELS = [
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

_REGISTRY_RELATIVE = Path("assets") / "class_registry.json"


def _get_registry_path() -> Path:
    """Resolve the class_registry.json path using get_base_dir()."""
    from src.config_loader import get_base_dir

    return get_base_dir() / _REGISTRY_RELATIVE


@dataclass
class ClassEntry:
    name: str
    type: str  # "TEXT" | "NON_TEXT"


class ClassRegistry:
    """Registry of YOLO class names with TEXT/NON_TEXT classification."""

    def __init__(self, entries: List[ClassEntry], path: Path) -> None:
        self._entries: List[ClassEntry] = list(entries)
        self._path = path

    # ------------------------------------------------------------------
    # Class-method constructors
    # ------------------------------------------------------------------

    @classmethod
    def load(cls) -> ClassRegistry:
        """Load from assets/class_registry.json.

        Auto-creates from DEFAULT_TARGET_LABELS if the file is missing.
        """
        path = _get_registry_path()
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                entries = [
                    ClassEntry(name=c["name"], type=c["type"])
                    for c in data.get("classes", [])
                ]
                logger.debug(
                    "ClassRegistry loaded %d entries from %s", len(entries), path
                )
                return cls(entries, path)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to load class_registry.json (%s); using defaults", exc
                )

        # Auto-create from defaults
        entries = [
            ClassEntry(
                name=name,
                type="NON_TEXT" if name in _NON_TEXT_DEFAULTS else "TEXT",
            )
            for name in _DEFAULT_TARGET_LABELS
        ]
        registry = cls(entries, path)
        try:
            registry.save()
            logger.info("ClassRegistry auto-created at %s", path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not auto-save class_registry.json: %s", exc)
        return registry

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Save registry to class_registry.json."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "1.0",
            "classes": [{"name": e.name, "type": e.type} for e in self._entries],
        }
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.debug(
            "ClassRegistry saved %d entries to %s", len(self._entries), self._path
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def is_non_text(self, name: str) -> bool:
        """Return True if class type is NON_TEXT."""
        entry = self._find(name)
        if entry is None:
            return False
        return entry.type == "NON_TEXT"

    def get_type(self, name: str) -> Optional[str]:
        """Return 'TEXT' | 'NON_TEXT', or None if not found."""
        entry = self._find(name)
        return entry.type if entry is not None else None

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def add_class(self, name: str, type_: str) -> None:
        """Add a new class entry.

        Raises ValueError if a class with that name already exists.
        """
        if self._find(name) is not None:
            raise ValueError(f"Class '{name}' already exists in registry")
        self._entries.append(ClassEntry(name=name, type=type_))

    def remove_class(self, name: str) -> None:
        """Remove a class entry.

        Raises KeyError if the class is not found.
        """
        for i, entry in enumerate(self._entries):
            if entry.name == name:
                del self._entries[i]
                return
        raise KeyError(f"Class '{name}' not found in registry")

    def set_type(self, name: str, type_: str) -> None:
        """Change the type of an existing class.

        Raises KeyError if the class is not found.
        """
        entry = self._find(name)
        if entry is None:
            raise KeyError(f"Class '{name}' not found in registry")
        entry.type = type_

    # ------------------------------------------------------------------
    # Collection accessors
    # ------------------------------------------------------------------

    def all_classes(self) -> List[ClassEntry]:
        """Return a shallow copy of all entries."""
        return list(self._entries)

    def class_names(self) -> List[str]:
        """Return list of all class names."""
        return [e.name for e in self._entries]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find(self, name: str) -> Optional[ClassEntry]:
        for entry in self._entries:
            if entry.name == name:
                return entry
        return None
