"""Generate hbatch launch script for remote Mantra rendering.

Uses hbatch with the ``render`` HScript command because Mantra is a ROP node.
Syntax: ``render -Va -f start end -i inc rop_path`` (piped to hbatch stdin).
"""

import os
from datetime import datetime

from src.platform_utils import detect_hfs, hfs_source_block, make_executable


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
    hfs_path = hfs_path or detect_hfs()

    script = f"""#!/bin/bash
# Remote Mantra Render — hbatch launcher
# Shot: {shot_name}
# Generated: {timestamp}

set -e
cd "$(dirname "$0")/.."
{hfs_source_block(hfs_path)}
echo "Starting Mantra render: {shot_name}"
echo "Frames: {frame_start}-{frame_end} (inc {frame_inc})"
echo "ROP: {rop_node_path}"
echo ""

cd Scenes
echo 'render -Va -f {frame_start} {frame_end} -i {frame_inc} {rop_node_path}' | hbatch "{hip_filename}"

echo ""
echo "Render complete."
"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="\n") as f:
        f.write(script)

    make_executable(output_path)
