# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from scripts.pyinstaller_support import (
    PRETRAIN_BUNDLE_PACKAGES,
    OPTIONAL_BUNDLE_EXCLUDES,
    collect_package_bundle,
)

block_cipher = None

bundle_datas, bundle_binaries, bundle_hiddenimports = collect_package_bundle(
    PRETRAIN_BUNDLE_PACKAGES
)

a = Analysis(
    ['scripts/run_pretrain_local.py'],
    pathex=['.'],
    binaries=bundle_binaries,
    datas=[
        ('assets/config.json', 'assets'),
        ('assets/models', 'assets/models'),
    ] + bundle_datas,
    hiddenimports=[
        'ultralytics',
        'torch',
        'torchvision',
        'torch._C',
        'cv2',
        'numpy',
        'yaml',
        'PIL',
        'PIL.Image',
        'datasets',
        'huggingface_hub',
        'roboflow',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='connector_pretrain',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
