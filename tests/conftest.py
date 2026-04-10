from __future__ import annotations

import os
import re
import shutil
import uuid
import json
from pathlib import Path

import pytest


def _default_runtime_root() -> Path:
    override = os.environ.get("CONNECTOR_AGENT_TEST_RUNTIME")
    if override:
        return Path(override).expanduser().resolve()

    return Path("artifacts/test-runtime/tmpcases").resolve()


_CREATED_DIRS: list[Path] = []


def _safe_node_name(nodeid: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", nodeid)
    return cleaned[:80] or "tmpcase"


@pytest.fixture
def tmp_path(request: pytest.FixtureRequest) -> Path:
    """Stable tmp_path replacement that avoids the flaky Windows tmpdir plugin path.

    Some Windows environments in this repository produce inaccessible ACLs for the
    built-in pytest tmpdir base folder during session cleanup. We keep a repo-local
    temp root under artifacts/test-runtime instead, which also makes strict QA runs
    easier to inspect after failures.
    """

    runtime_root = _default_runtime_root()
    runtime_root.mkdir(parents=True, exist_ok=True)
    case_dir = runtime_root / f"{_safe_node_name(request.node.nodeid)}_{uuid.uuid4().hex[:8]}"
    case_dir.mkdir(parents=True, exist_ok=False)
    _CREATED_DIRS.append(case_dir)
    return case_dir.resolve()


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    config = {
        "version": "5.1.0",
        "password": "1111",
        "llm": {"enabled": False, "backend": "http", "model_path": "dummy"},
        "vision": {"model_path": "assets/models/yolo26x_local_pretrained.pt", "confidence_threshold": 0.6, "ocr_psm": 7},
        "control": {"retries": 3},
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    keep_tmp = session.config.getoption("--keep-tmp-artifacts", default=False)
    if keep_tmp:
        return

    for path in reversed(_CREATED_DIRS):
        shutil.rmtree(path, ignore_errors=True)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--keep-tmp-artifacts",
        action="store_true",
        default=False,
        help="Keep repo-local temporary test directories under artifacts/test-runtime/tmpcases.",
    )
