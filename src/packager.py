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
