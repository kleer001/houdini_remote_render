"""HDA-embedded Python entry points for redshift_usd_packager.

LOP HDA that packages a Solaris USD stage for remote rendering via
redshiftUsdCmdLine. Follows the same pipeline as the Karma packager
but generates a Redshift-specific render script.
"""

import os
import sys
import time
import zipfile
from datetime import datetime


# Default filenames
DEFAULT_USDZ_FILENAME = "{shot_name}.usdz"
DEFAULT_WRAPPER_FILENAME = "{shot_name}.usda"


def _ensure_src_path(node):
    """Ensure the src/ directory is on sys.path for imports.

    Derives the repo root from the HDA's library file path:
    src/hda/redshift_usd_packager.hdalc -> repo root is two levels up.
    """
    hda_def = node.type().definition()
    if hda_def is None:
        return
    hda_dir = os.path.dirname(hda_def.libraryFilePath())
    repo_root = os.path.dirname(os.path.dirname(hda_dir))  # up from src/hda/ to repo root

    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


def _get_hip_dir():
    """Return the directory containing the current .hip file."""
    import hou
    return os.path.dirname(hou.hipFile.path())


def _format_version(raw):
    """Normalize version string: lowercase 'v' prefix, 3-digit zero-padded."""
    raw = raw.strip().lower()
    if raw.startswith("v"):
        raw = raw[1:]
    digits = raw.lstrip("0") or "0"
    return f"v{int(digits):03d}"


def _build_folder_name(node):
    """Build the output folder name: SHOT_P<pod>T<team>_v<NNN>."""
    shot = node.parm("shot_name").eval()
    pod = node.parm("pod_number").eval()
    team = node.parm("team_number").eval()
    ver = _format_version(node.parm("version").eval())
    return f"{shot}_P{pod}T{team}_{ver}"


def _has_ui():
    """Return True if hou.ui is available (False in headless/hython)."""
    import hou
    return hasattr(hou, "ui") and hou.ui is not None


def on_shot_name_changed(kwargs):
    """Parameter callback — flag red background if invalid."""
    import hou
    node = kwargs["node"]
    _ensure_src_path(node)
    node.parm("verified").set(0)
    node.parm("log_output").set("")

    from src.validator import validate_shot_name
    name = node.parm("shot_name").eval()
    ok, msg = validate_shot_name(name)
    if not ok:
        node.parm("shot_name").set(name)  # trigger UI refresh


