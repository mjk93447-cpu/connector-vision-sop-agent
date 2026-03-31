from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}


def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in _IMAGE_SUFFIXES


@dataclass
class AnnotationQueue:
    """Simple ordered queue for bulk image annotation workflows."""

    items: List[Path] = field(default_factory=list)
    index: int = 0

    def clear(self) -> None:
        self.items = []
        self.index = 0

    def load(self, paths: Iterable[Path]) -> int:
        unique: List[Path] = []
        seen = set()
        for path in paths:
            p = Path(path)
            if not is_image_file(p):
                continue
            resolved = p.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            unique.append(p)
        unique.sort(key=lambda p: (p.name.lower(), str(p)))
        self.items = unique
        self.index = 0 if unique else -1
        return len(unique)

    def has_items(self) -> bool:
        return bool(self.items)

    def current(self) -> Path | None:
        if not self.items or self.index < 0 or self.index >= len(self.items):
            return None
        return self.items[self.index]

    def next(self) -> Path | None:
        if not self.items:
            return None
        if self.index < len(self.items) - 1:
            self.index += 1
        return self.current()

    def prev(self) -> Path | None:
        if not self.items:
            return None
        if self.index > 0:
            self.index -= 1
        return self.current()

    def set_index(self, index: int) -> Path | None:
        if not self.items:
            self.index = -1
            return None
        self.index = max(0, min(index, len(self.items) - 1))
        return self.current()

    def position(self) -> tuple[int, int]:
        if not self.items:
            return (0, 0)
        return (self.index + 1, len(self.items))
