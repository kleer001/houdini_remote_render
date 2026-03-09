"""Save a portable .hip copy with rewritten File Cache output paths.

Temporarily modifies the internal File Cache SOP's parameters, saves the .hip,
then reverts. The artist's live scene is never permanently changed.
"""

import os
import zipfile
from pathlib import Path


def save_portable_hip(
    filecache_node,
    output_hip_path: str,
    remote_cache_dir: str = "$HIP/../Cache",
) -> str:
    """Save a copy of the current .hip with File Cache output rewritten.

    Temporarily changes the filecache node's output path so caches land in
    the remote package's Cache/ directory, saves the .hip, then reverts all
    changes.

    Args:
        filecache_node: The hou.SopNode for the internal File Cache.
        output_hip_path: Full path to save the portable .hip file.
        remote_cache_dir: Base directory for cache output in the saved .hip.
            Defaults to "$HIP/../Cache" which resolves correctly when the .hip
            is inside Scenes/.

    Returns:
        The output_hip_path on success.
    """
    import hou

    os.makedirs(os.path.dirname(output_hip_path), exist_ok=True)

    # Snapshot original state — parms may have expressions (from HDA linking)
    # so we save expression/value pairs and restore the correct type.
    def _snapshot_parm(parm):
        """Return (has_expr, expr_or_value) for later restoration."""
        try:
            return (True, parm.expression(), parm.expressionLanguage())
        except hou.OperationFailed:
            # No expression — it's a raw value
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

    # The filecache lives inside a locked HDA — unlock so we can modify parms
    hda_node = filecache_node.parent()
    hda_node.allowEditingOfContents()

    snap_basedir = _snapshot_parm(filecache_node.parm("basedir"))
    snap_file = _snapshot_parm(filecache_node.parm("file"))
    snap_savebackground = _snapshot_parm(filecache_node.parm("savebackground"))
    snap_loadfromdisk = _snapshot_parm(filecache_node.parm("loadfromdisk"))

    try:
        # Rewrite for remote execution — delete expressions first so we can set values
        file_method = filecache_node.parm("filemethod").eval()
        if file_method == 0:  # Constructed
            filecache_node.parm("basedir").deleteAllKeyframes()
            filecache_node.parm("basedir").set(remote_cache_dir)
        else:  # Explicit
            orig_expanded = filecache_node.parm("file").eval()
            filename = Path(orig_expanded).name
            filecache_node.parm("file").deleteAllKeyframes()
            filecache_node.parm("file").set(f"{remote_cache_dir}/{filename}")

        # Force blocking saves and ensure it cooks (not loads)
        filecache_node.parm("savebackground").deleteAllKeyframes()
        filecache_node.parm("savebackground").set(False)
        filecache_node.parm("loadfromdisk").deleteAllKeyframes()
        filecache_node.parm("loadfromdisk").set(False)

        # Save a copy: save to the new path, then restore the original hip path.
        # Using save() with a path argument acts like "Save As", so we must
        # restore the original path afterward.
        orig_hip_path = hou.hipFile.path()
        hou.hipFile.save(output_hip_path, save_to_recent_files=False)
        # Restore original hip file path so the artist's session is unchanged
        hou.hipFile.setName(orig_hip_path)

    finally:
        # Always revert to original state (expressions or raw values)
        _restore_parm(filecache_node.parm("basedir"), snap_basedir)
        _restore_parm(filecache_node.parm("file"), snap_file)
        _restore_parm(filecache_node.parm("savebackground"), snap_savebackground)
        _restore_parm(filecache_node.parm("loadfromdisk"), snap_loadfromdisk)
        # Re-lock the HDA contents
        hda_node.matchCurrentDefinition()

    return output_hip_path


def backup_hip_as_zip(zip_path: str) -> str:
    """Zip the current .hip file as a backup.

    Args:
        zip_path: Full path for the output .zip file.

    Returns:
        The zip_path on success.
    """
    import hou

    hip_path = hou.hipFile.path()
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(hip_path, Path(hip_path).name)

    return zip_path
