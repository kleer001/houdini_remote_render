"""Validation guards for the Remote File Cache packaging pipeline.

Checks that a File Cache SOP exists, has valid parameters, and is ready
for remote packaging.
"""


def validate_cache_node(node) -> tuple[bool, str]:
    """Check that the node is a valid File Cache SOP.

    Args:
        node: A hou.SopNode (or None).

    Returns:
        (True, "") on success, (False, reason) on failure.
    """
    if node is None:
        return False, "No File Cache node found inside this HDA."

    type_name = node.type().name()
    if not type_name.startswith("filecache"):
        return False, (
            f"Internal node is type '{type_name}', expected 'filecache'."
        )

    return True, ""


def validate_frame_range(start: float, end: float, inc: float) -> tuple[bool, str]:
    """Sanity-check frame range values.

    Returns:
        (True, "") on success, (False, reason) on failure.
    """
    if inc <= 0:
        return False, f"Frame increment must be positive, got {inc}."

    if start > end:
        return False, (
            f"Frame start ({start}) is after frame end ({end})."
        )

    return True, ""


def validate_output_path(output_path: str) -> tuple[bool, str]:
    """Check that the File Cache output path is non-empty.

    Returns:
        (True, "") on success, (False, reason) on failure.
    """
    if not output_path or not output_path.strip():
        return False, "File Cache output path is empty."

    return True, ""
