"""资源文件存储工具：BGM / 图片集 / 视频统一落 UPLOAD_ROOT。

DB 中只存相对路径，前端通过 /media/{relpath} 拉取。
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from ..config import DATA_DIR

UPLOAD_ROOT = DATA_DIR / "uploads"
BGM_DIR = UPLOAD_ROOT / "bgm"
IMAGE_SETS_DIR = UPLOAD_ROOT / "image_sets"
VIDEOS_DIR = UPLOAD_ROOT / "videos"


def ensure_upload_dirs() -> None:
    for d in (UPLOAD_ROOT, BGM_DIR, IMAGE_SETS_DIR, VIDEOS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def abs_path(relpath: str) -> Path:
    return UPLOAD_ROOT / relpath


def rel_path(p: Path) -> str:
    return p.resolve().relative_to(UPLOAD_ROOT.resolve()).as_posix()


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._一-鿿-]+")


def safe_filename(name: str, fallback: str = "file") -> str:
    base = _SAFE_NAME_RE.sub("_", name).strip("._-")
    return base or fallback


def image_set_dir(set_id: int) -> Path:
    d = IMAGE_SETS_DIR / str(set_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def video_dir(video_id: int) -> Path:
    d = VIDEOS_DIR / str(video_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def remove_dir(path: Path) -> None:
    if path.exists() and path.is_dir():
        shutil.rmtree(path, ignore_errors=True)


def remove_file(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass
