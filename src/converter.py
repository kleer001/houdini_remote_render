"""Texture converter — convert source textures to mipmapped format using imaketx.

Handles individual textures, batch conversion, and UDIM tile sets.
"""

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from src.platform_utils import get_imaketx_path, ensure_dir
from src.classifier import expand_udim_pattern

# Extensions that are already optimal and don't need conversion
OPTIMAL_EXTENSIONS = frozenset([".rat"])

# Default output format for imaketx
DEFAULT_FORMAT = "OpenEXR"

# Map of imaketx format names to file extensions
FORMAT_EXTENSIONS = {
    "OpenEXR": ".exr",
    "RAT": ".rat",
    "TIFF": ".tif",
}


@dataclass
class ConversionReport:
    """Results of a batch texture conversion."""
    converted: list[tuple[str, str]] = field(default_factory=list)  # (src, dst)
    skipped: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)  # (src, error)


def needs_conversion(path: str) -> bool:
    """Return True if the texture needs conversion to mipmapped format."""
    ext = os.path.splitext(path)[1].lower()
    return ext not in OPTIMAL_EXTENSIONS


def convert_texture(src: str, dst_dir: str, fmt: str = DEFAULT_FORMAT) -> str:
    """Convert a single texture to mipmapped format using imaketx.

    Args:
        src: Source texture file path.
        dst_dir: Directory for the output file.
        fmt: Output format — "OpenEXR", "RAT", or "TIFF".

    Returns:
        Path of the converted file.

    Raises:
        RuntimeError: If conversion fails.
    """
    ensure_dir(dst_dir)

    imaketx = get_imaketx_path()
    ext = FORMAT_EXTENSIONS.get(fmt, ".exr")
    base_name = Path(src).stem + ext
    dst = os.path.join(dst_dir, base_name)

    cmd = [imaketx, src, dst, "--format", fmt]

    result = subprocess.run(cmd, capture_output=True, text=True, shell=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"imaketx failed for {src}: {result.stderr.strip() or result.stdout.strip()}"
        )

    return dst


def convert_all(
    textures: list[str],
    dst_dir: str,
    fmt: str = DEFAULT_FORMAT,
    dry_run: bool = False,
) -> ConversionReport:
    """Convert a batch of textures, skipping already-optimal formats.

    Args:
        textures: List of source texture paths.
        dst_dir: Output directory for converted textures.
        fmt: Output format for imaketx.
        dry_run: If True, report what would be done without converting.

    Returns:
        ConversionReport with converted, skipped, and failed lists.
    """
    report = ConversionReport()

    for src in textures:
        if not needs_conversion(src):
            report.skipped.append(src)
            continue

        if dry_run:
            ext = FORMAT_EXTENSIONS.get(fmt, ".exr")
            dst = os.path.join(dst_dir, Path(src).stem + ext)
            report.converted.append((src, dst))
            continue

        try:
            dst = convert_texture(src, dst_dir, fmt=fmt)
            report.converted.append((src, dst))
        except RuntimeError as e:
            report.failed.append((src, str(e)))

    return report


def convert_udim_set(
    pattern: str,
    dst_dir: str,
    fmt: str = DEFAULT_FORMAT,
    dry_run: bool = False,
) -> str:
    """Expand a UDIM pattern, convert each tile, return new pattern in dst_dir.

    Args:
        pattern: Path with <UDIM> placeholder.
        dst_dir: Output directory.
        fmt: Output format.
        dry_run: If True, don't actually convert.

    Returns:
        New pattern string pointing to dst_dir.
    """
    tiles = expand_udim_pattern(pattern)
    ext = FORMAT_EXTENSIONS.get(fmt, ".exr")

    for tile in tiles:
        if not dry_run:
            convert_texture(tile, dst_dir, fmt=fmt)

    # Build new pattern in dst_dir
    src_stem = Path(pattern.replace("<UDIM>", "UDIM_PLACEHOLDER")).stem
    new_stem = src_stem.replace("UDIM_PLACEHOLDER", "<UDIM>")
    return os.path.join(dst_dir, new_stem + ext)
