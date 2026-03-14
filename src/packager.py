"""USD packager — flatten stage and create USDZ archive.

Handles stage flattening and USDZ package creation.
"""

import os
import tempfile
from pathlib import Path

from src.platform_utils import ensure_dir


def flatten_stage(stage, staging_dir: str) -> str:
    """Flatten a USD stage and export to a temp .usda in the staging directory.

    Args:
        stage: A Usd.Stage to flatten.
        staging_dir: Directory to write the flattened file.

    Returns:
        Path to the flattened .usda file.
    """
    ensure_dir(staging_dir)
    flat_layer = stage.Flatten()
    output_path = os.path.join(staging_dir, "flattened.usda")
    flat_layer.Export(output_path)
    return output_path


def create_usdz(
    flattened_usda: str,
    output_usdz: str,
    dry_run: bool = False,
) -> list[str]:
    """Create a USDZ package from a flattened .usda.

    Uses UsdUtils.CreateNewUsdzPackage (non-ARKit variant).

    Args:
        flattened_usda: Path to the flattened .usda file.
        output_usdz: Path for the output .usdz file.
        dry_run: If True, return file list without writing.

    Returns:
        List of files included in the package.
    """
    from pxr import UsdUtils

    if dry_run:
        # Compute what would be included without creating the archive
        from pxr import Usd
        stage = Usd.Stage.Open(flattened_usda)
        layers, assets, unresolved = UsdUtils.ComputeAllDependencies(flattened_usda)
        files = [flattened_usda] + list(assets)
        return files

    ensure_dir(os.path.dirname(output_usdz))
    success = UsdUtils.CreateNewUsdzPackage(flattened_usda, output_usdz)

    if not success:
        raise RuntimeError(
            f"Failed to create USDZ at {output_usdz}. Common causes: "
            "referenced assets don't exist on disk, or asset paths "
            "contain unresolved variables."
        )

    return [output_usdz]


def extract_shader_assets(usdz_path: str, output_dir: str) -> dict[str, str]:
    """Extract VEX shader files from a USDZ to disk for standalone husk.

    Husk's VEX compiler cannot read files from inside a USDZ archive.
    This function finds Shader prims that use ``info:implementationSource =
    "sourceAsset"``, extracts the referenced files from the USDZ, and
    returns a mapping suitable for ``write_wrapper(shader_path_map=...)``.

    Args:
        usdz_path: Path to the USDZ package.
        output_dir: Directory to extract shader files into (e.g. Scenes/).

    Returns:
        Mapping of {shader_prim_path: relative_path_to_extracted_file}.
        Relative paths are from the perspective of the wrapper USDA
        (assumed to live in the same directory as the USDZ).
    """
    import zipfile
    from pxr import Usd, Sdf

    stage = Usd.Stage.Open(usdz_path)
    if not stage:
        return {}

    # Find shader prims using sourceAsset
    shader_assets = {}  # {prim_path: asset_path_inside_usdz}
    for prim in stage.Traverse():
        if prim.GetTypeName() != "Shader":
            continue
        impl = prim.GetAttribute("info:implementationSource")
        if not impl or impl.Get() != "sourceAsset":
            continue
        sa = prim.GetAttribute("info:sourceAsset")
        if not sa:
            continue
        asset_path = sa.Get()
        if asset_path:
            path_str = asset_path.path if hasattr(asset_path, "path") else str(asset_path)
            if path_str:
                shader_assets[str(prim.GetPath())] = path_str

    if not shader_assets:
        return {}

    # Extract referenced files from the USDZ
    shader_path_map = {}
    ensure_dir(output_dir)
    with zipfile.ZipFile(usdz_path, "r") as zf:
        archive_names = set(zf.namelist())
        for prim_path, asset_path in shader_assets.items():
            if asset_path in archive_names:
                dest = os.path.join(output_dir, os.path.basename(asset_path))
                with zf.open(asset_path) as src, open(dest, "wb") as dst:
                    dst.write(src.read())
                # Relative path from wrapper USDA (same dir as USDZ)
                shader_path_map[prim_path] = os.path.basename(asset_path)

    return shader_path_map
