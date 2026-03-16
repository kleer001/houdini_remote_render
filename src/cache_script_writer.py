"""Generate hython launch script for remote File Cache execution.

Uses hython instead of hbatch because filecache::2.0 is a SOP, not a ROP —
hbatch's ``render`` command only works with ROP nodes and silently skips SOPs.
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


def write_cache_script(
    output_path: str,
    shot_name: str,
    hip_filename: str,
    cache_node_path: str,
    frame_start: int,
    frame_end: int,
    hfs_path: str | None = None,
) -> None:
    """Write a bash script that runs the File Cache via hython.

    Args:
        output_path: Full path to write the script.
        shot_name: Shot identifier (for comments).
        hip_filename: Name of the .hip file in Scenes/.
        cache_node_path: Houdini node path to the filecache node.
        frame_start: First frame number.
        frame_end: Last frame number.
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
# HFS not known at packaging time — hython must be on PATH
"""

    script = f"""#!/bin/bash
# Remote File Cache — hython launcher
# Shot: {shot_name}
# Generated: {timestamp}

set -e
cd "$(dirname "$0")/.."
{hfs_block}
echo "Starting cache: {shot_name}"
echo "Frames: {frame_start}-{frame_end}"
echo "Node: {cache_node_path}"
echo ""

hython -c '
import hou, sys
hou.hipFile.load("Scenes/{hip_filename}")
node = hou.node("{cache_node_path}")
if node is None:
    print("ERROR: Node {cache_node_path} not found")
    sys.exit(1)
node.parm("trange").set(1)
node.parm("f1").set({frame_start})
node.parm("f2").set({frame_end})
node.parm("f3").set(1)
node.parm("execute").pressButton()
'

echo ""
echo "Cache complete."
"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="\n") as f:
        f.write(script)

    # Make executable
    st = os.stat(output_path)
    os.chmod(output_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
