"""Wrapper writer — author thin .usda that combines USDZ with cache references.

Creates a lightweight USD file that sublayers the USDZ archive and
overrides asset paths to point to local cache files.
"""

import os
from pathlib import Path


def write_wrapper(
    usdz_relative_path: str,
    cache_path_map: dict[str, str],
    output_usda: str,
) -> None:
    """Author a wrapper .usda file that references the USDZ and cache files.

    Args:
        usdz_relative_path: Relative path to the USDZ file (e.g. "shot_001.usdz").
            Should be just the filename since both files live in Scenes/.
        cache_path_map: Mapping of {prim_path: relative_cache_path}.
            Keys are USD prim paths, values are relative paths to cache files.
        output_usda: Absolute path for the output .usda wrapper file.
    """
    from pxr import Usd, Sdf

    stage = Usd.Stage.CreateNew(output_usda)
    root_layer = stage.GetRootLayer()

    # Add USDZ as a sublayer
    root_layer.subLayerPaths.append(usdz_relative_path)

    # Author cache path overrides
    for prim_path, cache_rel_path in cache_path_map.items():
        prim = stage.OverridePrim(prim_path)
        if prim:
            # Find the asset path attribute and override it
            prim_spec = root_layer.GetPrimAtPath(prim_path)
            if prim_spec is None:
                prim_spec = Sdf.CreatePrimInLayer(root_layer, prim_path)

            attr_spec = Sdf.AttributeSpec(
                prim_spec, "filePath", Sdf.ValueTypeNames.Asset
            )
            attr_spec.default = cache_rel_path

    root_layer.Save()
