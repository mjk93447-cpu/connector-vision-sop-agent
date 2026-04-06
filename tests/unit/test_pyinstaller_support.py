from __future__ import annotations

from pathlib import Path

from scripts.pyinstaller_support import (
    MAIN_BUNDLE_PACKAGES,
    OPTIONAL_BUNDLE_EXCLUDES,
    PRETRAIN_BUNDLE_PACKAGES,
    collect_package_bundle,
)


def test_bundle_package_lists_cover_numpy_and_cv2() -> None:
    assert "numpy" in MAIN_BUNDLE_PACKAGES
    assert "cv2" in MAIN_BUNDLE_PACKAGES
    assert "numpy" in PRETRAIN_BUNDLE_PACKAGES
    assert "cv2" in PRETRAIN_BUNDLE_PACKAGES
    assert "datasets" in PRETRAIN_BUNDLE_PACKAGES
    assert "huggingface_hub" in PRETRAIN_BUNDLE_PACKAGES


def test_optional_bundle_excludes_cover_heavy_optional_packages() -> None:
    assert "tensorflow" in OPTIONAL_BUNDLE_EXCLUDES
    assert "jax" in OPTIONAL_BUNDLE_EXCLUDES
    assert "keras" in OPTIONAL_BUNDLE_EXCLUDES
    assert "torch.testing._internal" not in OPTIONAL_BUNDLE_EXCLUDES


def test_requirements_pin_numpy_1_26() -> None:
    text = Path("requirements-common.txt").read_text(encoding="utf-8")
    assert "numpy==1.26.4" in text


def test_collect_package_bundle_merges_all_package_outputs(monkeypatch) -> None:
    calls: list[str] = []

    def fake_collect_all(package_name: str):
        calls.append(package_name)
        return (
            [(package_name, "data")],
            [(package_name, "binary")],
            [f"{package_name}.hidden"],
        )

    monkeypatch.setattr("scripts.pyinstaller_support.collect_all", fake_collect_all)

    datas, binaries, hiddenimports = collect_package_bundle(("numpy", "cv2"))

    assert calls == ["numpy", "cv2"]
    assert datas == [("numpy", "data"), ("cv2", "data")]
    assert binaries == [("numpy", "binary"), ("cv2", "binary")]
    assert hiddenimports == ["numpy.hidden", "cv2.hidden"]
