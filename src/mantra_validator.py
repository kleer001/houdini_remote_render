"""Validation guards for the Mantra Render packaging pipeline.

Checks that a Mantra ROP exists, has valid parameters, and is ready
for remote packaging.
"""

import re

_HYPHEN_BEFORE_FRAME_VAR = re.compile(r"-\$F")


def validate_mantra_node(node) -> tuple[bool, str]:
    """Check that the node is a valid Mantra ROP.

    Mantra's internal node type name is 'ifd'. Accepts any type starting
    with 'ifd' (e.g. 'ifd', 'ifd::2.0').

    Args:
        node: A hou.RopNode (or None).

    Returns:
        (True, "") on success, (False, reason) on failure.
    """
    if node is None:
        return False, "No Mantra ROP node found."

    type_name = node.type().name()
    if not type_name.startswith("ifd"):
        return False, (
            f"Node is type '{type_name}', expected Mantra ROP ('ifd')."
        )

    return True, ""


def validate_output_picture(path: str) -> tuple[bool, str]:
    """Check that the Mantra output picture path is non-empty.

    Returns:
        (True, "") on success, (False, reason) on failure.
    """
    if not path or not path.strip():
        return False, "Mantra output picture (vm_picture) is empty."

    return True, ""


def warn_output_picture(path: str) -> str | None:
    """Return a warning string if the output path has known pitfalls, else None.

    Checks for hyphens before $F variables which cause MPlay to interpret
    frame numbers as negative.
    """
    if path and _HYPHEN_BEFORE_FRAME_VAR.search(path):
        return (
            "Output filename contains '-$F' — MPlay may interpret this as a "
            "negative frame number. Use '_$F' or '.$F' instead."
        )
    return None
