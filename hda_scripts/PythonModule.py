"""HDA-embedded Python entry points for karma_usd_packager.

Called by HDA parameter callbacks and buttons.
"""

import os
import sys
from pathlib import Path
from datetime import datetime


def _ensure_src_path():
    """Ensure the src/ directory is on sys.path for imports."""
    # The src dir lives next to the hda_scripts dir
    src_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
    if src_dir not in sys.path:
        sys.path.insert(0, os.path.dirname(src_dir))


def get_shot_root():
    """Called by Shot Root expression parameter."""
    import hou
    try:
        from src.platform_utils import get_shot_root_from_hip
        return get_shot_root_from_hip()
    except Exception:
        return ""


def on_shot_name_changed(kwargs):
    """Parameter callback — flag red background if invalid."""
    import hou
    node = kwargs["node"]
    parm = node.parm("shot_name")
    name = parm.eval()

    from src.validator import validate_shot_name
    ok, msg = validate_shot_name(name)

    template = parm.parmTemplate()
    if not ok:
        parm.set(parm.eval())  # trigger UI refresh


def on_verify_clicked(kwargs):
    """Dry-run pipeline — populate log with what would happen."""
    import hou
    _ensure_src_path()
    node = kwargs["node"]
    log = []

    try:
        from src.validator import (
            validate_shot_name, validate_hip_saved,
            validate_shot_structure, validate_rop_connection,
        )
        from src.auditor import audit_stage
        from src.classifier import classify_dependencies
        from src.converter import convert_all

        shot_name = node.parm("shot_name").eval()

        # Validate
        ok, msg = validate_shot_name(shot_name)
        if not ok:
            hou.ui.displayMessage(msg, severity=hou.severityType.Error)
            return
        log.append(f"Shot name: {shot_name} [OK]")

        ok, msg = validate_hip_saved()
        if not ok:
            hou.ui.displayMessage(msg, severity=hou.severityType.Error)
            return
        if msg:
            log.append(f"  {msg}")
        log.append("HIP file saved [OK]")

        shot_root = node.parm("shot_root").eval()
        ok, msg = validate_shot_structure(shot_root)
        if not ok:
            log.append(f"Shot structure: {msg}")
        else:
            log.append(f"Shot root: {shot_root} [OK]")

        ok, msg = validate_rop_connection(node)
        if msg:
            log.append(f"  {msg}")

        # Audit stage
        input_node = node.inputs()[0] if node.inputs() else None
        if input_node:
            stage = input_node.stage()
            report = audit_stage(stage)
            log.append(f"Render settings: {'found' if report.has_render_settings else 'MISSING'}")
            log.append(f"Camera: {'found' if report.has_camera else 'MISSING'}")
            log.append(f"Render products: {'found' if report.has_render_products else 'MISSING'}")
            log.append(f"Instance count: {report.instance_count:,}")
            for w in report.warnings:
                log.append(f"  ! {w}")
        else:
            log.append("! No input connected — cannot audit stage")

        log.append("")
        log.append("=== VERIFY COMPLETE (dry run) ===")

    except Exception as e:
        log.append(f"ERROR: {e}")
        hou.ui.displayMessage(str(e), severity=hou.severityType.Error)

    node.parm("log_output").set("\n".join(log))


