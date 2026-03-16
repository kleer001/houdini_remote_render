"""Auto-wire the Remote Mantra Render HDA into the network on creation."""


def onCreate(kwargs):
    """Called when the HDA is created."""
    import hou

    node = kwargs["node"]

    try:
        parent = node.parent()

        # Check if inside a ROP network
        if parent.childTypeCategory() != hou.ropNodeTypeCategory():
            return

        # If user had a node selected, wire up
        selected = hou.selectedNodes()
        if selected:
            sel = selected[0]
            node.setInput(0, sel, 0)

        # Set node color (forest green — distinct from deep red and amber)
        node.setColor(hou.Color((0.2, 0.6, 0.3)))

        # Create network box
        netbox = parent.createNetworkBox()
        netbox.setComment("Remote Mantra Render")
        netbox.setColor(hou.Color((0.2, 0.6, 0.3)))
        netbox.addNode(node)
        netbox.fitAroundContents()

        # Open parameter pane
        node.setSelected(True, clear_all_selected=True)
        pane = hou.ui.paneTabOfType(hou.paneTabType.Parm)
        if pane:
            pane.setCurrentNode(node)

    except Exception as e:
        print(f"[remote_mantra_render] OnCreated warning: {e}")
