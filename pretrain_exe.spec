# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['scripts/run_pretrain_local.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('assets/config.json', 'assets'),
        ('assets/models', 'assets/models'),
    ],
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
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
