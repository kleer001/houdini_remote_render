"""HDA-embedded Python entry points for karma_usd_packager.

All paths are relative to $HIP (the directory containing the .hip file).
"""

import os
import shutil
import sys
import time
import zipfile
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
    warnings = []
    has_failure = False

    try:
        from src.validator import (
            validate_shot_name, validate_hip_saved,
            validate_shot_structure, validate_rop_connection,
        )
        from src.auditor import audit_stage

        shot_name = node.parm("shot_name").eval()
        SEP = "=" * 48

        log.append(f"Verify — {shot_name}")
        log.append(SEP)
        log.append("")

        # [1/5] Shot name
        ok, msg = validate_shot_name(shot_name)
        if not ok:
            hou.ui.displayMessage(msg, severity=hou.severityType.Error)
            return
        log.append(f"  [1/5] Shot name ........... PASS")

        # [2/5] HIP file
        ok, msg = validate_hip_saved()
        if not ok:
            hou.ui.displayMessage(msg, severity=hou.severityType.Error)
            return
        log.append(f"  [2/5] HIP file ............ PASS")
        if msg:
            warnings.append(msg)

        # [3/5] Shot directory
        hip_dir = _get_hip_dir()
        shot_dir = os.path.join(hip_dir, shot_name)
        ok, msg = validate_shot_structure(shot_dir)
        if not ok:
            log.append(f"  [3/5] Shot directory ...... WILL CREATE")
        else:
            log.append(f"  [3/5] Shot directory ...... PASS")

        # [4/5] Karma ROP
        ok, msg = validate_rop_connection(node)
        if ok:
            log.append(f"  [4/5] Karma ROP ........... PASS")
        else:
            log.append(f"  [4/5] Karma ROP ........... WARN (not connected)")
            warnings.append("No Karma ROP found downstream")

        # [5/5] Stage audit
        input_node = node.inputs()[0] if node.inputs() else None
        if input_node:
            stage = input_node.stage()
            if stage is None:
                hou.ui.displayMessage(
                    "Input node returned an empty stage. Check the LOP network.",
                    severity=hou.severityType.Error,
                )
                return
            report = audit_stage(stage)

            audit_issues = []
            if not report.has_render_settings:
                audit_issues.append("render settings missing (will be created)")
            if not report.has_camera:
                audit_issues.append("no camera found")
            if not report.has_render_products:
                audit_issues.append("no render products found")

            if audit_issues:
                log.append(f"  [5/5] Stage audit ......... WARN")
            else:
                log.append(f"  [5/5] Stage audit ......... PASS")

            log.append(f"        Render settings       {'found' if report.has_render_settings else 'MISSING (will create)'}")
            log.append(f"        Camera                {'found' if report.has_camera else 'MISSING'}")
            log.append(f"        Render products       {'found' if report.has_render_products else 'MISSING'}")
            log.append(f"        Instances             {report.instance_count:,}")

            warnings.extend(report.warnings)
            warnings.extend(audit_issues)
        else:
            log.append(f"  [5/5] Stage audit ......... FAIL (no input)")
            has_failure = True

        # Warnings section
        if warnings:
            log.append("")
            log.append("  Warnings:")
            for w in warnings:
                log.append(f"    ! {w}")

        # Final status
        log.append("")
        log.append(SEP)
        if has_failure:
            log.append("ISSUES FOUND — see above before packaging.")
        elif warnings:
            log.append("READY TO GO — review warnings above.")
        else:
            log.append("All checks passed. READY TO GO.")

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
        SEP = "=" * 48

        # 1. Validate
        ok, msg = validate_shot_name(shot_name)
        if not ok:
            hou.ui.displayMessage(msg, severity=hou.severityType.Error)
            return

        ok, msg = validate_hip_saved()
        if not ok:
            hou.ui.displayMessage(msg, severity=hou.severityType.Error)
            return
        if msg:
            if not hou.ui.displayConfirmation(msg + "\n\nContinue anyway?"):
                return

        t0 = time.time()

        log.append(f"Package — {shot_name}")
        log.append(SEP)
        log.append("")
        log.append(f"  [1/8] Validating .......... PASS")

        # 2. Create shot directories at $HIP/shot_name/
        hip_dir = _get_hip_dir()
        shot_dir = os.path.join(hip_dir, shot_name)
        for d in ("Output", "Textures", "Cache", "Scenes", "Scripts"):
            ensure_dir(os.path.join(shot_dir, d))
        log.append(f"  [2/8] Creating dirs ....... DONE")

        # 3. Backup current .hip file as a zip into the shot directory
        hip_path = hou.hipFile.path()
        hip_basename = os.path.basename(hip_path)
        zip_name = hip_basename + ".zip"
        zip_path = os.path.join(shot_dir, zip_name)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(hip_path, hip_basename)
        zip_size = os.path.getsize(zip_path) / (1024 * 1024)
        log.append(f"  [3/8] Backing up HIP ..... {zip_size:.2f} MB")

        # 4. Get stage from input
        input_node = node.inputs()[0] if node.inputs() else None
        if not input_node:
            hou.ui.displayMessage(
                "No input connected. Connect a LOP node to input 0.",
                severity=hou.severityType.Error,
            )
            return

        stage = input_node.stage()
        if stage is None:
            hou.ui.displayMessage(
                "Input node returned an empty stage. Check the LOP network.",
                severity=hou.severityType.Error,
            )
            return

        # 5. Audit
        report = audit_stage(stage)
        ensure_render_settings(stage)
        log.append(f"  [4/8] Auditing stage ...... PASS")

        # 6. Inject output paths
        inject_output_paths(stage)
        log.append(f"  [5/8] Injecting paths ..... DONE")

        # 7. Flatten and create USDZ
        staging_dir = tempfile.mkdtemp(prefix="usd_packager_")
        flat_path = flatten_stage(stage, staging_dir)

        scenes_dir = os.path.join(shot_dir, "Scenes")
        usdz_filename = node.parm("usdz_filename").eval()
        usdz_path = os.path.join(scenes_dir, usdz_filename)

        if os.path.exists(usdz_path):
            if not hou.ui.displayConfirmation(
                f"USDZ already exists:\n{usdz_path}\n\nOverwrite?"
            ):
                return

        create_usdz(flat_path, usdz_path)
        shutil.rmtree(staging_dir, ignore_errors=True)
        usdz_size = os.path.getsize(usdz_path) / (1024 * 1024)
        log.append(f"  [6/8] Creating USDZ ....... {usdz_size:.2f} MB")

        # 8. Write wrapper
        wrapper_filename = node.parm("wrapper_filename").eval()
        wrapper_path = os.path.join(scenes_dir, wrapper_filename)

        write_wrapper(usdz_filename, {}, wrapper_path)
        log.append(f"  [7/8] Writing wrapper ..... DONE")

        # 9. Write manifest
        manifest_path = os.path.join(shot_dir, f"{shot_name}_manifest.txt")

        elapsed = time.time() - t0
        manifest_data = ManifestData(
            shot_name=shot_name,
            houdini_version=hou.applicationVersionString(),
            generated_at=datetime.now().isoformat(),
            usdz_path=usdz_path,
            wrapper_path=wrapper_path,
            warnings=report.warnings,
            total_usdz_size_mb=usdz_size,
            elapsed_seconds=elapsed,
        )
        write_manifest(manifest_path, manifest_data)
        log.append(f"  [8/8] Writing manifest .... DONE")

        # Warnings
        if report.warnings:
            log.append("")
            log.append("  Warnings:")
            for w in report.warnings:
                log.append(f"    ! {w}")

        # Output summary
        log.append("")
        log.append("  Output:")
        log.append(f"    HIP zip:  {zip_path}")
        log.append(f"    USDZ:     {usdz_path}")
        log.append(f"    Wrapper:  {wrapper_path}")
        log.append(f"    Manifest: {manifest_path}")

        log.append(f"  Elapsed: {elapsed:.1f}s")

        # Disk space check
        total, used, free = shutil.disk_usage(shot_dir)
        free_mb = free / (1024 * 1024)
        pct = (free / total) * 100 if total else 0
        if free < 100 * 1024 * 1024 or pct < 1.0:
            hou.ui.displayMessage(
                f"Low disk space warning: {free_mb:.0f} MB remaining "
                f"({pct:.1f}% free). Packaging has duplicated scene data. "
                "Consider freeing space before rendering.",
                severity=hou.severityType.Warning,
            )

        log.append("")
        log.append(SEP)
        log.append("PACKAGING COMPLETE.")

    except Exception as e:
        log.append("")
        log.append(f"  ERROR: {e}")
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
            except Exception as e:
                hou.ui.displayMessage(
                    f"Found ROP at {output.path()} but couldn't read "
                    f"frame range: {e}",
                    severity=hou.severityType.Warning,
                )
                return

    hou.ui.displayMessage(
        "No Karma ROP found downstream. Connect this node before a Karma ROP.",
        severity=hou.severityType.Warning,
    )
