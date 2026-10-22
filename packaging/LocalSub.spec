# -*- mode: python ; coding: utf-8 -*-
"""
LocalSub - PyInstaller Specification.
Packages LocalSub into a standalone Windows x64 distribution directory.
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs

block_cipher = None
project_root = Path.cwd()

# Collect data files and submodules
datas = [
    (str(project_root / "assets"), "assets"),
]

# Include bin/ffmpeg.exe if present
ffmpeg_exe = project_root / "bin" / "ffmpeg.exe"
binaries = []
if ffmpeg_exe.is_file():
    binaries.append((str(ffmpeg_exe), "bin"))

# Collect faster_whisper, ctranslate2, transformers, and huggingface_hub assets
datas += collect_data_files("faster_whisper")
datas += collect_data_files("transformers")

hiddenimports = [
    "ctranslate2",
    "faster_whisper",
    "transformers",
    "sentencepiece",
    "tokenizers",
    "huggingface_hub",
    "onnxruntime",
    "av",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
]
hiddenimports += collect_submodules("faster_whisper")
hiddenimports += collect_submodules("ctranslate2")

a = Analysis(
    [str(project_root / "app" / "main.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy", "notebook"],
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
    name="LocalSub",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # No terminal window on normal launch
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / "assets" / "app_icon.ico") if (project_root / "assets" / "app_icon.ico").is_file() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="LocalSub",
)
