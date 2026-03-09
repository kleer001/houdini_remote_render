"""Manifest writer for Remote File Cache packaging reports."""

import os
from dataclasses import dataclass, field

from src.platform_utils import ensure_dir


@dataclass
class CacheManifestData:
    """Data for the cache packaging manifest."""
    shot_name: str = ""
    folder_name: str = ""
    houdini_version: str = ""
    generated_at: str = ""
    elapsed_seconds: float = 0.0
    frame_start: int = 0
    frame_end: int = 0
    frame_inc: int = 1
    substeps: int = 1
    cache_format: str = ".bgeo.sc"
    cache_node_path: str = ""
    cache_output_pattern: str = ""
    hip_path: str = ""
    hip_size_mb: float = 0.0
    backup_zip_path: str = ""
    backup_zip_size_mb: float = 0.0
    warnings: list[str] = field(default_factory=list)


def write_cache_manifest(output_path: str, data: CacheManifestData) -> None:
    """Write a human-readable manifest for the cache package.

    Args:
        output_path: Path to write the manifest file.
        data: CacheManifestData with all packaging information.
    """
    ensure_dir(os.path.dirname(output_path))

    frame_count = 0
    if data.frame_inc > 0:
        frame_count = int((data.frame_end - data.frame_start) / data.frame_inc) + 1

    lines = [
        "Remote File Cache Packager — Manifest",
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
        f"Substeps:   {data.substeps}",
        f"Frames:     {frame_count}",
        "",
        "Cache Setup",
        "-" * 50,
        f"Node:       {data.cache_node_path}",
        f"Format:     {data.cache_format}",
        f"Output:     {data.cache_output_pattern}",
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
