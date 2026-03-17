"""Generate mantra standalone launch script for IFD-based remote rendering.

Uses the ``mantra`` standalone renderer which consumes IFD files using free
render tokens — no Houdini license required on the remote machine.
"""

import os
from datetime import datetime

from src.platform_utils import detect_hfs, hfs_source_block, hfs_bat_block, make_executable


def write_mantra_script(
    output_path: str,
    shot_name: str,
    ifd_pattern: str,
    frame_start: int,
    frame_end: int,
    frame_inc: int = 1,
    hfs_path: str | None = None,
) -> None:
    """Write a bash script that renders IFDs via mantra standalone.

    Args:
        output_path: Full path to write the script.
        shot_name: Shot identifier (for comments).
        ifd_pattern: printf-style IFD filename pattern (e.g. "shot.%04d.ifd").
        frame_start: First frame number.
        frame_end: Last frame number.
        frame_inc: Frame increment (default 1).
        hfs_path: Houdini install path ($HFS). Auto-detected if not provided.
    """
    timestamp = datetime.now().isoformat(timespec="seconds")
    hfs_path = hfs_path or detect_hfs()

    script = f"""#!/bin/bash
# Remote Mantra Render — mantra standalone launcher (IFD)
# Shot: {shot_name}
# Generated: {timestamp}

set -e
cd "$(dirname "$0")/.."
{hfs_source_block(hfs_path)}
export HOUDINI_TEXTURE_PATH="$(pwd)/Textures:&"

echo "Starting Mantra render: {shot_name}"
echo "Frames: {frame_start}-{frame_end} (inc {frame_inc})"
echo "IFD pattern: {ifd_pattern}"
echo ""

cd IFDs
for frame in $(seq {frame_start} {frame_inc} {frame_end}); do
    ifd=$(printf "{ifd_pattern}" "$frame")
    echo "Rendering frame $frame: $ifd"
    mantra -V 2a -j 0 -f "$ifd"
done

echo ""
echo "Render complete."
"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="\n") as f:
        f.write(script)

    make_executable(output_path)

    # Windows companion
    # Batch for loop: for /L %%f in (start,inc,end) do ...
    # printf pattern conversion: %04d → batch padding via set with leading zeros
    bat_path = output_path.rsplit(".sh", 1)[0] + ".bat"
    bat = f"""@echo off
rem Remote Mantra Render — mantra standalone launcher (IFD)
rem Shot: {shot_name}
rem Generated: {timestamp}

cd /d "%~dp0.."
{hfs_bat_block(hfs_path)}
set "HOUDINI_TEXTURE_PATH=%CD%\\Textures;&"

echo Starting Mantra render: {shot_name}
echo Frames: {frame_start}-{frame_end} (inc {frame_inc})
echo IFD pattern: {ifd_pattern}
echo.

cd IFDs
setlocal enabledelayedexpansion
for /L %%f in ({frame_start},{frame_inc},{frame_end}) do (
    set "frame=000000%%f"
    set "padded=!frame:~-4!"
    call set "ifd={ifd_pattern}" & rem printf pattern replaced below
    echo Rendering frame %%f
    mantra -V 2a -j 0 -f "{ifd_pattern.replace('%04d', '!padded!')}"
)
endlocal

echo.
echo Render complete.
"""
    with open(bat_path, "w", newline="\r\n") as f:
        f.write(bat)
