# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Coletar dados extras (bases de dados CSV, etc.)
datas = [
    ('ps2_db.csv', '.'),
]
datas += collect_data_files('emumanager')

a = Analysis(
    ['emumanager/__main__.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'emumanager.core.session',
        'emumanager.core.orchestrator',
        'emumanager.core.scanner',
        'emumanager.core.dat_manager',
        'emumanager.core.integrity',
        'emumanager.common.registry',
        'emumanager.ps2.provider',
        'emumanager.psx.provider',
        'emumanager.switch.provider',
        'emumanager.gamecube.provider',
        'emumanager.wii.provider',
        'emumanager.n3ds.provider',
        'emumanager.psp.provider',
        'emumanager.ps3.provider'
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
    name='emumanager',
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
    icon='docs/assets/icon.ico' if os.path.exists('docs/assets/icon.ico') else None
)
