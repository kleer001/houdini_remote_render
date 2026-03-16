"""Save a portable .hip copy with rewritten Mantra output paths.

Temporarily modifies the Mantra ROP's vm_picture parameter, saves the .hip,
then reverts. The artist's live scene is never permanently changed.
"""

import os

from src.cache_scene_writer import _snapshot_parm, _restore_parm


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

    # Unlock HDA contents if the mantra node lives inside a locked HDA
    hda_node = mantra_node.parent()
    is_locked_hda = hda_node.matchesCurrentDefinition()
    if is_locked_hda:
        hda_node.allowEditingOfContents()

    snap_picture = _snapshot_parm(mantra_node.parm("vm_picture"))

    try:
        # Use unexpandedString to preserve $F4 and other variables in the filename
        try:
            orig_picture = mantra_node.parm("vm_picture").unexpandedString()
        except hou.OperationFailed:
            orig_picture = mantra_node.parm("vm_picture").eval()
        filename = os.path.basename(orig_picture) if orig_picture else "render.$F4.exr"
        mantra_node.parm("vm_picture").deleteAllKeyframes()
        mantra_node.parm("vm_picture").set(f"{remote_output_dir}/{filename}")

        orig_hip_path = hou.hipFile.path()
        hou.hipFile.save(output_hip_path, save_to_recent_files=False)
        hou.hipFile.setName(orig_hip_path)

    finally:
        _restore_parm(mantra_node.parm("vm_picture"), snap_picture)
        if is_locked_hda:
            hda_node.matchCurrentDefinition()

    return output_hip_path
