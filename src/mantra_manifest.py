"""Manifest writer for Remote Mantra Render packaging reports."""

import os
from dataclasses import dataclass, field

from src.platform_utils import ensure_dir


@dataclass
class MantraManifestData:
    """Data for the Mantra render packaging manifest."""
    shot_name: str = ""
    folder_name: str = ""
    houdini_version: str = ""
    generated_at: str = ""
    elapsed_seconds: float = 0.0
    frame_start: int = 0
    frame_end: int = 0
    frame_inc: int = 1
    resolution: tuple[int, int] = (1280, 720)
    pixel_samples: tuple[int, int] = (3, 3)
    render_engine: str = "raytrace"
    camera: str = ""
    aov_count: int = 0
    rop_node_path: str = ""
    output_picture: str = ""
    hip_path: str = ""
    hip_size_mb: float = 0.0
    backup_zip_path: str = ""
    backup_zip_size_mb: float = 0.0
    warnings: list[str] = field(default_factory=list)


def write_mantra_manifest(output_path: str, data: MantraManifestData) -> None:
    """Write a human-readable manifest for the Mantra render package.

    Args:
        output_path: Path to write the manifest file.
        data: MantraManifestData with all packaging information.
    """
    ensure_dir(os.path.dirname(output_path))

    frame_count = 0
    if data.frame_inc > 0:
        frame_count = int((data.frame_end - data.frame_start) / data.frame_inc) + 1

    lines = [
        "Remote Mantra Render Packager — Manifest",
        "=" * 50,
        "",
        f"Shot Name:        {data.shot_name}",
        f"Folder:           {data.folder_name}",
        f"Houdini Version:  {data.houdini_version}",
        f"Generated:        {data.generated_at}",
        f"Elapsed:          {data.elapsed_seconds:.1f}s",
        "",
        "Frame Range",
        "-" * 50,
        f"Start:      {data.frame_start}",
        f"End:        {data.frame_end}",
        f"Increment:  {data.frame_inc}",
        f"Frames:     {frame_count}",
        "",
        "Render Setup",
        "-" * 50,
        f"ROP:        {data.rop_node_path}",
        f"Engine:     {data.render_engine}",
        f"Resolution: {data.resolution[0]}x{data.resolution[1]}",
        f"Samples:    {data.pixel_samples[0]}x{data.pixel_samples[1]}",
        f"Camera:     {data.camera}",
        f"AOVs:       {data.aov_count}",
        f"Output:     {data.output_picture}",
        "",
        "Files",
        "-" * 50,
        f"HIP File:   {data.hip_path}",
        f"HIP Size:   {data.hip_size_mb:.2f} MB",
        f"Backup:     {data.backup_zip_path}",
        f"Backup Size:{data.backup_zip_size_mb:.2f} MB",
        "",
    ]

    if data.warnings:
        lines.append(f"Warnings ({len(data.warnings)})")
        lines.append("-" * 50)
        for w in data.warnings:
            lines.append(f"  ! {w}")
        lines.append("")

    with open(output_path, "w", newline="\n") as f:
        f.write("\n".join(lines))
