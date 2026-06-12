# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

ROOT = Path(SPECPATH)

# customtkinter のテーマ・フォントデータをバンドル
ctk_datas = collect_data_files('customtkinter')

a = Analysis(
    [str(ROOT / 'widget' / '__main__.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=ctk_datas + [
        (str(ROOT / 'widget' / 'data'), 'widget/data'),
    ],
    hiddenimports=[
        'customtkinter',
        'tkinter',
        'tkinter.ttk',
        'tkcalendar',
        'pystray',
        'pynput.keyboard',
        'pynput.mouse',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'winrt.windows.applicationmodel.datatransfer',
        'winrt.windows.storage.streams',
        'winotify',
        'sounddevice',
        'scipy',
        'scipy.signal',
        'faster_whisper',
        'tkinterdnd2',
        'httpx',
        'ollama',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'matplotlib', 'notebook'],
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
    exclude_binaries=True,
    name='AutoTicket',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
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
    upx=True,
    upx_exclude=[],
    name='AutoTicket',
)
