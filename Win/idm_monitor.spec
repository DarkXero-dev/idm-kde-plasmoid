# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — produces a single portable .exe
# Build: pyinstaller idm_monitor.spec

import os
block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        (os.path.join(SPECPATH, 'logo.png'), '.'),    # IDM logo bundled alongside exe
    ],
    hiddenimports=[
        'pkg_resources.py2_compat',
        'requests.packages.urllib3',
        'charset_normalizer',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'numpy', 'scipy',
        'PIL', 'pandas', 'pytest',
    ],
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
    name='IDMQuotaMonitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                       # compress with UPX if available
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                  # no console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(SPECPATH, 'IDMLB.ico'),   # app icon embedded in the exe
    version_file=None,
)
