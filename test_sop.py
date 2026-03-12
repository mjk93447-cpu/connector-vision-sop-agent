"""
Top-level smoke test entry for Connector Vision SOP Agent v1.0.

Bridges repository-level test execution to the src-based SOP validation module.
"""

from src.test_sop import test_main_returns_trace


if __name__ == "__main__":
    test_main_returns_trace()
    print("test_main_returns_trace: OK")
