from __future__ import annotations

import ast
from pathlib import Path

from src.model_artifacts import CLOUD_PRETRAIN_MODEL_NAME, COCO_BASE_MODEL_NAME

APP_CRITICAL_FILES = (
    Path("src/main.py"),
    Path("src/gui/main_window.py"),
    Path("src/gui/workers.py"),
    Path("src/gui/panels/training_panel.py"),
    Path("src/training/training_manager.py"),
)


def _scan_class_method_signatures(file_path: Path) -> list[str]:
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    issues: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for member in node.body:
            if not isinstance(member, ast.FunctionDef):
                continue
            if not member.args.args:
                continue

            first_arg = member.args.args[0].arg
            decorators = {
                d.id
                for d in member.decorator_list
                if isinstance(d, ast.Name)
            }
            has_static = "staticmethod" in decorators
            has_class = "classmethod" in decorators

            if first_arg not in {"self", "cls"} and not (has_static or has_class):
                issues.append(
                    f"{file_path}:{member.lineno} "
                    f"{node.name}.{member.name} first arg '{first_arg}' "
                    "requires @staticmethod/@classmethod"
                )
            if first_arg == "cls" and not has_class:
                issues.append(
                    f"{file_path}:{member.lineno} "
                    f"{node.name}.{member.name} uses 'cls' without @classmethod"
                )
            if first_arg == "self" and has_static:
                issues.append(
                    f"{file_path}:{member.lineno} "
                    f"{node.name}.{member.name} uses 'self' with @staticmethod"
                )

    return issues


def test_app_critical_class_method_signatures_are_safe() -> None:
    issues: list[str] = []
    for file_path in APP_CRITICAL_FILES:
        assert file_path.exists(), f"Critical app file not found: {file_path}"
        issues.extend(_scan_class_method_signatures(file_path))
    assert not issues, "Method signature guard failed:\n" + "\n".join(issues)


def test_training_panel_base_model_priority_is_preserved() -> None:
    from src.gui.panels.training_panel import _resolve_base_model_options

    model_paths = [path for _, path in _resolve_base_model_options()]
    assert model_paths
    assert model_paths[0].endswith(f"/{CLOUD_PRETRAIN_MODEL_NAME}")
    assert any(path.endswith(f"/{COCO_BASE_MODEL_NAME}") for path in model_paths)
