"""Manifest writer for Remote Redshift Render (USD) packaging reports."""

import os
from dataclasses import dataclass, field

from src.platform_utils import ensure_dir


@dataclass
class RedshiftManifestData:
    """Data for the Redshift USD render packaging manifest."""
    shot_name: str = ""
    folder_name: str = ""
    houdini_version: str = ""
    generated_at: str = ""
    elapsed_seconds: float = 0.0
    frame_start: int = 0
    frame_end: int = 0
    frame_inc: int = 1
    resolution: tuple[int, int] = (1920, 1080)
    camera: str = ""
    aov_count: int = 0
    gpu_device: str = "all"
    texture_cache_gb: int | None = None
    ocio_config: str = ""
    usdz_size_mb: float = 0.0
    wrapper_path: str = ""
    backup_zip_path: str = ""
    backup_zip_size_mb: float = 0.0
    warnings: list[str] = field(default_factory=list)


def write_redshift_manifest(output_path: str, data: RedshiftManifestData) -> None:
    """Write a human-readable manifest for the Redshift USD render package.

    Args:
        output_path: Path to write the manifest file.
        data: RedshiftManifestData with all packaging information.
    """
    ensure_dir(os.path.dirname(output_path))

    frame_count = 0
    if data.frame_inc > 0:
        frame_count = int((data.frame_end - data.frame_start) / data.frame_inc) + 1

    lines = [
        "Remote Redshift Render Packager — Manifest",
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
        f"Renderer:   Redshift (redshiftUsdCmdLine)",
        f"Resolution: {data.resolution[0]}x{data.resolution[1]}",
        f"Camera:     {data.camera}",
        f"AOVs:       {data.aov_count}",
        f"GPU Device: {data.gpu_device}",
    ]

    if data.texture_cache_gb is not None:
        lines.append(f"Tex Cache:  {data.texture_cache_gb} GB")

    if data.ocio_config:
        lines.append(f"OCIO:       {data.ocio_config}")

    lines.extend([
        "",
        "USD Package",
        "-" * 50,
        f"USDZ Size:  {data.usdz_size_mb:.2f} MB",
        f"Wrapper:    {data.wrapper_path}",
        "",
        "Backup",
        "-" * 50,
        f"Archive:    {data.backup_zip_path}",
        f"Size:       {data.backup_zip_size_mb:.2f} MB",
        "",
    ])

    if data.warnings:
        lines.append(f"Warnings ({len(data.warnings)})")
        lines.append("-" * 50)
        for w in data.warnings:
            lines.append(f"  ! {w}")
        lines.append("")

    with open(output_path, "w", newline="\n") as f:
        f.write("\n".join(lines))
