"""Generate orchestration script that sequences cache jobs then render."""

import os
import stat
from datetime import datetime


def _detect_hfs() -> str | None:
    """Return HFS path from environment or None."""
    hfs = os.environ.get("HFS")
    if hfs and os.path.isdir(hfs):
        return hfs
    return None


def write_orchestration_script(
    output_path: str,
    shot_name: str,
    cache_scripts: list[tuple[str, str]],
    render_script_filename: str = "run_render.sh",
    hfs_path: str | None = None,
) -> None:
    """Write ``run_all.sh`` that runs cache scripts in order, then renders.

    Args:
        output_path: Full path to write the script.
        shot_name: Shot identifier.
        cache_scripts: Ordered list of ``(label, script_filename)`` tuples.
            The order must match the topological sort (dependencies first).
        render_script_filename: Filename of the render script in Scripts/.
        hfs_path: Houdini install path. Auto-detected if not provided.
    """
    timestamp = datetime.now().isoformat(timespec="seconds")
    hfs_path = hfs_path or _detect_hfs()
    total = len(cache_scripts) + 1  # caches + render

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
# HFS not known at packaging time — hython/husk must be on PATH
"""

    # Build step blocks
    steps: list[str] = []
    for i, (label, filename) in enumerate(cache_scripts, 1):
        steps.append(f"""\
# Step {i}/{total}: Cache — {label}
echo "--- [{i}/{total}] Cache: {label} ---"
bash "Scripts/{filename}"
echo "--- [{i}/{total}] complete ---"
echo """"")

    steps.append(f"""\
# Step {total}/{total}: Render
echo "--- [{total}/{total}] Render ---"
bash "Scripts/{render_script_filename}"
echo "--- [{total}/{total}] complete ---"
echo """"")

    steps_block = "\n".join(steps)

    script = f"""#!/bin/bash
# Orchestrated Build — cache + render
# Shot: {shot_name}
# Generated: {timestamp}
# Steps: {len(cache_scripts)} cache job(s) + 1 render

set -e
cd "$(dirname "$0")/.."
{hfs_block}
echo "=== Orchestrated Build: {shot_name} ==="
echo "Steps: {len(cache_scripts)} cache(s) + 1 render"
echo ""

{steps_block}
echo "=== All {total} steps complete ==="
"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="\n") as f:
        f.write(script)

    st = os.stat(output_path)
    os.chmod(output_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
