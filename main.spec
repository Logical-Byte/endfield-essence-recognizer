# -*- mode: python ; coding: utf-8 -*-

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import cast

    from PyInstaller.building.api import COLLECT, EXE, PYZ
    from PyInstaller.building.build_main import Analysis
    from PyInstaller.config import CONF

    DISTPATH = cast(str, CONF["distpath"])

a = Analysis(
    ["src/endfield_essence_recognizer/__main__.py"],
    pathex=[],
    binaries=[],
    datas=[
        (
            "src/endfield_essence_recognizer/data",
            "endfield_essence_recognizer/data",
        ),
        (
            "src/endfield_essence_recognizer/templates",
            "endfield_essence_recognizer/templates",
        ),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="endfield-essence-recognizer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="endfield-essence-recognizer",
)

# 把 README.md 复制到 dist 目录
# 这里不做任何错误处理，如果有错误就构建失败
readme_src = Path("README.md")
readme_dst = Path(DISTPATH) / "endfield-essence-recognizer" / "README.md"
shutil.copy(readme_src, readme_dst)
