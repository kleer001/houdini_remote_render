"""Generate orchestration script that sequences cache jobs then render."""

import os
from datetime import datetime

from src.platform_utils import detect_hfs, hfs_source_block, make_executable


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
    hfs_path = hfs_path or detect_hfs()
    total = len(cache_scripts) + 1  # caches + render

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
{hfs_source_block(hfs_path)}
echo "=== Orchestrated Build: {shot_name} ==="
echo "Steps: {len(cache_scripts)} cache(s) + 1 render"
echo ""

{steps_block}
echo "=== All {total} steps complete ==="
"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="\n") as f:
        f.write(script)

    make_executable(output_path)
