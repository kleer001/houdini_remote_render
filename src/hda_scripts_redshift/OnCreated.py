"""OnCreated callback for the Redshift USD Packager HDA.

Sets node appearance (Redshift brand red, X shape) and auto-wires
into the LOP network.
"""


def OnCreated(kwargs):
    import hou

    node = kwargs["node"]

    # Lock frame parms — auto-populated from downstream ROP
    for pname in ("frame_start", "frame_end"):
        p = node.parm(pname)
        if p:
            p.lock(True)

    # Redshift brand red
    node.setColor(hou.Color((0.8, 0.15, 0.15)))
    node.setUserData("nodeshape", "clipped_right")

    # Auto-wire: connect to the first available output of the
    # nearest upstream LOP node.
    parent = node.parent()
    if parent is None:
        return

    # Create network box around the node
    try:
        box = parent.createNetworkBox()
        box.setComment("Remote Redshift Render")
        box.addNode(node)
        box.fitAroundContents()
    except Exception:
        pass
