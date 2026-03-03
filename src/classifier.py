"""Dependency classifier — scan USD assets and sort into buckets.

Uses UsdUtils.ComputeAllDependencies to discover all referenced files.
"""

import os
import glob as globmod
from dataclasses import dataclass, field

TEXTURE_EXTENSIONS = frozenset([
    ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".exr", ".hdr", ".tx", ".rat",
])

CACHE_EXTENSIONS = frozenset([
    ".vdb", ".bgeo.sc", ".abc",
])

USD_EXTENSIONS = frozenset([
    ".usd", ".usda", ".usdc", ".usdz",
])


@dataclass
class ClassifiedDeps:
    """Classified dependency buckets."""
    textures: list[str] = field(default_factory=list)
    caches: list[str] = field(default_factory=list)
    sublayers: list[str] = field(default_factory=list)
    udim_patterns: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)


def _get_extension(path: str) -> str:
    """Get file extension, handling compound extensions like .bgeo.sc."""
    if path.endswith(".bgeo.sc"):
        return ".bgeo.sc"
    return os.path.splitext(path)[1].lower()


def classify_dependencies(stage_path: str) -> ClassifiedDeps:
    """Scan all asset dependencies and classify them.

    Args:
        stage_path: Path to a USD file on disk.

    Returns:
        ClassifiedDeps with assets sorted into buckets.
    """
    from pxr import UsdUtils

    layers, assets, unresolved = UsdUtils.ComputeAllDependencies(stage_path)

    result = ClassifiedDeps()

    # Unresolved paths (files that couldn't be found on disk)
    result.unresolved = list(unresolved)

    # Classify resolved assets
    for asset_path in assets:
        path_str = str(asset_path)
        ext = _get_extension(path_str)

        if ext in TEXTURE_EXTENSIONS:
            result.textures.append(path_str)
        elif ext in CACHE_EXTENSIONS:
            result.caches.append(path_str)

    # Classify layers (sublayers, references)
    # Skip the first layer — it's the root stage itself
    for layer in layers[1:]:
        layer_path = layer.realPath if hasattr(layer, "realPath") else str(layer)
        ext = _get_extension(layer_path)
        if ext in USD_EXTENSIONS:
            result.sublayers.append(layer_path)

    # Detect UDIM patterns in unresolved paths
    udim_patterns = detect_udim_pattern(result.unresolved)
    result.udim_patterns = udim_patterns

    return result


def expand_udim_pattern(pattern: str) -> list[str]:
    """Expand a <UDIM> pattern to matching tile files on disk.

    Args:
        pattern: Path containing <UDIM>, e.g. /tex/wood.<UDIM>.exr

    Returns:
        List of real file paths matching the pattern.
    """
    # Replace <UDIM> with a glob wildcard for 4-digit tile numbers
    glob_pattern = pattern.replace("<UDIM>", "[0-9][0-9][0-9][0-9]")
    return sorted(globmod.glob(glob_pattern))


def detect_udim_pattern(paths: list[str]) -> list[str]:
    """Detect UDIM patterns in a list of paths.

    Args:
        paths: List of file paths (resolved or unresolved).

    Returns:
        List of unique <UDIM> pattern strings found.
    """
    patterns = []
    for p in paths:
        if "<UDIM>" in p:
            if p not in patterns:
                patterns.append(p)
    return patterns
