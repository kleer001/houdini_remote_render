"""Write machine-readable render_info.txt for remote Redshift USD execution."""

import os
from datetime import datetime


def write_redshift_info(
    output_path: str,
    shot_name: str,
    folder_name: str,
    frame_start: int,
    frame_end: int,
    frame_inc: int,
    resolution: tuple[int, int],
    camera: str,
    gpu_device: str = "all",
    texture_cache_gb: int | None = None,
    ocio_config: str | None = None,
    usd_file: str = "",
    aov_count: int = 0,
    houdini_version: str = "",
) -> None:
    """Write render_info.txt with all metadata needed for remote execution.

    Args:
        output_path: Full path to write the file.
        shot_name: Shot identifier.
        folder_name: Package folder name (shot_P1T1_v001).
        frame_start: First frame.
        frame_end: Last frame.
        frame_inc: Frame increment.
        resolution: (width, height) tuple.
        camera: Camera prim path.
        gpu_device: GPU device setting.
        texture_cache_gb: Texture cache budget in GB (optional).
        ocio_config: OCIO config path (optional).
        usd_file: USD filename in Scenes/.
        aov_count: Number of AOVs/render vars.
        houdini_version: Houdini version string.
    """
    frame_count = int((frame_end - frame_start) / frame_inc) + 1 if frame_inc > 0 else 0

    lines = [
        f"shot_name={shot_name}",
        f"folder_name={folder_name}",
        f"renderer=redshift",
        f"command=redshiftUsdCmdLine",
        f"startframe={frame_start}",
        f"endframe={frame_end}",
        f"frameinc={frame_inc}",
        f"framecount={frame_count}",
        f"resolution={resolution[0]}x{resolution[1]}",
        f"camera={camera}",
        f"gpu_device={gpu_device}",
        f"aov_count={aov_count}",
        f"usd_file={usd_file}",
    ]

    if texture_cache_gb is not None:
        lines.append(f"texture_cache_gb={texture_cache_gb}")

    if ocio_config:
        lines.append(f"ocio_config={ocio_config}")

    lines.extend([
        f"houdini_version={houdini_version}",
        f"generated_at={datetime.now().isoformat(timespec='seconds')}",
    ])

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