def on_field_changed(kwargs):
    """Reset verified state and clear log when shot info fields change."""
    node = kwargs["node"]
    node.parm("verified").set(0)
    node.parm("log_output").set("")


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
            validate_shot_structure,
        )
        from src.auditor import audit_stage
        from src.redshift_validator import (
            validate_redshift_stage, validate_redshift_materials,
        )

        shot_name = node.parm("shot_name").eval()
        folder_name = _build_folder_name(node)
        SEP = "=" * 48

        log.append(f"Verify — {folder_name}")
        log.append(SEP)
        log.append("")

        # [1/5] Shot name
        ok, msg = validate_shot_name(shot_name)
        if not ok:
            log.append(f"  [1/5] Shot name ........... FAIL: {msg}")
            node.parm("log_output").set("\n".join(log))
            if _has_ui():
                hou.ui.displayMessage(msg, severity=hou.severityType.Error)
            return
        log.append(f"  [1/5] Shot name ........... PASS")

        # [2/5] HIP file
        ok, msg = validate_hip_saved()
        if not ok:
            log.append(f"  [2/5] HIP file ............ FAIL: {msg}")
            node.parm("log_output").set("\n".join(log))
            if _has_ui():
                hou.ui.displayMessage(msg, severity=hou.severityType.Error)
            return
        log.append(f"  [2/5] HIP file ............ PASS")
        if msg:
            warnings.append(msg)

        # [3/5] Shot directory
        hip_dir = _get_hip_dir()
        shot_dir = os.path.join(hip_dir, folder_name)
        ok, msg = validate_shot_structure(shot_dir)
        if not ok:
            log.append(f"  [3/5] Shot directory ...... WILL CREATE")
        else:
            log.append(f"  [3/5] Shot directory ...... PASS")

        # [4/5] Stage input
        input_node = node.inputs()[0] if node.inputs() else None
        if not input_node:
            log.append(f"  [4/5] Stage input ......... FAIL (no input)")
            has_failure = True
        else:
            stage = input_node.stage()
            if stage is None:
                log.append(f"  [4/5] Stage input ......... FAIL (empty stage)")
                has_failure = True
            else:
                log.append(f"  [4/5] Stage input ......... PASS")

        # [5/5] Stage audit + Redshift validation
        if input_node and input_node.stage():
            stage = input_node.stage()
            report = audit_stage(stage)

            # Redshift-specific validation
            rs_ok, rs_msg = validate_redshift_stage(stage)
            rs_mat_warnings = validate_redshift_materials(stage)

            # --- Blocking checks (FAIL) ---
            # These are things the artist must fix before packaging.
            # Each message tells them exactly what LOP to add.
            audit_failures = []

            if not report.has_render_settings:
                audit_failures.append(
                    "No RenderSettings prim found. Add a Render Settings "
                    "LOP (or Redshift RenderSettings LOP) to your network."
                )

            if not report.has_render_products:
                audit_failures.append(
                    "No RenderProduct prim found. Add a Render Product "
                    "LOP to define where rendered images are written. "
                    "Without this, the renderer produces no output files."
                )

            if not report.has_camera:
                audit_failures.append(
                    "No Camera prim found. Add a Camera LOP or ensure "
                    "your sublayered USD file contains a camera."
                )

            if not rs_ok:
                audit_failures.append(rs_msg)

            # Check products relationship wiring
            if report.has_render_settings and report.has_render_products:
                if report.products_missing_vars is not None:
                    # Reuse the existing check — but also verify
                    # the products rel itself is wired
                    from pxr import UsdRender as _UsdRender
                    for _p in stage.Traverse():
                        if _p.GetTypeName() == "RenderSettings":
                            _rs = _UsdRender.Settings(_p)
                            if not _rs.GetProductsRel().GetTargets():
                                audit_failures.append(
                                    "RenderSettings has no 'products' relationship. "
                                    "Wire your RenderProduct to the RenderSettings — "
                                    "in Solaris, connect the Render Product LOP's output "
                                    "to the Render Settings LOP's input."
                                )
                            break

            # --- Non-blocking checks (WARN) ---
            audit_warnings = []
            if not report.has_lights:
                audit_warnings.append(
                    "No lights found — Redshift has no default headlight, "
                    "the render will be black"
                )
            if report.camera_mismatch:
                audit_warnings.append(report.camera_mismatch)
            audit_warnings.extend(rs_mat_warnings)

            if audit_failures:
                log.append(f"  [5/5] Stage audit ......... FAIL")
                has_failure = True
            elif audit_warnings:
                log.append(f"  [5/5] Stage audit ......... WARN")
            else:
                log.append(f"  [5/5] Stage audit ......... PASS")

            log.append(f"        Render settings       {'found' if report.has_render_settings else 'MISSING'}")
            log.append(f"        Redshift settings      {'found' if rs_ok else 'MISSING'}")
            log.append(f"        Render products        {'found' if report.has_render_products else 'MISSING'}")
            log.append(f"        Camera                 {'found' if report.has_camera else 'MISSING'}")
            log.append(f"        AOVs (RenderVars)      {'found' if report.has_render_vars else 'none'}")
            log.append(f"        Lights                 {report.light_count}")
            log.append(f"        Instances              {report.instance_count:,}")

            if report.vex_shaders:
                log.append(f"        VEX shaders            {', '.join(report.vex_shaders)}")
            if report.resolution_mismatches:
                log.append(f"        Resolution             MISMATCH")

            # GPU device
            gpu_device = node.parm("gpu_device").evalAsString()
            log.append(f"        GPU device             {gpu_device}")

            # Show failures first, then warnings
            if audit_failures:
                log.append("")
                log.append("  Errors (must fix before packaging):")
                for f in audit_failures:
                    log.append(f"    [FAIL] {f}")

            warnings.extend(report.warnings)
            warnings.extend(audit_warnings)
        else:
            log.append(f"  [5/5] Stage audit ......... FAIL (no input)")
            has_failure = True

        # Check downstream render ROP for "Current Frame" pitfall
        for output in node.outputs():
            rop_type = output.type().name()
            if rop_type in ("usdrender_rop", "Redshift_IPR", "karma"):
                trange_parm = output.parm("trange")
                if trange_parm and trange_parm.eval() == 0:
                    warnings.append(
                        f"Downstream ROP '{output.name()}' is set to "
                        f"'Render Current Frame'. It will only render "
                        f"whichever frame is active — not a sequence. "
                        f"Set it to 'Render Frame Range' if you want "
                        f"an animation."
                    )
                break

        # Check if packager's own frame range is a single frame
        frame_start_val = node.parm("frame_start").eval()
        frame_end_val = node.parm("frame_end").eval()
        if frame_start_val == frame_end_val:
            warnings.append(
                f"Frame range is a single frame ({int(frame_start_val)}). "
                f"If you intended to render a sequence, update Frame "
                f"Start/End in the Packaging tab."
            )

        # [DEPS] Upstream dependency scan
        try:
            from src.dependency_resolver import (
                resolve_dependencies, format_dag_summary, CyclicDependencyError,
            )
            dag = resolve_dependencies(node)
            log.append("")
            log.append("[DEPS] Upstream dependency scan:")
            log.append(format_dag_summary(dag))
            if dag.execution_order:
                log.append("")
                log.append("[OK] Dependency chain verified — no cycles.")
        except Exception as e:
            log.append("")
            log.append(f"[DEPS] Scan skipped: {e}")

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

        if not has_failure:
            node.parm("verified").set(1)

    except Exception as e:
        log.append(f"ERROR: {e}")
        import traceback
        log.append(traceback.format_exc())
        if _has_ui():
            hou.ui.displayMessage(str(e), severity=hou.severityType.Error)

    node.parm("log_output").set("\n".join(log))


