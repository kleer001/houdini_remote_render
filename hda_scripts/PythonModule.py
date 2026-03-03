"""HDA-embedded Python entry points for karma_usd_packager.

All paths are relative to $HIP (the directory containing the .hip file).
"""

import os
import sys
from datetime import datetime


def _ensure_src_path(node):
    """Ensure the src/ directory is on sys.path for imports.

    Derives the repo root from the HDA's library file path:
    hda/karma_usd_packager.hdalc -> repo root is one level up.
    """
    hda_def = node.type().definition()
    if hda_def is None:
        return
    hda_dir = os.path.dirname(hda_def.libraryFilePath())
    repo_root = os.path.dirname(hda_dir)  # up from hda/ to repo root

    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


def _get_hip_dir():
    """Return the directory containing the current .hip file."""
    import hou
    return os.path.dirname(hou.hipFile.path())


def on_shot_name_changed(kwargs):
    """Parameter callback — flag red background if invalid."""
    import hou
    node = kwargs["node"]
    _ensure_src_path(node)

    from src.validator import validate_shot_name
    name = node.parm("shot_name").eval()
    ok, msg = validate_shot_name(name)
    if not ok:
        node.parm("shot_name").set(name)  # trigger UI refresh


def on_verify_clicked(kwargs):
    """Dry-run pipeline — populate log with what would happen."""
    import hou
    node = kwargs["node"]
    _ensure_src_path(node)
    log = []

    try:
        from src.validator import (
            validate_shot_name, validate_hip_saved,
            validate_shot_structure, validate_rop_connection,
        )
        from src.auditor import audit_stage

        shot_name = node.parm("shot_name").eval()

        # Validate shot name
        ok, msg = validate_shot_name(shot_name)
        if not ok:
            hou.ui.displayMessage(msg, severity=hou.severityType.Error)
            return
        log.append(f"Shot name: {shot_name} [OK]")

        # Validate HIP file
        ok, msg = validate_hip_saved()
        if not ok:
            hou.ui.displayMessage(msg, severity=hou.severityType.Error)
            return
        if msg:
            log.append(f"  {msg}")
        log.append("HIP file saved [OK]")

        # Report on shot directories ($HIP/shot_name/)
        hip_dir = _get_hip_dir()
        shot_dir = os.path.join(hip_dir, shot_name)
        log.append(f"Shot directory: {shot_dir}")
        ok, msg = validate_shot_structure(shot_dir)
        if not ok:
            log.append(f"  (will be created by Package & Stage)")
        else:
            log.append(f"  Directories: [OK]")

        # Check ROP connection
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
        import traceback
        log.append(traceback.format_exc())
        hou.ui.displayMessage(str(e), severity=hou.severityType.Error)

    node.parm("log_output").set("\n".join(log))


def on_package_clicked(kwargs):
    """Full pipeline run — package and stage."""
    import hou
    import tempfile
    node = kwargs["node"]
    _ensure_src_path(node)
    log = []

    try:
        from src.validator import validate_shot_name, validate_hip_saved
        from src.auditor import audit_stage, ensure_render_settings
        from src.output_injector import inject_output_paths
        from src.packager import flatten_stage, create_usdz
        from src.wrapper_writer import write_wrapper
        from src.manifest import ManifestData, write_manifest
        from src.platform_utils import ensure_dir

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

        # 2. Create shot directories at $HIP/shot_name/
        hip_dir = _get_hip_dir()
        shot_dir = os.path.join(hip_dir, shot_name)
        for d in ("Output", "Textures", "Cache", "Scenes", "Scripts"):
            ensure_dir(os.path.join(shot_dir, d))

        log.append(f"Shot: {shot_name}")
        log.append(f"Shot dir: {shot_dir}")

        # 3. Get stage from input
        input_node = node.inputs()[0] if node.inputs() else None
        if not input_node:
            hou.ui.displayMessage(
                "No input connected. Connect a LOP node to input 0.",
                severity=hou.severityType.Error,
            )
            return

        stage = input_node.stage()
        log.append("Stage acquired from input")

        # 4. Audit
        report = audit_stage(stage)
        ensure_render_settings(stage)
        for w in report.warnings:
            log.append(f"  ! {w}")

        # 5. Inject output paths
        inject_output_paths(stage)
        log.append("Output paths injected")

        # 6. Flatten and create USDZ
        staging_dir = tempfile.mkdtemp(prefix="usd_packager_")
        flat_path = flatten_stage(stage, staging_dir)
        log.append(f"Stage flattened")

        scenes_dir = os.path.join(shot_dir, "Scenes")
        usdz_filename = node.parm("usdz_filename").eval()
        usdz_path = os.path.join(scenes_dir, usdz_filename)

        create_usdz(flat_path, usdz_path)
        usdz_size = os.path.getsize(usdz_path) / (1024 * 1024)
        log.append(f"USDZ created: {usdz_path} ({usdz_size:.2f} MB)")

        # 7. Write wrapper
        wrapper_filename = node.parm("wrapper_filename").eval()
        wrapper_path = os.path.join(scenes_dir, wrapper_filename)

        write_wrapper(usdz_filename, {}, wrapper_path)
        log.append(f"Wrapper written: {wrapper_path}")

        # 8. Write manifest
        scripts_dir = os.path.join(shot_dir, "Scripts")
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
