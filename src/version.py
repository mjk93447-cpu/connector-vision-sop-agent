"""Central version management for Connector Vision SOP Agent.

Import:
    from src.version import APP_VERSION, APP_NAME, FULL_TITLE, WINDOW_TITLE

CLI bump tool (standalone — no package import required):
    python src/version.py --bump patch   # 4.1.1 -> 4.1.2
    python src/version.py --bump minor   # 4.1.1 -> 4.2.0
    python src/version.py --bump major   # 4.1.1 -> 5.0.0
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

APP_VERSION = "4.1.1"
APP_NAME = "Connector Vision SOP Agent"

FULL_TITLE = f"{APP_NAME} v{APP_VERSION}"
WINDOW_TITLE = f"{APP_NAME} v{APP_VERSION} [Offline]"


# ---------------------------------------------------------------------------
# Bump helpers
# ---------------------------------------------------------------------------

_VPREFIX_RE = re.compile(r"v\d+\.\d+\.\d+")


def _bump(version: str, part: str) -> str:
    """Return incremented version string.

    >>> _bump("4.1.0", "patch")
    '4.1.1'
    >>> _bump("4.1.1", "minor")
    '4.2.0'
    >>> _bump("4.2.0", "major")
    '5.0.0'
    """
    major, minor, patch = map(int, version.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    if part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"Unknown bump part: {part!r}. Use major/minor/patch.")


def _bump_all(part: str) -> None:
    """Perform version bump across all tracked files and print a summary."""
    this_file = Path(__file__).resolve()
    project_root = this_file.parent.parent  # src/ -> project root

    # 1. Read current version from this file
    text = this_file.read_text(encoding="utf-8")
    m = re.search(r'^APP_VERSION\s*=\s*"(\d+\.\d+\.\d+)"', text, re.MULTILINE)
    if not m:
        print("[ERROR] Could not find APP_VERSION in version.py", file=sys.stderr)
        sys.exit(1)
    old_v = m.group(1)
    new_v = _bump(old_v, part)

    print(f"Bumping {part}: {old_v} -> {new_v}\n")
    changes = []

    # 2. version.py itself — only the APP_VERSION line
    new_text = re.sub(
        r'^(APP_VERSION\s*=\s*")(\d+\.\d+\.\d+)(")',
        lambda mo: f"{mo.group(1)}{new_v}{mo.group(3)}",
        text,
        flags=re.MULTILINE,
    )
    this_file.write_text(new_text, encoding="utf-8")
    changes.append(f"  updated  src/version.py  ({old_v} -> {new_v})")

    # 3. Launcher files that embed vX.Y.Z
    targets = [
        "assets/launchers/start_agent.bat",
        "assets/launchers/INSTALL_GUIDE.txt",
        "assets/launchers/MERGE_GUIDE.txt",
    ]
    for rel in targets:
        p = project_root / rel
        if p.exists():
            t = p.read_text(encoding="utf-8")
            t2 = _VPREFIX_RE.sub(f"v{new_v}", t)
            if t2 != t:
                p.write_text(t2, encoding="utf-8")
                changes.append(f"  updated  {rel}")
            else:
                changes.append(f"  (no vX.Y.Z found) {rel}")

    print("Files changed:")
    for line in changes:
        print(line)
    print(f"\nDone. New version: {new_v}")
    print(f'Remember to commit: git commit -m "[chore] bump version to {new_v}"')


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Connector Vision SOP Agent version bump tool.",
        epilog="Example: python src/version.py --bump patch",
    )
    parser.add_argument(
        "--bump",
        choices=["major", "minor", "patch"],
        required=True,
        help="Which part of the semver to increment.",
    )
    args = parser.parse_args()
    _bump_all(args.bump)


if __name__ == "__main__":
    main()
