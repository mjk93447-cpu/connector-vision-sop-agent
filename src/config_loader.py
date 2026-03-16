"""
Config loader for offline Samsung OLED line deployment.

Reads tuning values such as engineer password, ROI coordinates, retry counts,
and model/config paths from assets/config.json for field-side adjustment.

Path resolution order (supports both source-run and PyInstaller EXE):
  1. EXE 옆 경로  — connector_agent/assets/config.json  (사용자 편집 가능)
  2. CWD 상대경로 — 개발 환경 소스 실행 시
  3. _MEIPASS     — PyInstaller 번들 내부 fallback
"""

import json
import sys
from pathlib import Path
from typing import Any


def _resolve_config_path(config_path: Path) -> Path:
    """EXE/소스 양 환경에서 config 파일을 찾아 반환한다."""

    if config_path.is_absolute() and config_path.exists():
        return config_path

    candidates: list[Path] = []

    if getattr(sys, "frozen", False):
        # 1순위: EXE 파일 옆 (라인 PC에서 사용자가 편집하는 config)
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir / config_path)
        # 3순위: PyInstaller 번들 내부 (_MEIPASS)
        meipass = Path(getattr(sys, "_MEIPASS", ""))
        if meipass.exists():
            candidates.append(meipass / config_path)

    # 2순위: CWD 기준 상대 경로 (소스 실행 / pytest)
    candidates.append(config_path)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    # 모든 후보 실패 → 원본 경로를 반환해 open()이 표준 에러를 올리도록 함
    return config_path


def load_config(config_path: str | Path = "assets/config.json") -> dict[str, Any]:
    """Load and return the project configuration JSON file.

    Args:
        config_path: config 파일 경로 (기본값: ``assets/config.json``).
            절대 경로, 또는 EXE·CWD·_MEIPASS 기준 상대 경로를 모두 지원.

    Returns:
        config 딕셔너리.

    Raises:
        FileNotFoundError: 모든 후보 경로에서 파일을 찾지 못한 경우.
        json.JSONDecodeError: JSON 파싱 실패 시.
    """

    resolved = _resolve_config_path(Path(config_path))
    with resolved.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)
