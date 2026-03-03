"""Output path injector — set RenderProduct output paths.

Finds all RenderProduct prims and sets their productName to write into
the specified output directory.
"""

from pathlib import Path


def inject_output_paths(stage, output_dir_relative: str = "../Output") -> list[str]:
    """Set RenderProduct output paths to the given relative directory.

    Finds all RenderProduct prims and authors productName as:
        {output_dir_relative}/{product_name}.$F4.exr

    Args:
        stage: A Usd.Stage to modify.
        output_dir_relative: Relative directory for output files.

    Returns:
        List of prim paths that were modified.
    """
    from pxr import Sdf

    modified = []
    root_layer = stage.GetRootLayer()

    for prim in stage.Traverse():
        if prim.GetTypeName() != "RenderProduct":
            continue

        prim_name = prim.GetName()
        new_path = f"{output_dir_relative}/{prim_name}.$F4.exr"

        # Author via Sdf so it survives flatten
        prim_spec = root_layer.GetPrimAtPath(prim.GetPath())
        if prim_spec is None:
            prim_spec = Sdf.CreatePrimInLayer(root_layer, prim.GetPath())

        attr_spec = root_layer.GetAttributeAtPath(
            prim.GetPath().AppendProperty("productName")
        )
        if attr_spec is None:
            attr_spec = Sdf.AttributeSpec(
                prim_spec, "productName", Sdf.ValueTypeNames.Token
            )
        attr_spec.default = new_path

        modified.append(str(prim.GetPath()))

    return modified
