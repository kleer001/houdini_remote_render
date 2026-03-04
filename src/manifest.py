"""Manifest writer — human-readable packaging report.

Writes a plain-text manifest to Scripts/ documenting what was packaged.
"""

import os
from dataclasses import dataclass, field
from datetime import datetime

from src.platform_utils import ensure_dir


@dataclass
class ManifestData:
    """Data for the packaging manifest."""
    shot_name: str = ""
    houdini_version: str = ""
    generated_at: str = ""
    usdz_path: str = ""
    wrapper_path: str = ""
    textures_converted: list[tuple[str, str]] = field(default_factory=list)
    textures_skipped: list[str] = field(default_factory=list)
    caches_copied: list[tuple[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    total_usdz_size_mb: float = 0.0
    total_cache_size_mb: float = 0.0
    elapsed_seconds: float = 0.0


def write_manifest(output_path: str, data: ManifestData) -> None:
    """Write a human-readable manifest file.

    Args:
        output_path: Path to write the manifest file.
        data: ManifestData with all packaging information.
    """
    ensure_dir(os.path.dirname(output_path))

    lines = [
        f"Karma USD Packager — Manifest",
        f"{'=' * 50}",
        f"",
        f"Shot Name:        {data.shot_name}",
        f"Houdini Version:  {data.houdini_version}",
        f"Generated:        {data.generated_at}",
        f"Elapsed:          {data.elapsed_seconds:.1f}s",
        f"",
        f"Output Files",
        f"{'-' * 50}",
        f"USDZ:    {data.usdz_path}",
        f"Wrapper: {data.wrapper_path}",
        f"",
        f"USDZ Size:  {data.total_usdz_size_mb:.2f} MB",
        f"Cache Size: {data.total_cache_size_mb:.2f} MB",
        f"",
    ]

    if data.textures_converted:
        lines.append(f"Textures Converted ({len(data.textures_converted)})")
        lines.append(f"{'-' * 50}")
        for src, dst in data.textures_converted:
            lines.append(f"  {src}")
            lines.append(f"    -> {dst}")
        lines.append("")

    if data.textures_skipped:
        lines.append(f"Textures Skipped ({len(data.textures_skipped)})")
        lines.append(f"{'-' * 50}")
        for path in data.textures_skipped:
            lines.append(f"  {path}")
        lines.append("")

    if data.caches_copied:
        lines.append(f"Caches Copied ({len(data.caches_copied)})")
        lines.append(f"{'-' * 50}")
        for src, dst in data.caches_copied:
            lines.append(f"  {src}")
            lines.append(f"    -> {dst}")
        lines.append("")

    if data.warnings:
        lines.append(f"Warnings ({len(data.warnings)})")
        lines.append(f"{'-' * 50}")
        for w in data.warnings:
            lines.append(f"  ! {w}")
        lines.append("")

    with open(output_path, "w", newline="\n") as f:
        f.write("\n".join(lines))
