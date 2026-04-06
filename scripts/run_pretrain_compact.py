"""Compatibility wrapper for the deprecated compact pretrain entrypoint."""

from __future__ import annotations

from legacy.pretrain.run_pretrain_compact import main


if __name__ == "__main__":
    main()

