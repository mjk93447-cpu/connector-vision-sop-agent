# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('assets/config.json', 'assets'),
        ('assets/models/yolov26n.pt', 'assets/models')
    ],
    hiddenimports=[
        # Vision/ML Core (필수)
        'ultralytics',
        'ultralytics.yolo.engine.model',
        'ultralytics.yolo.utils',
        'torch',
        'torchvision',
        'torch._C',
        
        # CV/OCR
        'cv2',
        'pytesseract',
        'PIL',
        'PIL.Image',
        
        # Utils
        'pyyaml',
        'numpy'
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
    name='connector_vision_agent',
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
    icon=None  # 아이콘 추가시 경로 입력
)
