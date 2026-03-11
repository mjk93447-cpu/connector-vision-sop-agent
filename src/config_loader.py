"""
Config loader for offline Samsung OLED line deployment.

Reads tuning values such as engineer password, ROI coordinates, retry counts,
and model/config paths from assets/config.json for field-side adjustment.
"""

import json
from pathlib import Path
from typing import Any


def load_config(config_path: str | Path = "assets/config.json") -> dict[str, Any]:
    """Load and return the project configuration JSON file."""

    path = Path(config_path)
    with path.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)
