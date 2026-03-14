"""Output path injector — set RenderProduct output paths.

Finds all RenderProduct prims and sets their productName to write into
the specified output directory.
"""

def inject_output_paths(
    stage,
    shot_name: str,
    output_dir_relative: str = "../Output",
    output_format: str = "png",
    frame_start: int | None = None,
    frame_end: int | None = None,
) -> list[str]:
    """Set RenderProduct output paths and stage time codes.

    Finds all RenderProduct prims and authors productName as:
        {output_dir_relative}/{shot_name}.<F4>.{ext}

    The <F4> token is a husk-native frame variable (UDIM-style) that husk
    expands to the zero-padded frame number at render time.  Unlike $F4,
    which Houdini's expression engine would evaluate (and consume) before
    the value reaches husk, <F4> is stored as a literal string in USD and
    only expanded by husk itself.  This is required for multi-frame
    renders — husk refuses to render an animation when productName has no
    frame variable ("Output file should have variables").

    When frame_start/frame_end are provided, authors startTimeCode and
    endTimeCode on the stage root layer so render scripts can extract the
    frame range directly from the USD file.

    Args:
        stage: A Usd.Stage to modify.
        shot_name: Shot name to prefix output filenames with.
        output_dir_relative: Relative directory for output files.
        output_format: Image format — "png" or "exr".
        frame_start: First frame number (authored as startTimeCode).
        frame_end: Last frame number (authored as endTimeCode).

    Returns:
        List of prim paths that were modified.
    """
    from pxr import Sdf

    modified = []
    root_layer = stage.GetRootLayer()

    # Author frame range so render scripts can read it from the USD
    if frame_start is not None:
        root_layer.startTimeCode = frame_start
    if frame_end is not None:
        root_layer.endTimeCode = frame_end

    for prim in stage.Traverse():
        if prim.GetTypeName() != "RenderProduct":
            continue

        prim_name = prim.GetName()
        ext = output_format if output_format in ("png", "exr") else "png"
        new_path = f"{output_dir_relative}/{shot_name}.<F4>.{ext}"

        # Clear any time-sampled productName baked by Karma's expression
        # evaluator ($HIP/render/$HIPNAME.$OS.$F4.exr → concrete path).
        # Time-sampled values take precedence over defaults in USD, so
        # husk would use the stale baked path instead of our override.
        attr = prim.GetAttribute("productName")
        if attr and attr.GetTimeSamples():
            attr.Clear()

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
