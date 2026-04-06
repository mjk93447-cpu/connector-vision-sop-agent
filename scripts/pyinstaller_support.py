"""Shared helpers for PyInstaller spec files.

The spec files are executed during build time, so keeping the package
collection logic in one place helps us reuse the same dependency set for the
main agent EXE and the local pretrain EXE.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from PyInstaller.utils.hooks import collect_all

# Packages that should always be bundled with the main agent EXE.
MAIN_BUNDLE_PACKAGES: tuple[str, ...] = (
    "numpy",
    "cv2",
    "PIL",
)

# The pretrain EXE needs the same CV stack plus the dataset download helpers.
PRETRAIN_BUNDLE_PACKAGES: tuple[str, ...] = (
    "numpy",
    "cv2",
    "PIL",
    "datasets",
    "huggingface_hub",
)

# Packages that are noisy or heavyweight in the current environment, but are
# not needed by the offline runtime paths we ship in the artifacts.
OPTIONAL_BUNDLE_EXCLUDES: tuple[str, ...] = (
    "tensorflow",
    "keras",
    "jax",
    "jaxlib",
    "tensorboard",
    "torch.testing._internal",
    "expecttest",
    "pytest",
)


def collect_package_bundle(packages: Iterable[str]) -> tuple[list[Any], list[Any], list[str]]:
    """Collect datas, binaries, and hidden imports for a list of packages."""

    datas: list[Any] = []
    binaries: list[Any] = []
    hiddenimports: list[str] = []

    for package_name in packages:
        package_datas, package_binaries, package_hiddenimports = collect_all(package_name)
        datas.extend(package_datas)
        binaries.extend(package_binaries)
        hiddenimports.extend(package_hiddenimports)

    return datas, binaries, hiddenimports
