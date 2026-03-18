#!/usr/bin/env hython
"""Create the Redshift USD Packager HDA definition.

Run via: hython src/scripts/create_redshift_hda.py

Creates src/hda/redshift_usd_packager.hdalc with all parameters and
embedded scripts from src/hda_scripts_redshift/.
"""

import hou
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HDA_PATH = os.path.join(REPO_ROOT, "src", "hda", "redshift_usd_packager.hdalc")
SCRIPTS_DIR = os.path.join(REPO_ROOT, "src", "hda_scripts_redshift")


def read_script(filename):
    """Read a script file from src/hda_scripts_redshift/."""
    path = os.path.join(SCRIPTS_DIR, filename)
    with open(path, "r") as f:
        return f.read()


def create_hda():
    """Create the Redshift USD Packager HDA."""

    # Create a temporary subnet LOP to define the HDA from
    stage = hou.node("/stage")
    if stage is None:
        stage = hou.node("/obj").createNode("lopnet", "tmp_stage")

    subnet = stage.createNode("subnet", "redshift_usd_packager")

    # Create HDA definition from the subnet
    hda_def = subnet.createDigitalAsset(
        name="redshift_usd_packager",
        hda_file_name=HDA_PATH,
        description="Redshift USD Packager",
        min_num_inputs=1,
        max_num_inputs=1,
    )

    # Get the definition for editing
    node_type = hda_def.type()
    definition = node_type.definition()

    # --- Add parameters ---
    ptg = definition.parmTemplateGroup()

    # === Packaging tab ===
    pkg_folder = hou.FolderParmTemplate(
        "pkg_folder", "Packaging", folder_type=hou.folderType.Tabs
    )

    pkg_folder.addParmTemplate(hou.StringParmTemplate(
        "shot_name", "Shot Name", 1,
        default_value=("shot_name",),
        script_callback="hou.phm().on_shot_name_changed(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
    ))
    pkg_folder.addParmTemplate(hou.IntParmTemplate(
        "pod_number", "Pod", 1, default_value=(1,),
        min=1, max=10,
        script_callback="hou.phm().on_field_changed(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
    ))
    pkg_folder.addParmTemplate(hou.IntParmTemplate(
        "team_number", "Team", 1, default_value=(1,),
        min=1, max=10,
        script_callback="hou.phm().on_field_changed(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
    ))
    pkg_folder.addParmTemplate(hou.StringParmTemplate(
        "version", "Version", 1, default_value=("1",),
        script_callback="hou.phm().on_field_changed(kwargs)",
        script_callback_language=hou.scriptLanguage.Python,
    ))

    pkg_folder.addParmTemplate(hou.SeparatorParmTemplate("sep1"))

    # Output format menu
    output_format = hou.MenuParmTemplate(
        "output_format", "Output Format",
        ("exr", "png", "jpg", "tiff"),
        ("EXR", "PNG", "JPG", "TIFF"),
        default_value=0,
    )
    pkg_folder.addParmTemplate(output_format)

    pkg_folder.addParmTemplate(hou.IntParmTemplate(
        "frame_start", "Frame Start", 1, default_value=(1001,),
    ))
    pkg_folder.addParmTemplate(hou.IntParmTemplate(
        "frame_end", "Frame End", 1, default_value=(1100,),
    ))

    pkg_folder.addParmTemplate(hou.SeparatorParmTemplate("sep2"))

    # Verify button
    pkg_folder.addParmTemplate(hou.ButtonParmTemplate(
        "btn_verify", "Verify",
        script_callback="exec(hou.pwd().type().definition().sections()['btn_verify.py'].contents())",
        script_callback_language=hou.scriptLanguage.Python,
    ))

    # Package button
    pkg_folder.addParmTemplate(hou.ButtonParmTemplate(
        "btn_package", "Package for Remote",
        script_callback="exec(hou.pwd().type().definition().sections()['btn_package.py'].contents())",
        script_callback_language=hou.scriptLanguage.Python,
    ))

    # Verified hidden parm
    verified = hou.IntParmTemplate("verified", "Verified", 1, default_value=(0,))
    verified.hide(True)
    pkg_folder.addParmTemplate(verified)

    pkg_folder.addParmTemplate(hou.SeparatorParmTemplate("sep3"))

    # Log output
    log_parm = hou.StringParmTemplate(
        "log_output", "Log", 1,
        default_value=("",),
        string_type=hou.stringParmType.Regular,
    )
    log_parm.setNumComponents(1)
    # Make it multiline by setting tags
    log_parm.setTags({"editor": "1", "editorlines": "15"})
    pkg_folder.addParmTemplate(log_parm)

    ptg.append(pkg_folder)

    # === Redshift tab ===
    rs_folder = hou.FolderParmTemplate(
        "rs_folder", "Redshift", folder_type=hou.folderType.Tabs
    )

    # GPU device menu
    gpu_menu = hou.MenuParmTemplate(
        "gpu_device", "GPU Device",
        ("all", "0", "1", "2", "3"),
        ("All GPUs", "GPU 0", "GPU 1", "GPU 2", "GPU 3"),
        default_value=0,
    )
    rs_folder.addParmTemplate(gpu_menu)

    rs_folder.addParmTemplate(hou.IntParmTemplate(
        "texture_cache_gb", "Texture Cache (GB)", 1,
        default_value=(0,),
        min=0, max=32,
        help="Texture cache budget in GB. 0 = use default.",
    ))

    rs_folder.addParmTemplate(hou.StringParmTemplate(
        "cache_path", "Cache Path", 1,
        default_value=("",),
        string_type=hou.stringParmType.FileReference,
        help="Redshift cache folder. Empty = use default.",
    ))

    rs_folder.addParmTemplate(hou.ToggleParmTemplate(
        "skip_postfx", "Skip Post Effects", default_value=False,
    ))

    rs_folder.addParmTemplate(hou.ToggleParmTemplate(
        "restart_delegate", "Restart Delegate Per Frame", default_value=False,
        help="Force the render delegate to restart every frame. "
             "Use for scenes with animated attributes that don't update correctly.",
    ))

    rs_folder.addParmTemplate(hou.StringParmTemplate(
        "ocio_config", "OCIO Config", 1,
        default_value=("",),
        string_type=hou.stringParmType.FileReference,
        help="Path to OCIO config file. Empty = use default (ACEScg).",
    ))

    ptg.append(rs_folder)

    # === Footer: version stamp (disabled — not user-editable) ===
    version_parm = hou.StringParmTemplate(
        "hda_version", "HDA Version", 1,
        default_value=("v0.1.72 (2d10711)",),
    )
    version_parm.setTags({"spare_category": "Version"})
    # Always-true disable condition locks the field from user editing
    version_parm.setConditional(
        hou.parmCondType.DisableWhen,
        '{ hda_version == "" } { hda_version != "" }',
    )
    ptg.append(version_parm)

    # Apply parameter template group
    definition.setParmTemplateGroup(ptg)

    # --- Embed scripts ---
    sections = definition.sections()

    # PythonModule
    definition.addSection("PythonModule", read_script("PythonModule.py"))
    # Set the PythonModule to be recognized as the node's Python module
    definition.setExtraFileOption("PythonModule/IsPython", True)

    # OnCreated
    definition.addSection("OnCreated", read_script("OnCreated.py"))
    definition.setExtraFileOption("OnCreated/IsPython", True)

    # Button scripts
    definition.addSection("btn_verify.py", read_script("btn_verify.py"))
    definition.setExtraFileOption("btn_verify.py/IsPython", True)

    definition.addSection("btn_package.py", read_script("btn_package.py"))
    definition.setExtraFileOption("btn_package.py/IsPython", True)

    # --- Set node properties ---
    # Icon
    definition.setIcon("ROP_redshift_ROP")

    # Save
    definition.save(HDA_PATH)

    print(f"HDA created: {HDA_PATH}")
    print(f"  Type: {node_type.name()}")
    print(f"  Category: {node_type.category().name()}")
    print(f"  Sections: {list(definition.sections().keys())}")

    # Clean up (subnet may already be destroyed by createDigitalAsset)
    try:
        subnet.destroy()
    except hou.ObjectWasDeleted:
        pass


if __name__ == "__main__":
    create_hda()
