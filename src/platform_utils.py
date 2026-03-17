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


def copy_launcher(name: str, dest_dir: str) -> str:
    """Copy a launcher script from launchers/ into the package Scripts/ dir.

    Args:
        name: Launcher filename (e.g. "run_render.py").
        dest_dir: Destination directory (e.g. shot_root/Scripts/).

    Returns:
        Full path to the copied launcher.
    """
    # Resolve launchers/ relative to repo root (one level up from src/)
    src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    launcher_path = os.path.join(src_dir, "launchers", name)

    if not os.path.isfile(launcher_path):
        raise FileNotFoundError(
            f"Launcher not found: {launcher_path}. "
            f"Expected it in the launchers/ directory of the repo."
        )

    import shutil
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, name)
    shutil.copy2(launcher_path, dest)
    make_executable(dest)
    return dest


def detect_redshift() -> str | None:
    """Return ``$REDSHIFT_COREDATAPATH`` from environment, or None.

    Falls back to common Linux install paths if the env var is unset.
    """
    rs = os.environ.get("REDSHIFT_COREDATAPATH")
    if rs and os.path.isdir(rs):
        return rs

    for fallback in ("/usr/redshift", "/opt/redshift"):
        if os.path.isdir(fallback):
            return fallback

    return None


def get_redshift_binary(name: str) -> str:
    """Locate a binary inside ``$REDSHIFT_COREDATAPATH/bin/``.

    Returns the full path to the executable.
    Raises RuntimeError if the path cannot be resolved.
    """
    rs = detect_redshift()
    if not rs:
        raise RuntimeError(
            f"Cannot locate {name}: $REDSHIFT_COREDATAPATH is not set "
            "and no Redshift install found at /usr/redshift or /opt/redshift."
        )

    binary = f"{name}.exe" if platform.system() == "Windows" else name
    path = os.path.join(rs, "bin", binary)

    if not os.path.isfile(path):
        raise RuntimeError(
            f"{name} not found at {path}. "
            f"Expected it inside $REDSHIFT_COREDATAPATH/bin/ "
            f"(REDSHIFT_COREDATAPATH={rs})."
        )

    return path


def redshift_env_block(rs_path: str | None) -> str:
    """Return a bash snippet that sets up the Redshift environment.

    Sets ``REDSHIFT_COREDATAPATH``, adds ``bin/`` to ``PATH`` and
    ``LD_LIBRARY_PATH``, and echoes the license server if configured.
    """
    if rs_path:
        return f"""
# Redshift environment
export REDSHIFT_COREDATAPATH="${{REDSHIFT_COREDATAPATH:-{rs_path}}}"
export PATH="$REDSHIFT_COREDATAPATH/bin:$PATH"
export LD_LIBRARY_PATH="$REDSHIFT_COREDATAPATH/bin:${{LD_LIBRARY_PATH:-}}"

if [ -n "${{redshift_LICENSE:-}}" ]; then
    echo "License server: $redshift_LICENSE"
fi
"""
    return """
# REDSHIFT_COREDATAPATH not known at packaging time —
# redshiftUsdCmdLine must already be on PATH
"""


