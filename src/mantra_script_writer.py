"""Generate hbatch launch script for remote Mantra rendering.

Uses hbatch with the ``render`` command because Mantra is a ROP node —
hbatch natively supports ROP rendering via ``render -f start end inc rop_path``.
"""

import os
import stat
from datetime import datetime


def _detect_hfs() -> str | None:
    """Return HFS path from environment or None."""
    hfs = os.environ.get("HFS")
    if hfs and os.path.isdir(hfs):
        return hfs
    return None


def write_mantra_script(
    output_path: str,
    shot_name: str,
    hip_filename: str,
    rop_node_path: str,
    frame_start: int,
    frame_end: int,
    frame_inc: int = 1,
    hfs_path: str | None = None,
) -> None:
    """Write a bash script that renders via hbatch.

    Args:
        output_path: Full path to write the script.
        shot_name: Shot identifier (for comments).
        hip_filename: Name of the .hip file in Scenes/.
        rop_node_path: Houdini node path to the Mantra ROP.
        frame_start: First frame number.
        frame_end: Last frame number.
        frame_inc: Frame increment (default 1).
        hfs_path: Houdini install path ($HFS). Auto-detected if not provided.
    """
    timestamp = datetime.now().isoformat(timespec="seconds")
    hfs_path = hfs_path or _detect_hfs()

    if hfs_path:
        hfs_block = f"""
# Source Houdini environment
_HFS="${{HFS:-{hfs_path}}}"
_SHOT_ROOT="$(pwd)"
if [ -d "$_HFS" ]; then
    cd "$_HFS"
    source ./houdini_setup_bash
    cd "$_SHOT_ROOT"
fi
"""
    else:
        hfs_block = """
# HFS not known at packaging time — hbatch must be on PATH
"""

    script = f"""#!/bin/bash
# Remote Mantra Render — hbatch launcher
# Shot: {shot_name}
# Generated: {timestamp}

set -e
cd "$(dirname "$0")/.."
{hfs_block}
echo "Starting Mantra render: {shot_name}"
echo "Frames: {frame_start}-{frame_end} (inc {frame_inc})"
echo "ROP: {rop_node_path}"
echo ""

cd Scenes
hbatch -c "render -Va -f {frame_start} {frame_end} {frame_inc} {rop_node_path}" "{hip_filename}"

echo ""
echo "Render complete."
"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="\n") as f:
        f.write(script)

    # Make executable
    st = os.stat(output_path)
    os.chmod(output_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
