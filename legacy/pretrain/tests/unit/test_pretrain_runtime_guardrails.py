from __future__ import annotations

from scripts import preflight_pretrain_runtime


def test_pretrain_runtime_guard_passes_on_current_tree() -> None:
    preflight_pretrain_runtime.main()
