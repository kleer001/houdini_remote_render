"""Shot name and path validation guards.

All go/no-go checks before any file operations run.
"""

import os
import re
from pathlib import Path

ILLEGAL_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')
REQUIRED_SHOT_DIRS = ("Output", "Cache", "Scenes", "Scripts")


def validate_shot_name(name: str) -> tuple[bool, str]:
    """Validate a shot name for use in file paths.

    Returns (True, "") on success, (False, reason) on failure.
    """
    if not name or name.strip() == "":
        return False, "Shot name is empty."

    if name == "SHOT_NAME_HERE":
        return False, "Shot name is still the default placeholder. Please set a real shot name."

    match = ILLEGAL_FILENAME_CHARS.search(name)
    if match:
        return False, (
            f"Shot name contains illegal character '{match.group()}'. "
            f"Avoid: \\ / : * ? \" < > |"
        )

    return True, ""


def validate_hip_saved() -> tuple[bool, str]:
    """Check that the HIP file is saved and not untitled.

    Returns (True, "") if OK.
    Returns (False, reason) with hard failure if untitled.
    Returns (True, warning) if saved but has unsaved changes.
    """
    import hou

    hip_path = hou.hipFile.path()

    if "untitled" in Path(hip_path).name.lower():
        return False, "Scene is unsaved (untitled). Please save the scene before packaging."

    if hou.hipFile.hasUnsavedChanges():
        return True, "Warning: scene has unsaved changes. Consider saving before packaging."

    return True, ""


def validate_shot_structure(shot_root: str) -> tuple[bool, str]:
    """Check that required shot directories exist under shot_root.

    Returns (True, "") if all present.
    Returns (False, message listing missing dirs) if any are missing.
    Ensures .placeholder files exist in each directory for Google Drive sync.
    """
    if not os.path.isdir(shot_root):
        return False, f"Shot root directory does not exist: {shot_root}"

    missing = []
    for dirname in REQUIRED_SHOT_DIRS:
        dirpath = os.path.join(shot_root, dirname)
        if not os.path.isdir(dirpath):
            missing.append(dirname)
        else:
            # Ensure .placeholder exists for Google Drive sync
            placeholder = os.path.join(dirpath, ".placeholder")
            if not os.path.exists(placeholder):
                with open(placeholder, "w", newline="\n") as f:
                    f.write("")

    if missing:
        return False, (
            f"Missing directories under {shot_root}: {', '.join(missing)}. "
            f"Create them to continue."
        )

    return True, ""


def validate_rop_connection(node) -> tuple[bool, str]:
    """Check if the node has a downstream Karma ROP connection.

    Returns (True, "") if a Karma ROP is found.
    Returns (True, warning) if no ROP found (non-blocking).
    """
    for output_node in node.outputs():
        if output_node.type().name() in ("usdrender_rop", "karma"):
            return True, ""
        # Recurse one level
        for grandchild in output_node.outputs():
            if grandchild.type().name() in ("usdrender_rop", "karma"):
                return True, ""

    return True, "Warning: no Karma ROP found downstream. Output paths may not be set."
