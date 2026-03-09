"""Read File Cache SOP parameters into a structured report.

Extracts frame range, format, output path, and flags from a File Cache node.
"""

from dataclasses import dataclass


@dataclass
class CacheAuditReport:
    """Structured data read from a File Cache SOP."""
    node_path: str = ""
    file_method: str = "constructed"     # "constructed" or "explicit"
    base_name: str = ""
    base_dir: str = ""
    file_type: str = ".bgeo.sc"
    explicit_path: str = ""
    output_path: str = ""               # resolved sopoutput
    frame_start: float = 0
    frame_end: float = 0
    frame_inc: float = 1
    substeps: int = 1
    is_time_dependent: bool = True
    is_simulation: bool = True
    save_in_background: bool = True
    load_from_disk: bool = False
    version_enabled: bool = True
    version: int = 1
    warnings: list[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []

    @property
    def frame_count(self) -> int:
        if self.frame_inc <= 0:
            return 0
        return int((self.frame_end - self.frame_start) / self.frame_inc) + 1


def audit_file_cache(node) -> CacheAuditReport:
    """Read all relevant parameters from a File Cache SOP node.

    Args:
        node: A hou.SopNode pointing to a filecache node.

    Returns:
        CacheAuditReport with all extracted data and warnings.
    """
    report = CacheAuditReport(node_path=node.path())
    warnings = []

    # File path method
    method_val = node.parm("filemethod").eval()
    report.file_method = "explicit" if method_val == 1 else "constructed"

    # Path components
    report.base_name = node.parm("basename").unexpandedString()
    report.base_dir = node.parm("basedir").unexpandedString()
    report.explicit_path = node.parm("file").unexpandedString()

    # File type
    report.file_type = node.parm("filetype").evalAsString()

    # Resolved output path
    report.output_path = node.parm("sopoutput").eval()

    # Versioning
    report.version_enabled = node.parm("enableversion").eval()
    report.version = node.parm("version").eval()

    # Frame range
    report.frame_start = node.parm("f1").eval()
    report.frame_end = node.parm("f2").eval()
    report.frame_inc = node.parm("f3").eval()

    # Substeps
    report.substeps = node.parm("substeps").eval()

    # Flags
    report.is_time_dependent = node.parm("timedependent").eval()
    report.is_simulation = node.parm("cachesim").eval()
    report.save_in_background = node.parm("savebackground").eval()
    report.load_from_disk = node.parm("loadfromdisk").eval()

    # Warnings
    if report.save_in_background:
        warnings.append(
            "Save in Background is ON. Remote hbatch execution requires "
            "blocking saves. This will be forced OFF in the packaged .hip."
        )

    if report.load_from_disk:
        warnings.append(
            "Load from Disk is ON. The packaged .hip will have this OFF "
            "so the cache is cooked, not loaded."
        )

    if report.frame_start > report.frame_end:
        warnings.append(
            f"Frame start ({report.frame_start}) is after frame end "
            f"({report.frame_end})."
        )

    if report.frame_inc <= 0:
        warnings.append(
            f"Frame increment ({report.frame_inc}) is zero or negative."
        )

    report.warnings = warnings
    return report
