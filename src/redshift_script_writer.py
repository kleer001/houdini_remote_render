"""Generate redshiftUsdCmdLine launch script for remote USD rendering.

Uses ``redshiftUsdCmdLine`` which includes all USD libs — no Houdini
or husk required on the render machine.
"""

import os
from datetime import datetime

from src.platform_utils import detect_redshift, redshift_env_block, make_executable


def write_redshift_script(
    output_path: str,
    shot_name: str,
    wrapper_filename: str,
    frame_start: int,
    frame_end: int,
    frame_inc: int = 1,
    gpu_device: str = "all",
    texture_cache_gb: int | None = None,
    cache_path: str | None = None,
    ocio_config: str | None = None,
    skip_postfx: bool = False,
    verbose: int = 2,
    restart_delegate: bool = False,
    extra_flags: list[str] | None = None,
    redshift_path: str | None = None,
) -> None:
    """Write a bash script that renders USD via redshiftUsdCmdLine.

    Args:
        output_path: Full path to write the script.
        shot_name: Shot identifier (for comments).
        wrapper_filename: Name of the wrapper .usda (or .usdz) in Scenes/.
        frame_start: First frame number.
        frame_end: Last frame number (inclusive).
        frame_inc: Frame increment (default 1).
        gpu_device: GPU device ordinal or "all" (default "all").
        texture_cache_gb: Texture cache budget in GB (optional).
        cache_path: Redshift cache folder (optional).
        ocio_config: Path to OCIO config file (optional).
        skip_postfx: Skip post-processing (default False).
        verbose: Verbosity level 0-6 (default 2).
        restart_delegate: Restart render delegate every frame (default False).
        extra_flags: Additional CLI flags passed verbatim (optional).
        redshift_path: Redshift install path. Auto-detected if not provided.
    """
    timestamp = datetime.now().isoformat(timespec="seconds")
    redshift_path = redshift_path or detect_redshift()

    # Build redshiftUsdCmdLine flags
    frame_count = int((frame_end - frame_start) / frame_inc) + 1
    flags = []

    flags.append(f"-f {frame_start}")
    flags.append(f"-n {frame_count}")
    if frame_inc != 1:
        flags.append(f"-i {frame_inc}")

    flags.append(f"-device {gpu_device}")

    if texture_cache_gb is not None:
        flags.append(f"-texturecachebudget {texture_cache_gb}")

    if cache_path is not None:
        flags.append(f'-cachepath "{cache_path}"')

    if ocio_config is not None:
        flags.append(f'-ocioconfig "{ocio_config}"')

    if skip_postfx:
        flags.append("-skippostfx")

    if verbose != 2:
        flags.append(f"-V {verbose}")

    if restart_delegate:
        flags.append("-restart-delegate")

    if extra_flags:
        flags.extend(extra_flags)

    flags_str = " \\\n    ".join(flags)

    script = f"""#!/bin/bash
# Remote Redshift Render — redshiftUsdCmdLine launcher
# Shot: {shot_name}
# Generated: {timestamp}

set -e
cd "$(dirname "$0")/.."
{redshift_env_block(redshift_path)}
echo "Starting Redshift render: {shot_name}"
echo "Frames: {frame_start}-{frame_end} (inc {frame_inc})"
echo "GPU device: {gpu_device}"
echo ""

# redshiftUsdCmdLine resolves productName paths relative to CWD
cd Scenes
mkdir -p ../Output

redshiftUsdCmdLine \\
    "{wrapper_filename}" \\
    {flags_str}

echo ""
echo "Render complete."
"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="\n") as f:
        f.write(script)

    make_executable(output_path)