def on_package_clicked(kwargs):
    """Full pipeline run — package and stage."""
    import hou
    import tempfile
    _ensure_src_path()
    node = kwargs["node"]
    log = []

    try:
        from src.validator import (
            validate_shot_name, validate_hip_saved, validate_shot_structure,
        )
        from src.auditor import audit_stage, ensure_render_settings
        from src.classifier import classify_dependencies
        from src.converter import convert_all
        from src.gatherer import (
            gather_textures, gather_caches,
            rewrite_paths_in_layer, make_cache_relative_path,
        )
        from src.output_injector import inject_output_paths
        from src.packager import flatten_stage, create_usdz
        from src.wrapper_writer import write_wrapper
        from src.manifest import ManifestData, write_manifest

        shot_name = node.parm("shot_name").eval()

        # 1. Validate
        ok, msg = validate_shot_name(shot_name)
        if not ok:
            hou.ui.displayMessage(msg, severity=hou.severityType.Error)
            return

        ok, msg = validate_hip_saved()
        if not ok:
            hou.ui.displayMessage(msg, severity=hou.severityType.Error)
            return

        shot_root = node.parm("shot_root").eval()
        ok, msg = validate_shot_structure(shot_root)
        if not ok:
            hou.ui.displayMessage(
                f"Shot structure issue:\n{msg}\n\nCreate missing directories and retry.",
                severity=hou.severityType.Error,
            )
            return

        log.append(f"Shot: {shot_name}")
        log.append(f"Root: {shot_root}")

        # 2. Get stage from input
        input_node = node.inputs()[0] if node.inputs() else None
        if not input_node:
            hou.ui.displayMessage(
                "No input connected. Connect a LOP node to input 0.",
                severity=hou.severityType.Error,
            )
            return

        stage = input_node.stage()
        log.append("Stage acquired from input")

        # 3. Audit
        report = audit_stage(stage)
        ensure_render_settings(stage)
        for w in report.warnings:
            log.append(f"  ! {w}")

        # 4. Inject output paths
        inject_output_paths(stage)
        log.append("Output paths injected")

        # 5. Flatten and create USDZ
        staging_dir = tempfile.mkdtemp(prefix="usd_packager_")
        flat_path = flatten_stage(stage, staging_dir)
        log.append(f"Stage flattened to {flat_path}")

        scenes_dir = os.path.join(shot_root, "Scenes")
        usdz_filename = node.parm("usdz_filename").eval()
        usdz_path = os.path.join(scenes_dir, usdz_filename)

        create_usdz(flat_path, usdz_path)
        usdz_size = os.path.getsize(usdz_path) / (1024 * 1024)
        log.append(f"USDZ created: {usdz_path} ({usdz_size:.2f} MB)")

        # 6. Write wrapper
        wrapper_filename = node.parm("wrapper_filename").eval()
        wrapper_path = os.path.join(scenes_dir, wrapper_filename)
        cache_path_map = {}  # Populated if caches are gathered

        write_wrapper(usdz_filename, cache_path_map, wrapper_path)
        log.append(f"Wrapper written: {wrapper_path}")

        # 7. Write manifest
        scripts_dir = os.path.join(shot_root, "Scripts")
        manifest_path = os.path.join(scripts_dir, f"{shot_name}_manifest.txt")

        manifest_data = ManifestData(
            shot_name=shot_name,
            houdini_version=hou.applicationVersionString(),
            generated_at=datetime.now().isoformat(),
            usdz_path=usdz_path,
            wrapper_path=wrapper_path,
            warnings=report.warnings,
            total_usdz_size_mb=usdz_size,
        )
        write_manifest(manifest_path, manifest_data)
        log.append(f"Manifest written: {manifest_path}")

        log.append("")
        log.append("=== PACKAGING COMPLETE ===")

    except Exception as e:
        log.append(f"ERROR: {e}")
        import traceback
        log.append(traceback.format_exc())
        hou.ui.displayMessage(str(e), severity=hou.severityType.Error)

    node.parm("log_output").set("\n".join(log))


def on_get_from_rop_clicked(kwargs):
    """Walk outputs to find Karma ROP and read frame range."""
    import hou
    node = kwargs["node"]

    for output in node.outputs():
        if output.type().name() in ("usdrender_rop", "karma"):
            try:
                start = output.parm("f1").eval()
                end = output.parm("f2").eval()
                node.parm("frame_start").set(start)
                node.parm("frame_end").set(end)
                return
            except Exception:
                pass

    hou.ui.displayMessage(
        "No Karma ROP found downstream. Connect this node before a Karma ROP.",
        severity=hou.severityType.Warning,
    )
