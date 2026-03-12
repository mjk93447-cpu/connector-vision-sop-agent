"""
Top-level smoke test entry for Connector Vision SOP Agent v1.0.

Historically this file tried to import a specific test function from
`src.test_sop`. The test layout has since changed, so this wrapper now simply
delegates to the full `src.test_sop` module when run directly.
"""

from src.test_sop import *  # noqa: F401,F403


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main(["-q", "src/test_sop.py"]))
