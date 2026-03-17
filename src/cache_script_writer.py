"""Generate hython launch script for remote File Cache execution.

Uses hython instead of hbatch because filecache::2.0 is a SOP, not a ROP —
hbatch's ``render`` command only works with ROP nodes and silently skips SOPs.
"""

import os
from datetime import datetime

from src.platform_utils import detect_hfs, hfs_source_block, make_executable, copy_launcher


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
    hfs_path = hfs_path or detect_hfs()

    script = f"""#!/bin/bash
# Remote File Cache — hython launcher
# Shot: {shot_name}
# Generated: {timestamp}

set -e
cd "$(dirname "$0")/.."
{hfs_source_block(hfs_path)}
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
for p in ("trange", "f1", "f2", "f3"):
    node.parm(p).deleteAllKeyframes()
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

    make_executable(output_path)

    # Cross-platform Python launcher
    copy_launcher("run_cache.py", os.path.dirname(output_path))
