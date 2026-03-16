"""Read Mantra ROP parameters into a structured report.

Extracts resolution, sampling, output path, camera, and frame range
from a Mantra ROP node.
"""

from dataclasses import dataclass, field


@dataclass
class MantraAuditReport:
    """Structured data read from a Mantra ROP."""
    node_path: str = ""
    resolution: tuple[int, int] = (1280, 720)
    pixel_samples: tuple[int, int] = (3, 3)
    max_ray_samples: int = 9
    min_ray_samples: int = 1
    output_picture: str = ""
    image_format: str = ""
    camera: str = ""
    render_engine: str = "micropoly"
    frame_start: float = 0
    frame_end: float = 0
    frame_inc: float = 1
    aov_count: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def frame_count(self) -> int:
        if self.frame_inc <= 0:
            return 0
        return int((self.frame_end - self.frame_start) / self.frame_inc) + 1


def audit_mantra_rop(node) -> MantraAuditReport:
    """Read all relevant parameters from a Mantra ROP node.

    Args:
        node: A hou.RopNode pointing to a Mantra (ifd) node.

    Returns:
        MantraAuditReport with all extracted data and warnings.
    """
    report = MantraAuditReport(node_path=node.path())
    warnings = []

    # Resolution
    res_x = node.parm("res_overridex")
    res_y = node.parm("res_overridey")
    if res_x and res_y:
        report.resolution = (res_x.eval(), res_y.eval())
    else:
        # Fall back to camera resolution override parms
        rx = node.parm("res_overridex") or node.parm("resx")
        ry = node.parm("res_overridey") or node.parm("resy")
        if rx and ry:
            report.resolution = (rx.eval(), ry.eval())

    # Pixel samples
    sx = node.parm("vm_samplesx")
    sy = node.parm("vm_samplesy")
    if sx and sy:
        report.pixel_samples = (sx.eval(), sy.eval())

    # Ray samples
    max_ray = node.parm("vm_maxraysamples")
    if max_ray:
        report.max_ray_samples = max_ray.eval()
    min_ray = node.parm("vm_minraysamples")
    if min_ray:
        report.min_ray_samples = min_ray.eval()

    # Output picture
    vm_picture = node.parm("vm_picture")
    if vm_picture:
        report.output_picture = vm_picture.eval()

    # Image format
    vm_format = node.parm("vm_image_format")
    if vm_format:
        report.image_format = vm_format.evalAsString()

    # Camera
    camera = node.parm("camera")
    if camera:
        report.camera = camera.eval()
        if not report.camera:
            warnings.append("No camera assigned to Mantra ROP.")

    # Render engine
    engine = node.parm("vm_renderengine")
    if engine:
        report.render_engine = engine.evalAsString()

    # Frame range
    trange = node.parm("trange")
    if trange and trange.eval() == 0:
        warnings.append(
            "Frame range is set to 'Render Current Frame'. "
            "Remote rendering will use the frame range from packaging."
        )

    f1 = node.parm("f1")
    f2 = node.parm("f2")
    f3 = node.parm("f3")
    if f1 and f2 and f3:
        report.frame_start = f1.eval()
        report.frame_end = f2.eval()
        report.frame_inc = f3.eval()

    # Count extra image planes (AOVs)
    num_planes = node.parm("vm_numaux")
    if num_planes:
        report.aov_count = num_planes.eval()

    # Warnings
    if report.max_ray_samples < 2:
        warnings.append(
            f"Max ray samples is {report.max_ray_samples} — "
            "this may produce noisy renders."
        )

    report.warnings = warnings
    return report
