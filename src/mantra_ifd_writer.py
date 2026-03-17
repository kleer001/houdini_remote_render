"""Generate IFD files from a Mantra ROP for license-free remote rendering.

Temporarily overrides Mantra parameters to write IFDs with embedded geometry
and shaders, then restores the original state. The artist's live scene is
never permanently changed.
"""

import os

from src.cache_scene_writer import _snapshot_parm, _restore_parm


# Parms we override on the internal mantra node during IFD generation.
_IFD_OVERRIDE_PARMS = (
    "soho_outputmode",
    "soho_diskfile",
    "soho_mkpath",
    "vm_inlinestorage",
    "vm_embedvex",
    "vm_binarygeometry",
    "vm_picture",
)


def generate_ifds(
    mantra_node,
    ifd_dir: str,
    shot_name: str,
    output_picture: str,
    frame_start: int,
    frame_end: int,
    frame_inc: int = 1,
) -> list[str]:
    """Generate one IFD file per frame from a Mantra ROP.

    Temporarily sets parameters to write self-contained IFDs (embedded
    geometry, embedded VEX, binary geo), renders the frame range, then
    restores all parameters.

    Args:
        mantra_node: The hou.RopNode for the internal Mantra (ifd) node.
        ifd_dir: Directory to write IFD files into.
        shot_name: Shot identifier used in the IFD filename pattern.
        output_picture: Render output path baked into the IFD (e.g.
            ``../Output/shot.$F4.exr``). Relative to CWD at render time.
        frame_start: First frame number.
        frame_end: Last frame number.
        frame_inc: Frame increment (default 1).

    Returns:
        List of generated IFD file paths.
    """
    import hou

    os.makedirs(ifd_dir, exist_ok=True)

    # Unlock HDA contents if the mantra node lives inside a locked HDA
    hda_node = mantra_node.parent()
    is_locked_hda = hda_node.matchesCurrentDefinition()
    if is_locked_hda:
        hda_node.allowEditingOfContents()

    # Snapshot all parms we'll override
    snaps = {}
    for pname in _IFD_OVERRIDE_PARMS:
        parm = mantra_node.parm(pname)
        if parm is not None:
            snaps[pname] = _snapshot_parm(parm)

    ifd_pattern = os.path.join(ifd_dir, f"{shot_name}.$F4.ifd")

    try:
        # Set IFD generation mode
        mantra_node.parm("soho_outputmode").deleteAllKeyframes()
        mantra_node.parm("soho_outputmode").set(1)

        mantra_node.parm("soho_diskfile").deleteAllKeyframes()
        mantra_node.parm("soho_diskfile").set(ifd_pattern)

        mantra_node.parm("soho_mkpath").deleteAllKeyframes()
        mantra_node.parm("soho_mkpath").set(1)

        # Embed geometry and shaders for self-contained IFDs
        mantra_node.parm("vm_inlinestorage").deleteAllKeyframes()
        mantra_node.parm("vm_inlinestorage").set(1)

        mantra_node.parm("vm_embedvex").deleteAllKeyframes()
        mantra_node.parm("vm_embedvex").set(1)

        mantra_node.parm("vm_binarygeometry").deleteAllKeyframes()
        mantra_node.parm("vm_binarygeometry").set(1)

        # Bake output path into IFD
        mantra_node.parm("vm_picture").deleteAllKeyframes()
        mantra_node.parm("vm_picture").set(output_picture)

        # Generate IFDs
        mantra_node.render(
            frame_range=(frame_start, frame_end, frame_inc),
        )

    finally:
        for pname, snap in snaps.items():
            _restore_parm(mantra_node.parm(pname), snap)
        if is_locked_hda:
            hda_node.matchCurrentDefinition()

    # Verify generated IFDs and collect paths
    generated = []
    for frame in range(frame_start, frame_end + 1, frame_inc):
        ifd_path = os.path.join(ifd_dir, f"{shot_name}.{frame:04d}.ifd")
        if os.path.isfile(ifd_path):
            generated.append(ifd_path)

    return generated
