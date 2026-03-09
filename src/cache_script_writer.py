"""Generate hbatch launch script for remote File Cache execution."""

import os
import stat
from datetime import datetime


def write_cache_script(
    output_path: str,
    shot_name: str,
    hip_filename: str,
    cache_node_path: str,
    frame_start: int,
    frame_end: int,
) -> None:
    """Write a bash script that runs the File Cache via hbatch.

    Args:
        output_path: Full path to write the script.
        shot_name: Shot identifier (for comments).
        hip_filename: Name of the .hip file in Scenes/.
        cache_node_path: Houdini node path to render.
        frame_start: First frame number.
        frame_end: Last frame number.
    """
    timestamp = datetime.now().isoformat(timespec="seconds")

    script = f"""#!/bin/bash
# Remote File Cache — hbatch launcher
# Shot: {shot_name}
# Generated: {timestamp}

set -e
cd "$(dirname "$0")/.."

echo "Starting cache: {shot_name}"
echo "Frames: {frame_start}-{frame_end}"
echo "Node: {cache_node_path}"
echo ""

hbatch -c "mread Scenes/{hip_filename}; render -f {frame_start} {frame_end} {cache_node_path}; quit"

echo ""
echo "Cache complete."
"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="\n") as f:
        f.write(script)

    # Make executable
    st = os.stat(output_path)
    os.chmod(output_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
