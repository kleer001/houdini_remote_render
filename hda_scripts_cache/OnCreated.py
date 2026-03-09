"""Auto-wire the Remote File Cache HDA into the network on creation."""


def onCreate(kwargs):
    """Called when the HDA is created."""
    import hou

    node = kwargs["node"]

    try:
        parent = node.parent()

        # Check if inside a SOP network
        if parent.childTypeCategory() != hou.sopNodeTypeCategory():
            return

        # If user had a node selected, wire up
        selected = hou.selectedNodes()
        if selected:
            sel = selected[0]
            node.setInput(0, sel, 0)

        # Set node color (amber — distinct from teal render packager)
        node.setColor(hou.Color((0.8, 0.5, 0.1)))

        # Create network box
        netbox = parent.createNetworkBox()
        netbox.setComment("Remote File Cache")
        netbox.setColor(hou.Color((0.8, 0.5, 0.1)))
        netbox.addNode(node)
        netbox.fitAroundContents()

        # Open parameter pane
        node.setSelected(True, clear_all_selected=True)
        pane = hou.ui.paneTabOfType(hou.paneTabType.Parm)
        if pane:
            pane.setCurrentNode(node)

    except Exception as e:
        print(f"[remote_file_cache] OnCreated warning: {e}")
