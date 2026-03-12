-*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(
    ['src/main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('assets/config.json', 'assets'),
        # Placeholder for YOLO weights; file is provided in deployment artifacts.
        ('assets/models/yolov26n.pt', 'assets/models'),
    ],
    hiddenimports=[
        'ultralytics',
        'cv2',
        'pytesseract',
        'pyyaml',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
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
    name='connector_vision_agent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
