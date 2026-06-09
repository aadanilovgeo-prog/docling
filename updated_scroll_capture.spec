# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec: updated_scroll_capture.exe (Windows)

block_cipher = None

a = Analysis(
    ['updated_scroll_capture.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'numpy',
        'PIL',
        'PIL.Image',
        'PIL.ImageFilter',
        'scroll_long_screenshot',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['playwright', 'matplotlib', 'tkinter', 'pytest'],
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
    name='updated_scroll_capture',
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
)
