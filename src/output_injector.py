"""Output path injector — set RenderProduct output paths.

Finds all RenderProduct prims and sets their productName to write into
the specified output directory.
"""

def inject_output_paths(stage, shot_name: str, output_dir_relative: str = "../Output", output_format: str = "png") -> list[str]:
    """Set RenderProduct output paths to the given relative directory.

    Finds all RenderProduct prims and authors productName as:
        {output_dir_relative}/{shot_name}.<F4>.{ext}

    The <F4> token is a husk-native frame variable (UDIM-style) that husk
    expands to the zero-padded frame number at render time.  Unlike $F4,
    which Houdini's expression engine would evaluate (and consume) before
    the value reaches husk, <F4> is stored as a literal string in USD and
    only expanded by husk itself.  This is required for multi-frame
    renders — husk refuses to render an animation when productName has no
    frame variable ("Output file should have variables").

    Args:
        stage: A Usd.Stage to modify.
        shot_name: Shot name to prefix output filenames with.
        output_dir_relative: Relative directory for output files.
        output_format: Image format — "png" or "exr".

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
        ext = output_format if output_format in ("png", "exr") else "png"
        new_path = f"{output_dir_relative}/{shot_name}.<F4>.{ext}"

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
