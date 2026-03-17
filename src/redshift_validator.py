"""Validation guards for the Redshift USD packaging pipeline.

Checks that the USD stage contains Redshift-compatible render setup
and is ready for remote packaging via redshiftUsdCmdLine.
"""


def validate_redshift_stage(stage) -> tuple[bool, str]:
    """Check that the stage has Redshift render settings.

    Looks for ``redshift:`` namespaced attributes on RenderSettings prims,
    which indicate Redshift-specific configuration was authored.

    Args:
        stage: A Usd.Stage (or None).

    Returns:
        (True, "") on success, (False, reason) on failure.
    """
    if stage is None:
        return False, "No USD stage available."

    for prim in stage.Traverse():
        if prim.GetTypeName() != "RenderSettings":
            continue
        for attr in prim.GetAttributes():
            if attr.GetName().startswith("redshift:"):
                return True, ""

    return False, (
        "No Redshift render settings found in the stage. "
        "Add a Redshift RenderSettings LOP to author redshift: attributes."
    )


def validate_redshift_materials(stage) -> list[str]:
    """Return warnings for UsdPreviewSurface materials in the stage.

    UsdPreviewSurface shaders are renderable by Redshift (since RS 2025.3)
    but lack Redshift-specific features like AOV output and advanced shading.
    """
    warnings = []
    preview_surface_mats = []

    for prim in stage.Traverse():
        if prim.GetTypeName() != "Shader":
            continue
        shader_id = prim.GetAttribute("info:id")
        if shader_id and shader_id.Get() == "UsdPreviewSurface":
            mat = prim.GetParent()
            mat_name = mat.GetName() if mat else prim.GetName()
            if mat_name not in preview_surface_mats:
                preview_surface_mats.append(mat_name)

    if preview_surface_mats:
        names = ", ".join(preview_surface_mats)
        warnings.append(
            f"UsdPreviewSurface materials found: {names}. "
            "Redshift can render these (since RS 2025.3) but they lack "
            "Redshift-specific features. For best results use RS Material Builder."
        )

    return warnings
