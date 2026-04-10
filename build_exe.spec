# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from scripts.pyinstaller_support import MAIN_BUNDLE_PACKAGES, collect_package_bundle
from scripts.pyinstaller_support import OPTIONAL_BUNDLE_EXCLUDES

block_cipher = None

bundle_datas, bundle_binaries, bundle_hiddenimports = collect_package_bundle(
    MAIN_BUNDLE_PACKAGES
)

a = Analysis(
    ['src/gui_app.py'],
    pathex=['.'],
    binaries=bundle_binaries,
    datas=[
        ('assets/config.json', 'assets'),
        ('assets/sop_steps.json', 'assets'),
        # Package models directory (may only contain placeholders in git).
        ('assets/models', 'assets/models'),
    ] + bundle_datas,
    hiddenimports=[
        # Vision/ML Core
        'ultralytics',
        'torch',
        'torchvision',
        'torch._C',
        # CV/OCR
        'cv2',
        'pytesseract',
        'PIL',
        'PIL.Image',
        # Utils
        'numpy',
    ] + bundle_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=list(OPTIONAL_BUNDLE_EXCLUDES),
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    name='connector_vision_agent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX on the current Windows workstation turns the already-large torch/cv
    # bundle into a very slow final-packaging step. Keep the build uncompressed
    # so QA can regenerate bundle candidates in a practical amount of time.
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    exclude_binaries=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='connector_vision_agent',
)
