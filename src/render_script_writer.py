"""Generate husk launch script for remote Karma rendering."""

import os
import stat
from datetime import datetime


def _detect_hfs() -> str | None:
    """Return HFS path from environment or None."""
    hfs = os.environ.get("HFS")
    if hfs and os.path.isdir(hfs):
        return hfs
    return None


def write_render_script(
    output_path: str,
    shot_name: str,
    wrapper_filename: str,
    frame_start: int,
    frame_end: int,
    renderer: str = "BRAY_HdKarma",
    engine: str | None = None,
    restart_delegate: int | None = None,
    exr_mode: int | None = None,
    autotile: bool = False,
    timelimit: float | None = None,
    snapshot: float | None = None,
    oiio_mem_pct: int | None = None,
    extra_flags: list[str] | None = None,
    hfs_path: str | None = None,
) -> None:
    """Write a bash script that renders the packaged USD via husk.

    Args:
        output_path: Full path to write the script.
        shot_name: Shot identifier (for comments).
        wrapper_filename: Name of the wrapper .usda in Scenes/.
        frame_start: First frame number.
        frame_end: Last frame number.
        renderer: Hydra render delegate name.
        engine: Karma engine — "xpu" or "cpu". If None, uses renderer default.
        restart_delegate: Restart render delegate every N frames (memory
            management). Auto-set to 1 for sequences if not provided.
        exr_mode: EXR output mode — 0=legacy, 1=modern.
        autotile: Enable tiled rendering.
        timelimit: Per-frame time limit in seconds.
        snapshot: Progressive snapshot interval in seconds.
        oiio_mem_pct: OIIO texture cache max memory percentage (0-100).
        extra_flags: Additional husk CLI flags passed verbatim.
        hfs_path: Houdini install path ($HFS). Auto-detected if not provided.
    """
    timestamp = datetime.now().isoformat(timespec="seconds")
    hfs_path = hfs_path or _detect_hfs()
    is_sequence = frame_end - frame_start > 0

    # Smart default: restart delegate every frame for sequences
    if restart_delegate is None and is_sequence:
        restart_delegate = 1

    # Build husk flags
    flags = []
    flags.append(f"--renderer {renderer}")

    if engine:
        flags.append(f"--engine {engine}")

    flags.append("--make-output-path")
    flags.append("--headlight none")

    if restart_delegate is not None:
        flags.append(f"--restart-delegate {restart_delegate}")

    if exr_mode is not None:
        flags.append(f"--exrmode {exr_mode}")

    if autotile:
        flags.append("--autotile")

    if timelimit is not None:
        flags.append(f"--timelimit {timelimit}")

    if snapshot is not None:
        flags.append(f"--snapshot {snapshot}")

    if oiio_mem_pct is not None:
        flags.append(f"--oiio-max-memory-percent {oiio_mem_pct}")

    if extra_flags:
        flags.extend(extra_flags)

    frame_count = frame_end - frame_start + 1
    flags.append(f"-f {frame_start}")
    flags.append(f"-n {frame_count}")
    flags.append("-i 1")

    flags_str = " \\\n    ".join(flags)

    # Build HFS setup block — always source to get full environment
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
# HFS not known at packaging time — husk must be on PATH
"""

    script = f"""#!/bin/bash
# Remote Karma Render — husk launcher
# Shot: {shot_name}
# Generated: {timestamp}

set -e
cd "$(dirname "$0")/.."
{hfs_block}
echo "Starting render: {shot_name}"
echo "Frames: {frame_start}-{frame_end}"
echo "Renderer: {renderer}"
echo ""

# husk resolves productName paths relative to CWD, so run from Scenes/
cd Scenes

husk \\
    {flags_str} \\
    "{wrapper_filename}"

echo ""
echo "Render complete."
"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="\n") as f:
        f.write(script)

    # Make executable
    st = os.stat(output_path)
    os.chmod(output_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
