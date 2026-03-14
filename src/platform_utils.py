"""OS-agnostic path and executable helpers.

All OS-sensitive logic lives here. Nothing else in the codebase does OS detection.
"""

import os
import platform
from pathlib import Path


def get_imaketx_path() -> str:
    """Locate imaketx inside $HFS/bin/.

    Returns the full path to the imaketx executable.
    Raises RuntimeError if not found.
    """
    try:
        import hou
        hfs = hou.expandString("$HFS")
    except ImportError:
        hfs = os.environ.get("HFS", "")

    if not hfs:
        raise RuntimeError(
            "Cannot locate imaketx: $HFS is not set. "
            "Are you running inside Houdini?"
        )

    name = "imaketx.exe" if platform.system() == "Windows" else "imaketx"
    path = os.path.join(hfs, "bin", name)

    if not os.path.isfile(path):
        raise RuntimeError(
            f"imaketx not found at {path}. "
            f"Expected it inside $HFS/bin/ (HFS={hfs})."
        )

    return path


def get_iconvert_path() -> str:
    """Locate iconvert inside $HFS/bin/.

    Returns the full path to the iconvert executable.
    Raises RuntimeError if not found.
    """
    try:
        import hou
        hfs = hou.expandString("$HFS")
    except ImportError:
        hfs = os.environ.get("HFS", "")

    if not hfs:
        raise RuntimeError(
            "Cannot locate iconvert: $HFS is not set. "
            "Are you running inside Houdini?"
        )

    name = "iconvert.exe" if platform.system() == "Windows" else "iconvert"
    path = os.path.join(hfs, "bin", name)

    if not os.path.isfile(path):
        raise RuntimeError(
            f"iconvert not found at {path}. "
            f"Expected it inside $HFS/bin/ (HFS={hfs})."
        )

    return path


def normalize_path(p: str) -> str:
    """Resolve and return a POSIX-style path string.

    USD always expects forward slashes internally.
    """
    return Path(p).resolve().as_posix()


def path_join(*parts: str) -> str:
    """Join path components and return a POSIX-style string."""
    return Path(os.path.join(*parts)).as_posix()


def ensure_dir(path: str) -> None:
    """Create directory and parents if they don't exist.

    Also creates a .placeholder file so the directory survives
    sync to services like Google Drive that drop empty folders.
    """
    os.makedirs(path, exist_ok=True)
    placeholder = os.path.join(path, ".placeholder")
    if not os.path.exists(placeholder):
        with open(placeholder, "w", newline="\n") as f:
            f.write("")


def get_hip_dir() -> str:
    """Return the directory containing the current HIP file as a POSIX path.

    Raises RuntimeError if the scene is unsaved (untitled).
    """
    import hou

    hip_path = hou.hipFile.path()
    if "untitled" in Path(hip_path).name.lower():
        raise RuntimeError(
            "Scene is unsaved (untitled). Please save the scene first."
        )

    return Path(hip_path).parent.as_posix()


def check_disk_space(path: str) -> tuple[int, int, int]:
    """Return (total, used, free) disk space in bytes for the filesystem containing path."""
    import shutil
    usage = shutil.disk_usage(path)
    return (usage.total, usage.used, usage.free)
