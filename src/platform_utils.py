"""OS-agnostic path and executable helpers.

All OS-sensitive logic lives here. Nothing else in the codebase does OS detection.
"""

import os
import platform
import stat
from pathlib import Path


def _get_hfs_binary(binary: str) -> str:
    """Locate a binary inside $HFS/bin/.

    Returns the full path to the executable.
    Raises RuntimeError if $HFS is unset or the binary is missing.
    """
    try:
        import hou
        hfs = hou.expandString("$HFS")
    except ImportError:
        hfs = os.environ.get("HFS", "")

    if not hfs:
        raise RuntimeError(
            f"Cannot locate {binary}: $HFS is not set. "
            "Are you running inside Houdini?"
        )

    name = f"{binary}.exe" if platform.system() == "Windows" else binary
    path = os.path.join(hfs, "bin", name)

    if not os.path.isfile(path):
        raise RuntimeError(
            f"{binary} not found at {path}. "
            f"Expected it inside $HFS/bin/ (HFS={hfs})."
        )

    return path


def get_imaketx_path() -> str:
    """Locate imaketx inside $HFS/bin/."""
    return _get_hfs_binary("imaketx")


def get_iconvert_path() -> str:
    """Locate iconvert inside $HFS/bin/."""
    return _get_hfs_binary("iconvert")


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


def detect_hfs() -> str | None:
    """Return ``$HFS`` path from environment, or None if unset/missing."""
    hfs = os.environ.get("HFS")
    if hfs and os.path.isdir(hfs):
        return hfs
    return None


def make_executable(path: str) -> None:
    """Add owner/group/other execute bits to a file."""
    st = os.stat(path)
    os.chmod(path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def hfs_source_block(hfs_path: str | None) -> str:
    """Return a bash snippet that sources ``houdini_setup_bash``.

    If *hfs_path* is None, returns a comment indicating hython/husk must
    already be on PATH.
    """
    if hfs_path:
        return f"""
# Source Houdini environment
_HFS="${{HFS:-{hfs_path}}}"
_SHOT_ROOT="$(pwd)"
if [ -d "$_HFS" ]; then
    cd "$_HFS"
    source ./houdini_setup_bash
    cd "$_SHOT_ROOT"
fi
"""
    return """
# HFS not known at packaging time — hython/husk must be on PATH
"""
