"""Auto-wire the HDA into the network on creation."""


def onCreate(kwargs):
    """Called when the HDA is created."""
    import hou

    node = kwargs["node"]

    try:
        parent = node.parent()

        # Check if inside a LOP network
        if parent.childTypeCategory() != hou.lopNodeTypeCategory():
            return

        # If user had a node selected, wire up
        selected = hou.selectedNodes()
        if selected:
            sel = selected[0]

            # Connect selected -> HDA input
            node.setInput(0, sel, 0)

            # If selected node connects to a Karma ROP, insert HDA in between
            for output in sel.outputs():
                if output.type().name() in ("usdrender_rop", "karma"):
                    # Rewire: selected -> HDA -> ROP
                    output.setInput(0, node, 0)
                    break

        # Lock frame parms — auto-populated from downstream ROP
        for pname in ("frame_start", "frame_end"):
            p = node.parm(pname)
            if p:
                p.lock(True)

        # Set node color (deep red) and shape (X)
        node.setColor(hou.Color((0.8, 0.1, 0.1)))
        node.setUserData("nodeshape", "null")

        # Create network box
        netbox = parent.createNetworkBox()
        netbox.setComment("USD Packager")
        netbox.setColor(hou.Color((0.8, 0.1, 0.1)))
        netbox.addNode(node)
        netbox.fitAroundContents()

        # Open parameter pane
        node.setSelected(True, clear_all_selected=True)
        pane = hou.ui.paneTabOfType(hou.paneTabType.Parm)
        if pane:
            pane.setCurrentNode(node)

    except Exception as e:
        print(f"[karma_usd_packager] OnCreated warning: {e}")
