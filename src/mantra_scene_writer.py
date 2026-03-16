"""Save a portable .hip copy with rewritten Mantra output paths.

Temporarily modifies the Mantra ROP's vm_picture parameter, saves the .hip,
then reverts. The artist's live scene is never permanently changed.
"""

import os
from pathlib import Path


def save_portable_hip(
    mantra_node,
    output_hip_path: str,
    remote_output_dir: str = "$HIP/../Output",
) -> str:
    """Save a copy of the current .hip with Mantra output rewritten.

    Temporarily changes the Mantra ROP's vm_picture so renders land in
    the remote package's Output/ directory, saves the .hip, then reverts.

    Args:
        mantra_node: The hou.RopNode for the Mantra ROP.
        output_hip_path: Full path to save the portable .hip file.
        remote_output_dir: Base directory for render output in the saved .hip.
            Defaults to "$HIP/../Output" which resolves correctly when the .hip
            is inside Scenes/.

    Returns:
        The output_hip_path on success.
    """
    import hou

    os.makedirs(os.path.dirname(output_hip_path), exist_ok=True)

    def _snapshot_parm(parm):
        """Return (has_expr, expr_or_value, language) for later restoration."""
        try:
            return (True, parm.expression(), parm.expressionLanguage())
        except hou.OperationFailed:
            try:
                return (False, parm.unexpandedString(), None)
            except hou.OperationFailed:
                return (False, parm.eval(), None)

    def _restore_parm(parm, snapshot):
        """Restore a parm from its snapshot."""
        has_expr, value, lang = snapshot
        if has_expr:
            parm.setExpression(value, lang)
        else:
            parm.set(value)

    # Snapshot vm_picture
    snap_picture = _snapshot_parm(mantra_node.parm("vm_picture"))

    try:
        # Rewrite output path for remote execution
        orig_picture = mantra_node.parm("vm_picture").eval()
        filename = Path(orig_picture).name if orig_picture else "render.$F4.exr"
        mantra_node.parm("vm_picture").deleteAllKeyframes()
        mantra_node.parm("vm_picture").set(f"{remote_output_dir}/{filename}")

        # Save a copy
        orig_hip_path = hou.hipFile.path()
        hou.hipFile.save(output_hip_path, save_to_recent_files=False)
        hou.hipFile.setName(orig_hip_path)

    finally:
        _restore_parm(mantra_node.parm("vm_picture"), snap_picture)

    return output_hip_path
