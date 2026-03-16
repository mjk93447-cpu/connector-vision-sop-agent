# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('assets/config.json', 'assets'),
        ('assets/sop_steps.json', 'assets'),
        # Package models directory (may only contain placeholders in git).
        ('assets/models', 'assets/models'),
    ],
    hiddenimports=[
        # Vision/ML Core
        'ultralytics',
        'torch',
        'torchvision',
        'torch._C',
        # CV
        'cv2',
        'PIL',
        'PIL.Image',
        # Utils
        'numpy',
        # GUI (PyQt6)
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.sip',
        # GUI sub-modules
        'src.gui',
        'src.gui.main_window',
        'src.gui.workers',
        'src.gui.panels',
        'src.gui.panels.sop_panel',
        'src.gui.panels.vision_panel',
        'src.gui.panels.llm_panel',
        'src.gui.panels.sop_editor_panel',
        'src.gui.panels.config_panel',
        'src.gui.panels.audit_panel',
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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
