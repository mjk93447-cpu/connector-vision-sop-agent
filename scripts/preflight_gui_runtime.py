from __future__ import annotations

import ast
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.model_artifacts import CLOUD_PRETRAIN_MODEL_NAME, COCO_BASE_MODEL_NAME

APP_CRITICAL_FILES = (
    Path("src/main.py"),
    Path("src/gui/main_window.py"),
    Path("src/gui/workers.py"),
    Path("src/gui/panels/training_panel.py"),
    Path("src/training/training_manager.py"),
)


def _scan_class_method_signatures(file_path: Path) -> list[str]:
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(file_path))
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


def _smoke_imports_and_model_priority() -> None:
    import src.gui.main_window  # noqa: F401
    import src.gui.workers  # noqa: F401
    import src.training.training_manager  # noqa: F401
    from src.gui.panels.training_panel import _resolve_base_model_options

    options = _resolve_base_model_options()
    model_paths = [path for _, path in options]
    if not model_paths:
        raise RuntimeError("Training panel base model options are empty.")
    if not model_paths[0].endswith(f"/{CLOUD_PRETRAIN_MODEL_NAME}"):
        raise RuntimeError(
            "Training panel model priority is broken: cloud pretrain "
            "must be the first option."
        )
    if not any(path.endswith(f"/{COCO_BASE_MODEL_NAME}") for path in model_paths):
        raise RuntimeError("COCO base model option is missing from training panel.")


def main() -> None:
    issues: list[str] = []
    for file_path in APP_CRITICAL_FILES:
        if not file_path.exists():
            raise FileNotFoundError(f"Critical app file not found: {file_path}")
        issues.extend(_scan_class_method_signatures(file_path))

    if issues:
        raise RuntimeError(
            "GUI runtime method-signature guard failed:\n" + "\n".join(issues)
        )

    _smoke_imports_and_model_priority()
    print("[preflight_gui] GUI runtime guard checks passed")


if __name__ == "__main__":
    main()
