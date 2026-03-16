"""Write machine-readable render_info.txt for remote Mantra execution."""

import os
from datetime import datetime


def write_mantra_info(
    output_path: str,
    shot_name: str,
    folder_name: str,
    frame_start: float,
    frame_end: float,
    frame_inc: float,
    resolution: tuple[int, int],
    pixel_samples: tuple[int, int],
    render_engine: str,
    camera: str,
    rop_node_path: str,
    output_picture: str,
    hip_filename: str,
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
        pixel_samples: (x, y) pixel samples.
        render_engine: Mantra render engine name.
        camera: Camera path.
        rop_node_path: Houdini node path to the Mantra ROP.
        output_picture: Output file pattern relative to package root.
        hip_filename: Name of the .hip file in Scenes/.
        houdini_version: Houdini version string.
    """
    frame_count = int((frame_end - frame_start) / frame_inc) + 1 if frame_inc > 0 else 0

    lines = [
        f"shot_name={shot_name}",
        f"folder_name={folder_name}",
        f"renderer=mantra",
        f"render_engine={render_engine}",
        f"startframe={int(frame_start)}",
        f"endframe={int(frame_end)}",
        f"frameinc={int(frame_inc)}",
        f"framecount={frame_count}",
        f"resolution={resolution[0]}x{resolution[1]}",
        f"pixel_samples={pixel_samples[0]}x{pixel_samples[1]}",
        f"camera={camera}",
        f"rop_node={rop_node_path}",
        f"output_picture={output_picture}",
        f"hipfile=Scenes/{hip_filename}",
        f"houdini_version={houdini_version}",
        f"generated_at={datetime.now().isoformat(timespec='seconds')}",
    ]

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
