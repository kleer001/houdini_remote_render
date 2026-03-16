"""Save a portable .hip copy with rewritten File Cache output paths.

Temporarily modifies the internal File Cache SOP's parameters, saves the .hip,
then reverts. The artist's live scene is never permanently changed.
"""

import os
import zipfile
from pathlib import Path


def _snapshot_parm(parm):
    """Capture a parm's expression or raw value for later restoration."""
    import hou

    try:
        return (True, parm.expression(), parm.expressionLanguage())
    except hou.OperationFailed:
        try:
            return (False, parm.unexpandedString(), None)
        except hou.OperationFailed:
            return (False, parm.eval(), None)


def _restore_parm(parm, snapshot):
    """Restore a parm from a snapshot created by ``_snapshot_parm``."""
    has_expr, value, lang = snapshot
    if has_expr:
        parm.setExpression(value, lang)
    else:
        parm.set(value)


def _rewrite_filecache(fc, remote_cache_dir):
    """Rewrite a filecache node's output path and safety flags.

    Assumes the parent HDA is already unlocked. Deletes keyframes so
    ``set()`` is not silently ignored by active expressions.
    """
    file_method = fc.parm("filemethod").eval()
    if file_method == 0:  # Constructed
        fc.parm("basedir").deleteAllKeyframes()
        fc.parm("basedir").set(remote_cache_dir)
    else:  # Explicit
        orig_expanded = fc.parm("file").eval()
        filename = Path(orig_expanded).name
        fc.parm("file").deleteAllKeyframes()
        fc.parm("file").set(f"{remote_cache_dir}/{filename}")

    fc.parm("savebackground").deleteAllKeyframes()
    fc.parm("savebackground").set(False)
    fc.parm("loadfromdisk").deleteAllKeyframes()
    fc.parm("loadfromdisk").set(False)


_SNAPSHOT_PARMS = ("basedir", "file", "savebackground", "loadfromdisk")


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

    hda_node = filecache_node.parent()
    hda_node.allowEditingOfContents()

    snaps = {p: _snapshot_parm(filecache_node.parm(p)) for p in _SNAPSHOT_PARMS}

    try:
        _rewrite_filecache(filecache_node, remote_cache_dir)

        orig_hip_path = hou.hipFile.path()
        hou.hipFile.save(output_hip_path, save_to_recent_files=False)
        hou.hipFile.setName(orig_hip_path)

    finally:
        for pname, snap in snaps.items():
            _restore_parm(filecache_node.parm(pname), snap)
        hda_node.matchCurrentDefinition()

    return output_hip_path


def save_portable_hip_multi(
    filecache_nodes: list,
    output_hip_path: str,
    remote_cache_dir: str = "$HIP/../Cache",
) -> str:
    """Save a .hip with multiple File Cache nodes rewritten for remote execution.

    Like :func:`save_portable_hip` but rewrites all given filecache nodes in a
    single hip save. Each ``run_cache_NNN.sh`` loads the same hip but cooks a
    different filecache node.

    Args:
        filecache_nodes: List of ``hou.SopNode`` for each internal filecache.
        output_hip_path: Full path to save the portable .hip file.
        remote_cache_dir: Base directory for cache output.

    Returns:
        The output_hip_path on success.
    """
    import hou

    if not filecache_nodes:
        return output_hip_path

    os.makedirs(os.path.dirname(output_hip_path), exist_ok=True)

    # Unlock all HDAs and snapshot all parms.
    entries: list[dict] = []
    for fc in filecache_nodes:
        hda = fc.parent()
        hda.allowEditingOfContents()
        snaps = {p: _snapshot_parm(fc.parm(p)) for p in _SNAPSHOT_PARMS}
        entries.append({"fc": fc, "hda": hda, "snaps": snaps})

    try:
        for entry in entries:
            _rewrite_filecache(entry["fc"], remote_cache_dir)

        orig_hip_path = hou.hipFile.path()
        hou.hipFile.save(output_hip_path, save_to_recent_files=False)
        hou.hipFile.setName(orig_hip_path)

    finally:
        for entry in entries:
            for pname, snap in entry["snaps"].items():
                _restore_parm(entry["fc"].parm(pname), snap)
            entry["hda"].matchCurrentDefinition()

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
