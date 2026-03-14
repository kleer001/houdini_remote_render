"""Texture converter — convert source textures to mipmapped format using imaketx.

Handles individual textures, batch conversion, and UDIM tile sets.
"""

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from src.platform_utils import get_imaketx_path, get_iconvert_path, ensure_dir
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


def convert_rat_for_usdz(flat_usda_path: str, staging_dir: str) -> list[tuple[str, str]]:
    """Convert .rat textures to .exr so they can be bundled in USDZ.

    Scans the flattened USD layer for .rat asset paths, converts each
    to .exr using iconvert, and rewrites paths in the layer.

    Args:
        flat_usda_path: Path to the flattened .usda file.
        staging_dir: Directory for converted texture files.

    Returns:
        List of (original_path, converted_path) tuples.
    """
    from pxr import Sdf, UsdUtils

    layer = Sdf.Layer.FindOrOpen(flat_usda_path)

    # Collect .rat paths
    rat_paths = set()
    def _collect(path):
        if path and os.path.splitext(path)[1].lower() == ".rat":
            rat_paths.add(path)
        return path
    UsdUtils.ModifyAssetPaths(layer, _collect)

    if not rat_paths:
        return []

    iconvert = get_iconvert_path()
    tex_dir = os.path.join(staging_dir, "textures_exr")
    ensure_dir(tex_dir)

    converted = []
    path_map = {}
    for rat_path in sorted(rat_paths):
        if not os.path.isfile(rat_path):
            raise FileNotFoundError(
                f".rat texture referenced in USD but missing on disk: {rat_path}"
            )
        exr_name = Path(rat_path).stem + ".exr"
        exr_path = os.path.join(tex_dir, exr_name)
        result = subprocess.run(
            [iconvert, rat_path, exr_path],
            capture_output=True, text=True, shell=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"iconvert failed for {rat_path}: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        path_map[rat_path] = exr_path
        converted.append((rat_path, exr_path))

    # Rewrite paths in the layer
    if path_map:
        def _rewrite(path):
            return path_map.get(path, path)
        UsdUtils.ModifyAssetPaths(layer, _rewrite)
        layer.Save()

    return converted


def extract_udim_for_usdz(
    flat_usda_path: str,
    textures_dir: str,
) -> list[tuple[str, str, str]]:
    """Extract UDIM textures as loose files for standalone husk.

    USDZ archives can't resolve UDIM patterns (<UDIM> token) because the
    UDIM resolver needs to scan a directory for matching tiles. This function
    copies UDIM tile files to a loose directory and collects the prim/attr
    info needed to override paths in the wrapper USDA.

    Args:
        flat_usda_path: Path to the flattened .usda file.
        textures_dir: Shot Textures/ directory for loose tile files.

    Returns:
        List of (prim_path, attr_name, relative_udim_pattern) tuples
        for the wrapper writer to override.
    """
    import glob
    import shutil
    from pxr import Sdf

    layer = Sdf.Layer.FindOrOpen(flat_usda_path)

    # Walk all prims/attrs looking for <UDIM> asset paths
    udim_overrides = []  # (prim_path, attr_name, new_relative_pattern)
    seen_patterns = {}   # original_pattern -> relative_pattern (dedup copies)

    def _walk(prim_spec):
        for attr in prim_spec.attributes:
            val = attr.default
            if not isinstance(val, Sdf.AssetPath):
                continue
            path_str = val.path
            if "<UDIM>" not in path_str:
                continue

            if path_str not in seen_patterns:
                # Resolve actual tile files on disk
                glob_pattern = path_str.replace("<UDIM>", "[0-9][0-9][0-9][0-9]")
                tiles = sorted(glob.glob(glob_pattern))

                if tiles:
                    ensure_dir(textures_dir)
                    for tile in tiles:
                        dst = os.path.join(textures_dir, os.path.basename(tile))
                        if os.path.abspath(tile) != os.path.abspath(dst):
                            shutil.copy2(tile, dst)

                    # Build relative pattern from Scenes/ to Textures/
                    base_name = os.path.basename(path_str)
                    rel_pattern = f"../Textures/{base_name}"
                    seen_patterns[path_str] = rel_pattern

            if path_str in seen_patterns:
                udim_overrides.append(
                    (str(prim_spec.path), attr.name, seen_patterns[path_str])
                )

        for child in prim_spec.nameChildren:
            _walk(child)

    for prim in layer.rootPrims:
        _walk(prim)

    return udim_overrides
