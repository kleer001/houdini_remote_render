"""Wrapper writer — author thin .usda that combines USDZ with overrides.

Creates a lightweight USD file that sublayers the USDZ archive and
overrides asset paths for caches and shader sourceAsset references.
"""

def write_wrapper(
    usdz_relative_path: str,
    cache_path_map: dict[str, str],
    output_usda: str,
    shader_opdef_map: dict[str, str] | None = None,
    udim_overrides: list[tuple[str, str, str]] | None = None,
) -> None:
    """Author a wrapper .usda that references the USDZ and overrides paths.

    Args:
        usdz_relative_path: Relative path to the USDZ file.
        cache_path_map: {prim_path: relative_cache_path} for cache overrides.
        output_usda: Absolute path for the output .usda wrapper file.
        shader_opdef_map: {shader_prim_path: original_opdef_uri}.
            Restores opdef: URIs that were baked to files for USDZ packaging.
            Standalone husk resolves opdef: through the OTL system to compile
            VEX shaders at render time.
        udim_overrides: [(prim_path, attr_name, relative_udim_pattern)].
            Overrides UDIM texture paths to point to loose tile files,
            since USDZ archives can't resolve UDIM patterns internally.
    """
    from pxr import Usd, Sdf

    stage = Usd.Stage.CreateNew(output_usda)
    root_layer = stage.GetRootLayer()

    # Add USDZ as a sublayer
    root_layer.subLayerPaths.append(usdz_relative_path)

    def _set_asset_override(prim_path, attr_name, value):
        """Get-or-create an Over prim spec and set an Asset attribute."""
        prim_spec = root_layer.GetPrimAtPath(prim_path)
        if prim_spec is None:
            prim_spec = Sdf.CreatePrimInLayer(root_layer, prim_path)
            prim_spec.specifier = Sdf.SpecifierOver
        attr_spec = Sdf.AttributeSpec(
            prim_spec, attr_name, Sdf.ValueTypeNames.Asset
        )
        attr_spec.default = Sdf.AssetPath(value)

    # Author cache path overrides
    for prim_path, cache_rel_path in cache_path_map.items():
        stage.OverridePrim(prim_path)
        _set_asset_override(prim_path, "filePath", cache_rel_path)

    # Restore shader opdef: URIs so husk resolves VEX through OTL system.
    # The USDZ has baked VFL files (needed for packaging), but husk needs
    # the original opdef: path to trigger VEX compilation via VEX_VexResolver.
    for prim_path, opdef_uri in (shader_opdef_map or {}).items():
        _set_asset_override(prim_path, "info:sourceAsset", opdef_uri)

    # Override UDIM texture paths to point to loose tile files.
    # USDZ archives can't resolve <UDIM> patterns because the resolver
    # needs to scan a directory for matching tiles.
    for prim_path, attr_name, rel_pattern in (udim_overrides or []):
        _set_asset_override(prim_path, attr_name, rel_pattern)

    root_layer.Save()