def on_package_clicked(kwargs):
    """Full pipeline run — package and stage."""
    import hou
    import shutil
    import tempfile
    node = kwargs["node"]
    _ensure_src_path(node)
    log = []

    try:
        from src.validator import validate_shot_name, validate_hip_saved
        from src.auditor import audit_stage, ensure_render_settings
        from src.redshift_validator import (
            validate_redshift_stage, validate_redshift_materials,
        )
        from src.output_injector import inject_output_paths
        from src.packager import flatten_stage, create_usdz
        from src.wrapper_writer import write_wrapper
        from src.redshift_script_writer import write_redshift_script
        from src.redshift_info_writer import write_redshift_info
        from src.redshift_manifest import RedshiftManifestData, write_redshift_manifest
        from src.platform_utils import ensure_dir

        shot_name = node.parm("shot_name").eval()
        folder_name = _build_folder_name(node)
        SEP = "=" * 48

        # 1. Validate
        ok, msg = validate_shot_name(shot_name)
        if not ok:
            if _has_ui():
                hou.ui.displayMessage(msg, severity=hou.severityType.Error)
            return

        ok, msg = validate_hip_saved()
        if not ok:
            if _has_ui():
                hou.ui.displayMessage(msg, severity=hou.severityType.Error)
            return
        hip_warning = msg

        t0 = time.time()

        log.append(f"Package — {folder_name}")
        log.append(SEP)
        log.append("")
        log.append(f"  [1/9] Validating .......... PASS")

        # 2. Create shot directories
        hip_dir = _get_hip_dir()
        shot_dir = os.path.join(hip_dir, folder_name)
        for d in ("Output", "Textures", "Cache", "Scenes", "Scripts"):
            ensure_dir(os.path.join(shot_dir, d))
        log.append(f"  [2/9] Creating dirs ....... DONE")

        # 3. Backup current .hip file
        hip_path = hou.hipFile.path()
        hip_basename = os.path.basename(hip_path)
        zip_name = hip_basename + ".zip"
        zip_path = os.path.join(shot_dir, zip_name)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(hip_path, hip_basename)
        zip_size = os.path.getsize(zip_path) / (1024 * 1024)
        log.append(f"  [3/9] Backing up HIP ..... {zip_size:.2f} MB")

        # 3b. Resolve cache dependencies
        from src.dependency_resolver import resolve_dependencies, CyclicDependencyError
        cache_scripts_list = []

        try:
            dag = resolve_dependencies(node)
        except CyclicDependencyError as e:
            if _has_ui():
                hou.ui.displayMessage(
                    f"Cyclic cache dependency:\n{e}",
                    severity=hou.severityType.Error,
                )
            return
        except Exception as e:
            log.append(f"  [DEPS] Scan skipped: {e}")
            dag = None

        if dag and dag.execution_order:
            n_caches = len(dag.execution_order)
            labels = [dag.cache_units[p].label for p in dag.execution_order]

            if _has_ui():
                result = hou.ui.displayMessage(
                    f"Found {n_caches} upstream cache job(s):\n"
                    + "\n".join(f"  {i+1}. {l}" for i, l in enumerate(labels))
                    + "\n\nPackage these with the render?",
                    buttons=("Package All", "Render Only", "Cancel"),
                    title="Cache Dependencies Found",
                )
                if result == 2:
                    return
                include_caches = (result == 0)
            else:
                include_caches = True

            if include_caches:
                from src.cache_scene_writer import save_portable_hip_multi
                from src.cache_script_writer import write_cache_script

                fc_nodes = []
                for path in dag.execution_order:
                    unit = dag.cache_units[path]
                    fc = hou.node(unit.filecache_path)
                    if fc:
                        fc_nodes.append(fc)

                cache_hip_filename = f"{shot_name}_cache.hip"
                cache_hip_path = os.path.join(shot_dir, "Scenes", cache_hip_filename)
                save_portable_hip_multi(fc_nodes, cache_hip_path)

                actual_hip = cache_hip_path
                if not os.path.exists(actual_hip):
                    for ext in (".hiplc", ".hipnc"):
                        alt = cache_hip_path.rsplit(".hip", 1)[0] + ext
                        if os.path.exists(alt):
                            actual_hip = alt
                            break
                actual_hip_filename = os.path.basename(actual_hip)

                for i, path in enumerate(dag.execution_order, 1):
                    unit = dag.cache_units[path]
                    script_filename = f"run_cache_{i:03d}_{unit.label}.sh"
                    script_path = os.path.join(shot_dir, "Scripts", script_filename)
                    write_cache_script(
                        output_path=script_path,
                        shot_name=shot_name,
                        hip_filename=actual_hip_filename,
                        cache_node_path=unit.filecache_path,
                        frame_start=unit.frame_start,
                        frame_end=unit.frame_end,
                    )
                    cache_scripts_list.append((unit.label, script_filename))

                hip_mb = os.path.getsize(actual_hip) / (1024 * 1024)
                log.append(
                    f"  [CACHE] Packaged {n_caches} cache job(s) "
                    f"({hip_mb:.1f} MB .hip)"
                )

        # 4. Get stage from input
        input_node = node.inputs()[0] if node.inputs() else None
        if not input_node:
            if _has_ui():
                hou.ui.displayMessage(
                    "No input connected. Connect a LOP node to input 0.",
                    severity=hou.severityType.Error,
                )
            return

        stage = input_node.stage()
        if stage is None:
            if _has_ui():
                hou.ui.displayMessage(
                    "Input node returned an empty stage. Check the LOP network.",
                    severity=hou.severityType.Error,
                )
            return

        # 5. Audit — block on missing critical prims
        report = audit_stage(stage)
        rs_ok, rs_msg = validate_redshift_stage(stage)
        rs_mat_warnings = validate_redshift_materials(stage)
        all_warnings = list(report.warnings) + rs_mat_warnings
        if hip_warning:
            all_warnings.insert(0, hip_warning)

        # Blocking checks — refuse to package without these
        blocking = []
        if not report.has_render_settings:
            blocking.append(
                "No RenderSettings prim. Add a Render Settings LOP."
            )
        if not report.has_render_products:
            blocking.append(
                "No RenderProduct prim. Add a Render Product LOP."
            )
        if not report.has_camera:
            blocking.append(
                "No Camera prim. Add a Camera LOP."
            )

        if blocking:
            msg = "Cannot package — your scene is missing required prims:\n\n"
            msg += "\n".join(f"  - {b}" for b in blocking)
            msg += "\n\nAdd these LOPs upstream of the packager and try again."
            log.append(f"  [4/9] Auditing stage ...... FAIL")
            for b in blocking:
                log.append(f"    [FAIL] {b}")
            node.parm("log_output").set("\n".join(log))
            if _has_ui():
                hou.ui.displayMessage(msg, severity=hou.severityType.Error)
            return

        if not rs_ok and _has_ui():
            if not hou.ui.displayConfirmation(
                f"{rs_msg}\n\nContinue anyway?"
            ):
                return

        log.append(f"  [4/9] Auditing stage ...... PASS")

        # 6. Flatten and inject output paths
        output_format = node.parm("output_format").evalAsString()
        frame_start = int(node.parm("frame_start").eval())
        frame_end = int(node.parm("frame_end").eval())

        staging_dir = tempfile.mkdtemp(prefix="rs_packager_")
        flat_path = flatten_stage(stage, staging_dir)

        from pxr import Usd
        edit_stage = Usd.Stage.Open(flat_path)
        ensure_render_settings(edit_stage)
        inject_output_paths(
            edit_stage, shot_name,
            output_format=output_format,
            frame_start=frame_start,
            frame_end=frame_end,
        )
        edit_stage.GetRootLayer().Save()
        log.append(f"  [5/9] Injecting paths ..... DONE")

        # Bake Houdini-specific paths (op:, opdef:)
        bake_dir = os.path.join(staging_dir, "baked")
        baked, failed, shader_opdef_map = _bake_houdini_paths(
            flat_path, bake_dir, frame_range=(frame_start, frame_end)
        )
        if baked:
            total_mb = sum(sz for _, _, sz in baked)
            log.append(f"        Baked {len(baked)} Houdini paths ({total_mb:.1f} MB)")
        if failed:
            log.append(f"        WARNING: {len(failed)} paths could not be resolved")

        # Convert .rat textures for USDZ compatibility
        from src.converter import convert_rat_for_usdz, extract_udim_for_usdz
        rat_converted = convert_rat_for_usdz(flat_path, staging_dir)
        if rat_converted:
            log.append(f"        Converted {len(rat_converted)} .rat textures to .exr")

        textures_dir = os.path.join(shot_dir, "Textures")
        udim_overrides = extract_udim_for_usdz(flat_path, textures_dir)

        scenes_dir = os.path.join(shot_dir, "Scenes")
        usdz_filename = DEFAULT_USDZ_FILENAME.format(shot_name=shot_name)
        usdz_path = os.path.join(scenes_dir, usdz_filename)

        create_usdz(flat_path, usdz_path)
        shutil.rmtree(staging_dir, ignore_errors=True)
        usdz_size = os.path.getsize(usdz_path) / (1024 * 1024)
        log.append(f"  [6/9] Creating USDZ ....... {usdz_size:.2f} MB")

        # 7. Write wrapper
        wrapper_filename = DEFAULT_WRAPPER_FILENAME.format(shot_name=shot_name)
        wrapper_path = os.path.join(scenes_dir, wrapper_filename)
        write_wrapper(usdz_filename, {}, wrapper_path,
                      shader_opdef_map=shader_opdef_map,
                      udim_overrides=udim_overrides)
        log.append(f"  [7/9] Writing wrapper ..... DONE")

        # 8. Write render script + render_info.txt
        gpu_device = node.parm("gpu_device").evalAsString()
        texture_cache_gb_raw = node.parm("texture_cache_gb").eval()
        texture_cache_gb = texture_cache_gb_raw if texture_cache_gb_raw > 0 else None
        ocio_config = node.parm("ocio_config").eval() or None
        skip_postfx = node.parm("skip_postfx").eval()
        restart_delegate = node.parm("restart_delegate").eval()

        # Single-pass stage traversal for resolution, camera, AOV count
        width, height = 1920, 1080
        camera = ""
        aov_count = 0
        for _prim in stage.Traverse():
            _type = _prim.GetTypeName()
            if _type == "RenderSettings" and width == 1920:
                _res_attr = _prim.GetAttribute("resolution")
                if _res_attr:
                    _res = _res_attr.Get()
                    width, height = int(_res[0]), int(_res[1])
            elif _type == "Camera" and not camera:
                camera = str(_prim.GetPath())
            elif _type == "RenderVar":
                aov_count += 1

        render_script_path = os.path.join(shot_dir, "Scripts", "run_render.sh")
        write_redshift_script(
            output_path=render_script_path,
            shot_name=shot_name,
            wrapper_filename=wrapper_filename,
            frame_start=frame_start,
            frame_end=frame_end,
            gpu_device=gpu_device,
            texture_cache_gb=texture_cache_gb,
            ocio_config=ocio_config,
            skip_postfx=bool(skip_postfx),
            restart_delegate=bool(restart_delegate),
        )

        render_info_path = os.path.join(shot_dir, "render_info.txt")
        write_redshift_info(
            output_path=render_info_path,
            shot_name=shot_name,
            folder_name=folder_name,
            frame_start=frame_start,
            frame_end=frame_end,
            frame_inc=1,
            resolution=(width, height),
            camera=camera,
            gpu_device=gpu_device,
            texture_cache_gb=texture_cache_gb,
            ocio_config=ocio_config,
            usd_file=wrapper_filename,
            aov_count=aov_count,
            houdini_version=hou.applicationVersionString(),
        )
        log.append(f"  [8/9] Writing render script DONE")

        # 8b. Orchestration script
        if cache_scripts_list:
            from src.orchestration_writer import write_orchestration_script
            orch_path = os.path.join(shot_dir, "Scripts", "run_all.sh")
            write_orchestration_script(
                output_path=orch_path,
                shot_name=shot_name,
                cache_scripts=cache_scripts_list,
                render_script_filename="run_render.sh",
            )
            log.append(f"  [ORCH] Writing run_all.sh .. DONE")

        # 9. Write manifest
        elapsed = time.time() - t0
        manifest_data = RedshiftManifestData(
            shot_name=shot_name,
            folder_name=folder_name,
            houdini_version=hou.applicationVersionString(),
            generated_at=datetime.now().isoformat(),
            elapsed_seconds=elapsed,
            frame_start=frame_start,
            frame_end=frame_end,
            resolution=(width, height),
            camera=camera,
            aov_count=aov_count,
            gpu_device=gpu_device,
            texture_cache_gb=texture_cache_gb,
            ocio_config=ocio_config or "",
            usdz_size_mb=usdz_size,
            wrapper_path=wrapper_filename,
            backup_zip_path=zip_name,
            backup_zip_size_mb=zip_size,
            warnings=all_warnings,
        )

        manifest_path = os.path.join(shot_dir, f"{shot_name}_manifest.txt")
        write_redshift_manifest(manifest_path, manifest_data)
        log.append(f"  [9/9] Writing manifest .... DONE")

        # Warnings
        if all_warnings:
            log.append("")
            log.append("  Warnings:")
            for w in all_warnings:
                log.append(f"    ! {w}")

        # Output summary
        log.append("")
        log.append("  Output:")
        log.append(f"    HIP zip:  {zip_path}")
        log.append(f"    USDZ:     {usdz_path}")
        log.append(f"    Wrapper:  {wrapper_path}")
        log.append(f"    Script:   {render_script_path}")
        log.append(f"    Info:     {render_info_path}")
        log.append(f"    Manifest: {manifest_path}")
        log.append(f"  Elapsed: {elapsed:.1f}s")

        # Disk space check
        total, used, free = shutil.disk_usage(shot_dir)
        free_mb = free / (1024 * 1024)
        pct = (free / total) * 100 if total else 0
        if free < 100 * 1024 * 1024 or pct < 1.0:
            if _has_ui():
                hou.ui.displayMessage(
                    f"Low disk space: {free_mb:.0f} MB remaining ({pct:.1f}% free).",
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
        if _has_ui():
            hou.ui.displayMessage(str(e), severity=hou.severityType.Error)

    node.parm("log_output").set("\n".join(log))


def on_get_from_stage_clicked(kwargs):
    """Read frame range from downstream USD Render ROP."""
    import hou
    node = kwargs["node"]

    for output in node.outputs():
        if output.type().name() in ("usdrender_rop", "Redshift_IPR"):
            try:
                start = output.parm("f1").eval()
                end = output.parm("f2").eval()
                node.parm("frame_start").set(start)
                node.parm("frame_end").set(end)
                return
            except Exception as e:
                if _has_ui():
                    hou.ui.displayMessage(
                        f"Found ROP at {output.path()} but couldn't read "
                        f"frame range: {e}",
                        severity=hou.severityType.Warning,
                    )
                return

    if _has_ui():
        hou.ui.displayMessage(
            "No render ROP found downstream.",
            severity=hou.severityType.Warning,
        )


def _bake_houdini_paths(flat_usda_path, bake_dir, frame_range=None):
    """Delegate to the Karma packager's bake implementation.

    The bake logic is Houdini-generic (resolves op: and opdef: paths)
    and is shared between Karma and Redshift packagers. Loaded from the
    Karma HDA's PythonModule file on disk via importlib.util.
    """
    import importlib.util

    # _ensure_src_path has already added repo_root to sys.path.
    # The Karma PythonModule lives at repo_root/src/hda_scripts/PythonModule.py.
    # __file__ is NOT defined inside HDA-embedded code, so we find the
    # repo root from sys.path (set by _ensure_src_path).
    karma_pm_path = None
    for p in sys.path:
        candidate = os.path.join(p, "src", "hda_scripts", "PythonModule.py")
        if os.path.isfile(candidate):
            karma_pm_path = candidate
            break

    if karma_pm_path is None:
        raise FileNotFoundError(
            "Cannot find src/hda_scripts/PythonModule.py on sys.path. "
            "Is the repo root on sys.path via _ensure_src_path()?"
        )

    spec = importlib.util.spec_from_file_location("karma_pm", karma_pm_path)
    karma_pm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(karma_pm)
    return karma_pm._bake_houdini_paths(flat_usda_path, bake_dir, frame_range)
