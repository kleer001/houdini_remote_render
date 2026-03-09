"""Write machine-readable cache_info.txt for remote execution."""

import os
from datetime import datetime


def write_cache_info(
    output_path: str,
    shot_name: str,
    folder_name: str,
    frame_start: float,
    frame_end: float,
    frame_inc: float,
    substeps: int,
    cache_format: str,
    cache_node_path: str,
    cache_output_pattern: str,
    hip_filename: str,
    houdini_version: str = "",
) -> None:
    """Write cache_info.txt with all metadata needed for remote execution.

    Args:
        output_path: Full path to write the file.
        shot_name: Shot identifier.
        folder_name: Package folder name (shot_P1T1_v001).
        frame_start: First frame.
        frame_end: Last frame.
        frame_inc: Frame increment.
        substeps: Substeps per frame.
        cache_format: File extension (e.g. ".bgeo.sc").
        cache_node_path: Houdini node path to the File Cache SOP.
        cache_output_pattern: Output file pattern relative to package root.
        hip_filename: Name of the .hip file in Scenes/.
        houdini_version: Houdini version string.
    """
    frame_count = int((frame_end - frame_start) / frame_inc) + 1 if frame_inc > 0 else 0

    lines = [
        f"shot_name={shot_name}",
        f"folder_name={folder_name}",
        f"startframe={int(frame_start)}",
        f"endframe={int(frame_end)}",
        f"frameinc={int(frame_inc)}",
        f"substeps={substeps}",
        f"framecount={frame_count}",
        f"cache_format={cache_format}",
        f"cache_node={cache_node_path}",
        f"cache_output={cache_output_pattern}",
        f"hipfile=Scenes/{hip_filename}",
        f"houdini_version={houdini_version}",
        f"generated_at={datetime.now().isoformat(timespec='seconds')}",
    ]

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
