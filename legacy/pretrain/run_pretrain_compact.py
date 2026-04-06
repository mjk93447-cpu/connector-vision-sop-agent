"""Deprecated compact pretrain entrypoint.

Use `scripts/run_pretrain_local.py` for the supported offline workflow.
"""

from __future__ import annotations


def main() -> None:
    print(
        "[DEPRECATED] legacy.pretrain.run_pretrain_compact is kept only for compatibility."
    )
    print("Use scripts/run_pretrain_local.py instead.")
    raise SystemExit(2)


if __name__ == "__main__":
    main()

