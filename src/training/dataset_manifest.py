"""Dataset manifest validator for pretrain-only pipeline.

Manifest format (YAML)
----------------------
path: /path/to/data
sources:
  - name: showui_desktop
    enabled: true
    license: MIT
    format: yolo
    class_map:
      oled_inspection_top_view: 0
      ...
  - name: synthetic
    enabled: true
    ...

This module helps enforce source whitelist and metadata checks.
"""

from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any, Dict, List

VALID_SOURCES = {
    "showui_desktop",
    "synthetic",
    "rico_widget",
    "pcb_components",
}


class DatasetManifestError(ValueError):
    pass


class DatasetManifest:
    def __init__(self, manifest_path: Path | str):
        self.path = Path(manifest_path)
        if not self.path.exists():
            raise DatasetManifestError(f"Manifest not found: {self.path}")

        self._data = self._load_yaml(self.path)

    @staticmethod
    def _load_yaml(manifest_path: Path) -> Dict[str, Any]:
        with manifest_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise DatasetManifestError("Manifest must be a mapping")
        return data

    def validate(self) -> None:
        sources = self._data.get("sources")
        if sources is None or not isinstance(sources, list):
            raise DatasetManifestError("Manifest must contain sources list")

        for idx, src in enumerate(sources):
            if not isinstance(src, dict):
                raise DatasetManifestError(f"Source item at index {idx} must be mapping")

            name = src.get("name")
            if name not in VALID_SOURCES:
                raise DatasetManifestError(f"Invalid source name: {name}")

            if not isinstance(src.get("enabled"), bool):
                raise DatasetManifestError(f"Source {name} missing enabled bool")

            for key in ["license", "format", "class_map"]:
                if key not in src:
                    raise DatasetManifestError(f"Source {name} missing field {key}")

    @property
    def active_sources(self) -> List[str]:
        srcs = []
        for src in self._data.get("sources", []):
            if isinstance(src, dict) and src.get("enabled"):
                srcs.append(src.get("name"))
        return srcs

    @property
    def source_entries(self) -> List[Dict[str, Any]]:
        return [src for src in self._data.get("sources", []) if isinstance(src, dict)]

    def to_dict(self) -> Dict[str, Any]:
        return self._data
