from __future__ import annotations

import ast
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))


TARGET_FILE = Path("src/training/compact_pretrain_pipeline.py")


def _parse_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _find_class(tree: ast.Module, name: str) -> ast.ClassDef:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise RuntimeError(f"Class {name!r} not found in {TARGET_FILE}")


def _find_method(cls: ast.ClassDef, name: str) -> ast.FunctionDef:
    for node in cls.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise RuntimeError(f"Method {cls.name}.{name} not found in {TARGET_FILE}")


def _has_staticmethod(method: ast.FunctionDef) -> bool:
    return any(isinstance(d, ast.Name) and d.id == "staticmethod" for d in method.decorator_list)


def _train_and_save_uses_bound_yaml_path(method: ast.FunctionDef) -> None:
    assign_lines: list[int] = []
    load_lines: list[int] = []

    for node in ast.walk(method):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "yaml_path":
                    assign_lines.append(node.lineno)
        if isinstance(node, ast.Name) and node.id == "yaml_path" and isinstance(node.ctx, ast.Load):
            load_lines.append(node.lineno)

    if not assign_lines:
        raise RuntimeError(
            "compact pretrain runtime guard failed: train_and_save() does not assign yaml_path."
        )
    if not load_lines:
        raise RuntimeError(
            "compact pretrain runtime guard failed: train_and_save() does not use yaml_path."
        )
    if min(assign_lines) > min(load_lines):
        raise RuntimeError(
            "compact pretrain runtime guard failed: yaml_path is used before assignment."
        )


def main() -> None:
    if not TARGET_FILE.exists():
        raise FileNotFoundError(f"Critical pretrain file not found: {TARGET_FILE}")

    tree = _parse_tree(TARGET_FILE)
    cls = _find_class(tree, "CompactPretrainPipeline")
    train_and_save = _find_method(cls, "train_and_save")
    find_best_weights = _find_method(cls, "_find_best_weights")

    _train_and_save_uses_bound_yaml_path(train_and_save)
    if not _has_staticmethod(find_best_weights):
        raise RuntimeError(
            "compact pretrain runtime guard failed: _find_best_weights must be @staticmethod."
        )

    print("[preflight_pretrain] pretrain runtime guard checks passed")


if __name__ == "__main__":
    main()
