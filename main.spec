import shutil
from pathlib import Path
from typing import cast

from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.config import CONF
from PyInstaller.utils.hooks import collect_data_files

DISTPATH = cast("str", CONF["distpath"])

NAME = "endfield-essence-recognizer"


a = Analysis(
    ["src/endfield_essence_recognizer/__main__.py"],
    pathex=[],
    binaries=[],
    datas=[
        *collect_data_files("endfield_essence_recognizer"),
        *collect_data_files("certifi"),  # 新增：打包 CA 证书
        (
            "frontend/dist",
            "endfield_essence_recognizer/webui_dist",
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
    name=NAME,
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
    icon=["frontend/public/favicon.ico"],
    uac_admin=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=NAME,
)

# 拷贝一些额外的文件到 dist 目录
# 这里不做任何错误处理，如果有错误就构建失败
paths = [
    (Path("README.md"), Path(DISTPATH) / NAME),
    (Path("resources/images/遇到报错解决方法.webp"), Path(DISTPATH) / NAME),
    (Path("resources/texts/界面白屏解决方法.md"), Path(DISTPATH) / NAME),
    (Path("resources"), Path(DISTPATH) / NAME / "resources"),
]
for src, dst in paths:
    if src.is_file():
        shutil.copy(src, dst)
    elif src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        raise FileNotFoundError(f"{src} not found")

# 删除不需要的 opencv_videoio_ffmpeg DLL
for path in (Path(DISTPATH) / NAME / "_internal" / "cv2").glob(
    "opencv_videoio_ffmpeg*.dll"
):
    path.unlink()

# 拷贝 eer_updater.exe 到 _internal 目录（本地构建时从 updater/target/release/ 复制）
updater_src = Path("updater/target/release/eer_updater.exe")
updater_dst = Path(DISTPATH) / NAME / "_internal" / "eer_updater.exe"
if updater_src.is_file():
    updater_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(updater_src, updater_dst)
