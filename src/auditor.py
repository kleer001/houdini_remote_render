"""Stage auditor — inspect the incoming USD stage for render readiness.

Verifies or authors required prims (render settings, cameras, render products).
"""

from dataclasses import dataclass, field


@dataclass
class AuditReport:
    """Results of a stage audit."""
    has_render_settings: bool = False
    has_camera: bool = False
    has_render_products: bool = False
    has_render_vars: bool = False
    products_missing_vars: list[str] = field(default_factory=list)
    vex_shaders: list[str] = field(default_factory=list)
    resolution_mismatches: list[str] = field(default_factory=list)
    camera_mismatch: str | None = None
    instance_count: int = 0
    warnings: list[str] = field(default_factory=list)


def audit_stage(stage) -> AuditReport:
    """Inspect a USD stage and return an AuditReport."""
    from pxr import UsdGeom, UsdRender

    report = AuditReport()

    for prim in stage.Traverse():
        type_name = prim.GetTypeName()

        if type_name == "RenderSettings":
            report.has_render_settings = True
        elif type_name == "Camera":
            report.has_camera = True
        elif type_name == "RenderProduct":
            report.has_render_products = True
            product = UsdRender.Product(prim)
            if not product.GetOrderedVarsRel().GetTargets():
                report.products_missing_vars.append(str(prim.GetPath()))
        elif type_name == "RenderVar":
            report.has_render_vars = True

    report.instance_count = check_instance_density(stage)
    report.vex_shaders = check_vex_shaders(stage)
    report.resolution_mismatches = check_resolution_mismatches(stage)
    report.camera_mismatch = check_render_camera(stage)

    if not report.has_render_settings:
        report.warnings.append("No RenderSettings prim found.")
    if not report.has_camera:
        report.warnings.append("No Camera prim found. A camera is required for rendering.")
    if report.camera_mismatch:
        report.warnings.append(report.camera_mismatch)
    if not report.has_render_products:
        report.warnings.append("No RenderProduct prim found.")
    if report.products_missing_vars:
        report.warnings.append(
            "No AOVs (RenderVars) configured. Standalone husk will render a BLACK image. "
            "Enable the Beauty AOV in your Karma RenderSettings LOP."
        )
    if report.vex_shaders:
        names = ", ".join(report.vex_shaders)
        report.warnings.append(
            f"VEX shaders found: {names}. "
            "These require Houdini installed on the render machine (Karma CPU only, not XPU). "
            "For fully portable scenes, use MaterialX (mtlxstandard_surface)."
        )
    if report.resolution_mismatches:
        for msg in report.resolution_mismatches:
            report.warnings.append(msg)
    if report.instance_count > 1_000_000:
        report.warnings.append(
            f"High instance count ({report.instance_count:,}). "
            f"stage.Flatten() will expand all instances and may use excessive memory."
        )

    return report


def ensure_render_settings(stage) -> None:
    """Author a minimal /Render/rendersettings prim if none exists.

    When creating a fallback RenderSettings, wires the ``products``
    relationship to every RenderProduct already in the scene and sets
    the ``camera`` relationship to the first Camera found.
    """
    from pxr import Gf, Sdf, UsdRender

    for prim in stage.Traverse():
        if prim.GetTypeName() == "RenderSettings":
            return

    render_scope = stage.DefinePrim("/Render", "Scope")
    settings = UsdRender.Settings.Define(stage, "/Render/rendersettings")
    settings.GetResolutionAttr().Set(Gf.Vec2i(1920, 1080))

    # Wire products and camera relationships so husk can find them
    product_paths = []
    camera_path = None
    for prim in stage.Traverse():
        if prim.GetTypeName() == "RenderProduct":
            product_paths.append(prim.GetPath())
        elif prim.GetTypeName() == "Camera" and camera_path is None:
            camera_path = prim.GetPath()

    if product_paths:
        settings.GetProductsRel().SetTargets(product_paths)
    if camera_path:
        settings.GetCameraRel().SetTargets([camera_path])


