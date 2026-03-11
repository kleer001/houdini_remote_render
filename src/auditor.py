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

    report.instance_count = check_instance_density(stage)

    if not report.has_render_settings:
        report.warnings.append("No RenderSettings prim found.")
    if not report.has_camera:
        report.warnings.append("No Camera prim found. A camera is required for rendering.")
    if not report.has_render_products:
        report.warnings.append("No RenderProduct prim found.")
    if report.instance_count > 1_000_000:
        report.warnings.append(
            f"High instance count ({report.instance_count:,}). "
            f"stage.Flatten() will expand all instances and may use excessive memory."
        )

    return report


def ensure_render_settings(stage) -> None:
    """Author a minimal /Render/rendersettings prim if none exists."""
    from pxr import Gf, UsdRender

    for prim in stage.Traverse():
        if prim.GetTypeName() == "RenderSettings":
            return

    render_scope = stage.DefinePrim("/Render", "Scope")
    settings = UsdRender.Settings.Define(stage, "/Render/rendersettings")
    settings.GetResolutionAttr().Set(Gf.Vec2i(1920, 1080))


def ensure_render_vars(stage) -> int:
    """Add default orderedVars (beauty + alpha) to RenderProducts that lack them.

    Standalone husk requires explicit orderedVars to know which AOVs to write.
    Karma in-process handles this internally, so Houdini scenes often omit them.
    """
    from pxr import UsdRender

    patched = 0
    for prim in stage.Traverse():
        if prim.GetTypeName() != "RenderProduct":
            continue

        product = UsdRender.Product(prim)
        if product.GetOrderedVarsRel().GetTargets():
            continue

        parent_path = prim.GetPath().GetParentPath()
        vars_scope_path = parent_path.AppendChild("Vars")
        beauty_path = vars_scope_path.AppendChild("beauty")
        alpha_path = vars_scope_path.AppendChild("alpha")

        stage.DefinePrim(vars_scope_path, "Scope")

        beauty_var = UsdRender.Var.Define(stage, beauty_path)
        beauty_var.GetDataTypeAttr().Set("color3f")
        beauty_var.GetSourceNameAttr().Set("Ci")

        alpha_var = UsdRender.Var.Define(stage, alpha_path)
        alpha_var.GetDataTypeAttr().Set("float")
        alpha_var.GetSourceNameAttr().Set("a")

        product.GetOrderedVarsRel().SetTargets([beauty_path, alpha_path])
        patched += 1

    return patched


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
