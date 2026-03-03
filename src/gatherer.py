"""File gatherer — copy files to staging locations and rewrite USD paths.

Handles textures (into USDZ staging) and caches (into shot cache dir).
"""

import os
import shutil
from pathlib import Path

from src.platform_utils import ensure_dir


def gather_textures(
    converted_paths: list[str],
    usdz_staging_dir: str,
) -> dict[str, str]:
    """Copy textures into the USDZ staging textures/ subdirectory.

    Args:
        converted_paths: List of texture file paths to gather.
        usdz_staging_dir: Root staging directory for the USDZ package.

    Returns:
        Mapping of {original_path: new_staged_path}.
    """
    tex_dir = os.path.join(usdz_staging_dir, "textures")
    ensure_dir(tex_dir)

    path_map = {}
    for src in converted_paths:
        filename = os.path.basename(src)
        dst = os.path.join(tex_dir, filename)
        if os.path.abspath(src) != os.path.abspath(dst):
            shutil.copy2(src, dst)
        path_map[src] = dst

    return path_map


def gather_caches(
    cache_paths: list[str],
    shot_cache_dir: str,
) -> dict[str, str]:
    """Copy cache files into the shot Cache/ directory.

    Preserves frame-numbered filenames exactly.

    Args:
        cache_paths: List of cache file paths.
        shot_cache_dir: Target Cache/ directory.

    Returns:
        Mapping of {original_path: new_cache_path}.
    """
    ensure_dir(shot_cache_dir)

    path_map = {}
    for src in cache_paths:
        filename = os.path.basename(src)
        dst = os.path.join(shot_cache_dir, filename)
        if os.path.abspath(src) != os.path.abspath(dst):
            shutil.copy2(src, dst)
        path_map[src] = dst

    return path_map


def rewrite_paths_in_layer(layer, path_map: dict[str, str]) -> None:
    """Rewrite asset paths in a USD layer using a path mapping.

    Uses UsdUtils.ModifyAssetPaths with a replacement function.

    Args:
        layer: An Sdf.Layer to modify in place.
        path_map: Mapping of {old_path: new_path}.
    """
    from pxr import UsdUtils

    # Build a normalized lookup for matching
    normalized_map = {}
    for old, new in path_map.items():
        normalized_map[Path(old).as_posix()] = Path(new).as_posix()
        # Also store with the original form for exact matching
        normalized_map[old] = Path(new).as_posix()

    def _replace_fn(path_str):
        posix = Path(path_str).as_posix() if path_str else path_str
        return normalized_map.get(posix, normalized_map.get(path_str, path_str))

    UsdUtils.ModifyAssetPaths(layer, _replace_fn)


def make_cache_relative_path(cache_abs: str, wrapper_usda_path: str) -> str:
    """Compute relative path from wrapper .usda location to a cache file.

    Result should be like ../Cache/filename.vdb

    Args:
        cache_abs: Absolute path to the cache file.
        wrapper_usda_path: Absolute path to the wrapper .usda file.

    Returns:
        Relative POSIX-style path.
    """
    wrapper_dir = os.path.dirname(os.path.abspath(wrapper_usda_path))
    rel = os.path.relpath(os.path.abspath(cache_abs), wrapper_dir)
    return Path(rel).as_posix()
