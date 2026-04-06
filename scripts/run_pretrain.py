"""Compatibility wrapper for the deprecated legacy pretrain entrypoint."""

from __future__ import annotations

from legacy.pretrain.run_pretrain import main


if __name__ == "__main__":
    main()

