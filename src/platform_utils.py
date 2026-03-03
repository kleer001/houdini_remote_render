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


def normalize_path(p: str) -> str:
    """Resolve and return a POSIX-style path string.

    USD always expects forward slashes internally.
    """
    return Path(p).resolve().as_posix()


def path_join(*parts: str) -> str:
    """Join path components and return a POSIX-style string."""
    return Path(os.path.join(*parts)).as_posix()


def ensure_dir(path: str) -> None:
    """Create directory and parents if they don't exist."""
    os.makedirs(path, exist_ok=True)


def get_shot_root_from_hip() -> str:
    """Derive shot root from the current HIP file path.

    Returns the grandparent directory of the HIP file as a POSIX path.
    Raises RuntimeError if the scene is unsaved (untitled).
    """
    import hou

    hip_path = hou.hipFile.path()
    if "untitled" in Path(hip_path).name.lower():
        raise RuntimeError(
            "Cannot determine shot root: scene is unsaved (untitled). "
            "Please save the scene first."
        )

    return Path(hip_path).parent.parent.as_posix()


def check_path_length(path: str, limit: int = 240) -> str | None:
    """Return a warning string if path exceeds limit, else None.

    Windows has a 260-char path limit. We warn at 240 to leave headroom.
    """
    if len(path) > limit:
        return f"Path length {len(path)} exceeds {limit} chars: {path}"
    return None