def check_render_camera(stage) -> str | None:
    """Check if RenderSettings camera points to an existing Camera prim.

    Returns a warning string if mismatched, None if OK or no RenderSettings.
    """
    from pxr import UsdRender

    camera_paths = set()
    settings_camera = None

    for prim in stage.Traverse():
        if prim.GetTypeName() == "Camera":
            camera_paths.add(str(prim.GetPath()))
        elif prim.GetTypeName() == "RenderSettings" and settings_camera is None:
            rs = UsdRender.Settings(prim)
            targets = rs.GetCameraRel().GetTargets()
            if targets:
                settings_camera = str(targets[0])

    if settings_camera is None:
        return None
    if settings_camera not in camera_paths:
        available = ", ".join(sorted(camera_paths)) if camera_paths else "none found"
        return (
            f"RenderSettings camera points to {settings_camera} "
            f"which does not exist. Available cameras: {available}. "
            f"husk will fail with 'No render camera defined'."
        )
    return None


def check_render_vars(stage) -> list[str]:
    """Return paths of RenderProducts that have no orderedVars.

    Standalone husk requires explicit orderedVars authored by the Karma
    RenderSettings LOP (Beauty AOV checkbox).  Rather than trying to
    author our own RenderVars (which differ between in-process and
    standalone husk — SideFX BUG #134678), we detect the gap and warn
    the user to enable AOVs in their scene.
    """
    from pxr import UsdRender

    missing = []
    for prim in stage.Traverse():
        if prim.GetTypeName() != "RenderProduct":
            continue
        product = UsdRender.Product(prim)
        if not product.GetOrderedVarsRel().GetTargets():
            missing.append(str(prim.GetPath()))
    return missing


def check_vex_shaders(stage) -> list[str]:
    """Return material names containing VEX/sourceAsset shaders.

    Standalone husk cannot compile VEX shaders from sourceAsset references.
    These materials will render as default grey. Only MaterialX (ND_*),
    UsdPreviewSurface, and Karma-native (kma_*) shaders are portable.
    """
    vex_materials = []
    for prim in stage.Traverse():
        if prim.GetTypeName() != "Shader":
            continue
        impl = prim.GetAttribute("info:implementationSource")
        if impl and impl.Get() == "sourceAsset":
            mat = prim.GetParent()
            mat_name = mat.GetName() if mat else prim.GetName()
            if mat_name not in vex_materials:
                vex_materials.append(mat_name)
    return vex_materials


def check_resolution_mismatches(stage) -> list[str]:
    """Warn if RenderProduct resolution differs from RenderSettings."""
    from pxr import UsdRender

    settings_res = None
    for prim in stage.Traverse():
        if prim.GetTypeName() == "RenderSettings":
            attr = prim.GetAttribute("resolution")
            if attr:
                settings_res = attr.Get()
            break

    if settings_res is None:
        return []

    mismatches = []
    for prim in stage.Traverse():
        if prim.GetTypeName() != "RenderProduct":
            continue
        attr = prim.GetAttribute("resolution")
        if not attr:
            continue
        prod_res = attr.Get()
        if prod_res and prod_res != settings_res:
            mismatches.append(
                f"Resolution mismatch: RenderSettings={settings_res[0]}x{settings_res[1]} "
                f"but {prim.GetName()}={prod_res[0]}x{prod_res[1]}. "
                f"husk will use the RenderProduct resolution."
            )
    return mismatches


def ensure_camera(stage) -> None:
    """Log a warning if no camera exists. Does not create one."""
    for prim in stage.Traverse():
        if prim.GetTypeName() == "Camera":
            return
    # No camera found — caller should handle the warning via AuditReport


def check_instance_density(stage) -> int:
    """Count total estimated instances from PointInstancer prims."""
    from pxr import UsdGeom

    total = 0
    for prim in stage.Traverse():
        if prim.GetTypeName() == "PointInstancer":
            instancer = UsdGeom.PointInstancer(prim)
            positions = instancer.GetPositionsAttr().Get()
            if positions:
                total += len(positions)
    return total
