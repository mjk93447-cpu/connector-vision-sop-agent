"""Deprecated legacy pretrain entrypoint.

Use `scripts/run_pretrain_local.py` for all new work.
This shim is kept only so older notes and shortcuts fail with a clear message.
"""

from __future__ import annotations


def main() -> None:
    print(
        "[DEPRECATED] legacy.pretrain.run_pretrain is no longer the canonical pretrain entrypoint."
    )
    print("Use scripts/run_pretrain_local.py instead.")
    raise SystemExit(2)


if __name__ == "__main__":
    main()

