"""HDA-embedded Python entry points for karma_usd_packager.

All paths are relative to $HIP (the directory containing the .hip file).
"""

import os
import re
import shutil
import sys
import time
import zipfile
from datetime import datetime


# Default filenames — change here to override globally
DEFAULT_USDZ_FILENAME = "{shot_name}.usdz"
DEFAULT_WRAPPER_FILENAME = "{shot_name}.usda"


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


def _bake_opdef(opdef_path, bake_dir):
    """Extract opdef: HDA section content to a file on disk.

    Format: opdef:/Category/type_name?SectionName
    Handles Houdini's VexCode→VflCode section name mapping.
    """
    import hou
    try:
        path = opdef_path[len("opdef:"):]
        if "?" not in path:
            return None
        type_path, section_name = path.rsplit("?", 1)
        parts = type_path.strip("/").split("/", 1)
        if len(parts) != 2:
            return None
        cat_name, type_name = parts

        cat_map = {
            "Vop": hou.vopNodeTypeCategory,
            "Sop": hou.sopNodeTypeCategory,
            "Lop": hou.lopNodeTypeCategory,
            "Dop": hou.dopNodeTypeCategory,
            "Object": hou.objNodeTypeCategory,
            "Cop2": hou.cop2NodeTypeCategory,
        }
        cat_fn = cat_map.get(cat_name)
        if not cat_fn:
            return None

        node_type = hou.nodeType(cat_fn(), type_name)
        if not node_type or not node_type.definition():
            return None

        sections = node_type.definition().sections()

        # Try exact name first, then Houdini's VexCode→VflCode mapping
        actual_name = section_name
        if section_name not in sections:
            alt_name = section_name.replace("VexCode", "VflCode")
            if alt_name in sections:
                actual_name = alt_name
            else:
                return None

        content = sections[actual_name].contents()
        safe_name = f"{type_name.replace('::', '_').replace('.', '_')}_{actual_name}"
        output_path = os.path.join(bake_dir, safe_name)
        if isinstance(content, bytes):
            with open(output_path, "wb") as f:
                f.write(content)
        else:
            with open(output_path, "w") as f:
                f.write(content)
        return output_path
    except Exception:
        return None


def _bake_op(op_path, bake_dir, frame_range=None):
    """Bake op: COP/SOP node data to a file on disk.

    COP nodes: renders via a temp rop_image COP → .png (with alpha).
      Always renders the full frame range (isTimeDependent is unreliable
      on null/pass-through COPs). Returns a dict with frame info.
    SOP nodes: exports geometry via temp SOP Import LOP → .usdc.
    Handles UDIM [NNNN] suffixes and SDF_FORMAT_ARGS time values.
    """
    import hou
    try:
        raw = op_path[len("op:"):]

        # Parse UDIM [NNNN] suffix (COP textures)
        udim_match = re.search(r'\[(\d+)\]$', raw)
        udim = udim_match.group(1) if udim_match else None
        if udim:
            raw = raw[:udim_match.start()]

        # Parse SDF_FORMAT_ARGS
        args_str = ""
        if ":SDF_FORMAT_ARGS:" in raw:
            raw, args_str = raw.split(":SDF_FORMAT_ARGS:", 1)

        # Strip .sop.volumes, .sop.geo, .cop2.* suffixes to get node path
        clean_path = re.sub(r'\.(sop|cop2)\.\w+$', '', raw)

        node = hou.node(clean_path)
        if node is None:
            return None

        safe_name = clean_path.strip("/").replace("/", "__")
        cat = node.type().category()

        # --- COP: render to .png via temp rop_image ---
        # copNodeTypeCategory = new COPs (H21+ Solaris), cop2 = legacy COP2
        if cat in (hou.copNodeTypeCategory(), hou.cop2NodeTypeCategory()):
            copnet = node.parent()
            rop = copnet.createNode("rop_image", "tmp_bake_rop")
            try:
                rop.parm("coppath").set(f"../{node.name()}")

                if frame_range is not None:
                    frame_start, frame_end = frame_range
                    if udim:
                        filename_pat = f"{safe_name}.{udim}.$F4.png"
                    else:
                        filename_pat = f"{safe_name}.$F4.png"
                    output_pattern = os.path.join(bake_dir, filename_pat)
                    rop.parm("copoutput").set(output_pattern)
                    rop.parm("trange").set(1)  # Frame range
                    # Clear default $FSTART/$FEND expressions
                    rop.parm("f1").deleteAllKeyframes()
                    rop.parm("f2").deleteAllKeyframes()
                    rop.parm("f1").set(frame_start)
                    rop.parm("f2").set(frame_end)
                    rop.parm("f3").set(1)
                    rop.render()

                    first = output_pattern.replace("$F4", f"{int(frame_start):04d}")
                    if os.path.exists(first) and os.path.getsize(first) > 0:
                        files = [
                            output_pattern.replace("$F4", f"{f:04d}")
                            for f in range(int(frame_start), int(frame_end) + 1)
                            if os.path.exists(
                                output_pattern.replace("$F4", f"{f:04d}")
                            )
                        ]
                        return {
                            "animated": True,
                            "pattern": output_pattern,
                            "frame_start": int(frame_start),
                            "frame_end": int(frame_end),
                            "files": files,
                        }
                else:
                    if udim:
                        filename = f"{safe_name}.{udim}.png"
                    else:
                        filename = f"{safe_name}.png"
                    output_path = os.path.join(bake_dir, filename)
                    rop.parm("copoutput").set(output_path)
                    rop.parm("trange").set(0)  # Current frame
                    rop.render()
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                        return output_path
            finally:
                rop.destroy()
            return None

        # --- SOP: export as .usdc via temp SOP Import LOP ---
        if cat == hou.sopNodeTypeCategory():
            # Parse time from SDF_FORMAT_ARGS (t= is in seconds)
            frame = None
            if args_str:
                params = dict(
                    p.split("=", 1) for p in args_str.split("&") if "=" in p
                )
                if "t" in params:
                    frame = float(params["t"]) * hou.fps()

            output_path = os.path.join(bake_dir, f"{safe_name}.usdc")
            from pxr import Sdf, UsdUtils as _UsdUtils

            stage_net = hou.node("/stage")
            sop_import = stage_net.createNode("sopimport", "tmp_bake_sop")
            try:
                sop_import.parm("soppath").set(clean_path)
                if frame is not None:
                    old_frame = hou.frame()
                    hou.setFrame(frame)
                sop_import.cook(force=True)
                baked_stage = sop_import.stage()
                if baked_stage:
                    flat_layer = baked_stage.Flatten()
                    flat_layer.Export(output_path)
                if frame is not None:
                    hou.setFrame(old_frame)
            finally:
                sop_import.destroy()

            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                # Clean nested op:/opdef: paths from the exported .usdc
                # (SOP Import LOP embeds its own Houdini-internal refs in metadata)
                nested = Sdf.Layer.FindOrOpen(output_path)
                if nested:
                    def _clean(p):
                        return "" if p.startswith(("op:", "opdef:")) else p
                    _UsdUtils.ModifyAssetPaths(nested, _clean)
                    nested.Save()
                return output_path
            return None

        return None
    except Exception:
        return None


def _bake_houdini_paths(flat_usda_path, bake_dir, frame_range=None):
    """Resolve all op: and opdef: paths in a flattened .usda to real files.

    Bakes referenced data to disk and rewrites asset paths in-place.
    Animated COP textures are rendered as per-frame PNGs with time-sampled
    asset paths in the USD.
    Unbakeable paths are left unchanged (not stripped).

    Returns (baked, failed, shader_opdef_map):
        baked/failed -- lists of (original_path, baked_path|reason, size_mb).
        shader_opdef_map -- {prim_path: original_opdef_uri} for VOP shader
            sourceAsset refs.  The caller should override these back to opdef:
            URIs in the wrapper so husk resolves them through the OTL system.
    """
    from pxr import Sdf, Usd, UsdUtils

    os.makedirs(bake_dir, exist_ok=True)

    # Pre-scan: record shader opdef: URIs before baking rewrites them.
    shader_opdef_map = {}
    pre_stage = Usd.Stage.Open(flat_usda_path)
    for prim in pre_stage.Traverse():
        if prim.GetTypeName() != "Shader":
            continue
        impl = prim.GetAttribute("info:implementationSource")
        if not impl or impl.Get() != "sourceAsset":
            continue
        sa = prim.GetAttribute("info:sourceAsset")
        if not sa:
            continue
        val = sa.Get()
        path_str = val.path if hasattr(val, "path") else str(val)
        if path_str.startswith("opdef:") and "/Vop/" in path_str:
            shader_opdef_map[str(prim.GetPath())] = path_str
    del pre_stage

    layer = Sdf.Layer.FindOrOpen(flat_usda_path)

    # Collect unique Houdini paths
    houdini_paths = set()
    def _collect(path):
        if path.startswith(("op:", "opdef:")):
            houdini_paths.add(path)
        return path
    UsdUtils.ModifyAssetPaths(layer, _collect)

    if not houdini_paths:
        return [], [], shader_opdef_map

    import hou

    # Estimate whether heavy work is expected (for progress dialog)
    has_slow_work = len(houdini_paths) > 3

    # Bake each path — show progress if heavy work expected
    path_map = {}        # static: orig_path -> baked_path
    animated_map = {}    # animated: orig_path -> dict with frame info
    baked = []
    failed = []
    sorted_paths = sorted(houdini_paths)
    total = len(sorted_paths)

    with hou.InterruptableOperation(
        "Baking Houdini paths",
        long_operation_name="Baking op:/opdef: references to disk",
        open_interrupt_dialog=has_slow_work,
    ) as op:
        for i, orig in enumerate(sorted_paths):
            op.updateLongProgress(
                i / total if total else 1.0,
                f"Baking {i+1}/{total}: {orig[:60]}..."
            )

            if orig.startswith("opdef:"):
                result = _bake_opdef(orig, bake_dir)
            else:
                result = _bake_op(orig, bake_dir, frame_range=frame_range)

            if result is None:
                failed.append((orig, "could not resolve"))
            elif isinstance(result, dict) and result.get("animated"):
                animated_map[orig] = result
                total_sz = sum(
                    os.path.getsize(f) for f in result["files"]
                ) / (1024 * 1024)
                baked.append((orig, f"{len(result['files'])} frames", total_sz))
            else:
                path_map[orig] = result
                sz = os.path.getsize(result) / (1024 * 1024)
                baked.append((orig, result, sz))

    # Rewrite static paths (leave animated ones unchanged for now)
    def _rewrite(path):
        return path_map.get(path, path)
    UsdUtils.ModifyAssetPaths(layer, _rewrite)
    layer.Save()

    # Handle animated paths — set time-sampled asset values
    if animated_map:
        from pxr import Usd
        stage = Usd.Stage.Open(flat_usda_path)
        for prim in stage.Traverse():
            for attr in prim.GetAttributes():
                if attr.GetTypeName() != Sdf.ValueTypeNames.Asset:
                    continue
                val = attr.Get()
                if val is None:
                    continue
                val_str = val.path if hasattr(val, "path") else str(val)
                if val_str not in animated_map:
                    continue
                info = animated_map[val_str]
                attr.Clear()
                for frame in range(info["frame_start"], info["frame_end"] + 1):
                    frame_path = info["pattern"].replace(
                        "$F4", f"{frame:04d}"
                    )
                    attr.Set(Sdf.AssetPath(frame_path), Usd.TimeCode(frame))
        stage.GetRootLayer().Save()

    return baked, failed, shader_opdef_map


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
            validate_shot_structure, validate_rop_connection,
        )
        from src.auditor import audit_stage

        shot_name = node.parm("shot_name").eval()
        folder_name = _build_folder_name(node)
        SEP = "=" * 48

        log.append(f"Verify — {folder_name}")
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
        shot_dir = os.path.join(hip_dir, folder_name)
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
            if report.products_missing_vars:
                audit_issues.append(
                    "NO AOVs configured -- husk will render BLACK. "
                    "Enable Beauty in Karma RenderSettings."
                )

            if audit_issues:
                log.append(f"  [5/5] Stage audit ......... WARN")
            else:
                log.append(f"  [5/5] Stage audit ......... PASS")

            log.append(f"        Render settings       {'found' if report.has_render_settings else 'MISSING (will create)'}")
            log.append(f"        Camera                {'found' if report.has_camera else 'MISSING'}")
            log.append(f"        Render products       {'found' if report.has_render_products else 'MISSING'}")
            log.append(f"        AOVs (RenderVars)     {'found' if report.has_render_vars else 'MISSING'}")
            if report.vex_shaders:
                log.append(f"        VEX shaders           {', '.join(report.vex_shaders)}")
            if report.resolution_mismatches:
                log.append(f"        Resolution            MISMATCH")
            log.append(f"        Instances             {report.instance_count:,}")

            warnings.extend(report.warnings)
            warnings.extend(audit_issues)

            # Auto-switch to EXR if extra AOVs are present (PNG can't store them)
            render_vars = [p for p in stage.Traverse() if p.GetTypeName() == "RenderVar"]
            if len(render_vars) > 1 and node.parm("output_format").evalAsString() == "png":
                node.parm("output_format").set("exr")
                aov_names = []
                for rv in render_vars:
                    a = rv.GetAttribute("driver:parameters:aov:husk:name")
                    aov_names.append(a.Get() if a else rv.GetName())
                log.append(f"        AOVs                  {', '.join(aov_names)}")
                log.append(f"        *** Switched to EXR (multiple AOVs detected)")
            else:
                aov_count = len(render_vars)
                log.append(f"        AOVs                  {aov_count}")
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

        if not has_failure:
            node.parm("verified").set(1)

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
        folder_name = _build_folder_name(node)
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

        log.append(f"Package — {folder_name}")
        log.append(SEP)
        log.append("")
        log.append(f"  [1/8] Validating .......... PASS")

        # 2. Create shot directories at $HIP/folder_name/
        hip_dir = _get_hip_dir()
        shot_dir = os.path.join(hip_dir, folder_name)
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

        # 5. Audit (read-only — live LOP stage layer is not editable)
        report = audit_stage(stage)
        log.append(f"  [4/8] Auditing stage ...... PASS")

        # Warn (and optionally block) if no AOVs are configured
        if report.products_missing_vars:
            msg = (
                "No AOVs (RenderVars) found on RenderProducts.\n\n"
                "Standalone husk will render a BLACK image without them.\n"
                "Enable the Beauty AOV in your Karma RenderSettings LOP,\n"
                "then re-run packaging.\n\n"
                "Continue anyway?"
            )
            if not hou.ui.displayConfirmation(msg):
                return

        # 6. Flatten first, then modify the editable flattened stage
        output_format = node.parm("output_format").evalAsString()
        frame_start = int(node.parm("frame_start").eval())
        frame_end = int(node.parm("frame_end").eval())

        staging_dir = tempfile.mkdtemp(prefix="usd_packager_")
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
        log.append(f"  [5/8] Injecting paths ..... DONE")
        bake_dir = os.path.join(staging_dir, "baked")
        baked, failed, shader_opdef_map = _bake_houdini_paths(
            flat_path, bake_dir, frame_range=(frame_start, frame_end)
        )
        if baked:
            total_mb = sum(sz for _, _, sz in baked)
            log.append(f"        Baked {len(baked)} Houdini paths ({total_mb:.1f} MB)")
            for orig, dest, sz in baked:
                log.append(f"          {sz:6.1f} MB  {os.path.basename(dest)}")
        if failed:
            log.append(f"        WARNING: {len(failed)} paths could not be resolved")
            for orig, reason in failed:
                log.append(f"          {orig[:80]}")

        scenes_dir = os.path.join(shot_dir, "Scenes")
        usdz_filename = DEFAULT_USDZ_FILENAME.format(shot_name=shot_name)
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
        wrapper_filename = DEFAULT_WRAPPER_FILENAME.format(shot_name=shot_name)
        wrapper_path = os.path.join(scenes_dir, wrapper_filename)

        write_wrapper(usdz_filename, {}, wrapper_path,
                      shader_opdef_map=shader_opdef_map)
        if shader_opdef_map:
            log.append(f"        Restored {len(shader_opdef_map)} shader opdef: URI(s)")
        log.append(f"  [7/8] Writing wrapper ..... DONE")

        # 8b. Write render_info.txt for farm scripts
        render_info_path = os.path.join(shot_dir, "render_info.txt")
        frame_count = frame_end - frame_start + 1
        with open(render_info_path, "w") as f:
            f.write(f"startframe={frame_start}\n")
            f.write(f"endframe={frame_end}\n")
            f.write(f"framecount={frame_count}\n")
            f.write(f"usdfile=Scenes/{wrapper_filename}\n")

        # 9. Write manifest
        manifest_path = os.path.join(shot_dir, f"{shot_name}_manifest.txt")

        elapsed = time.time() - t0
        manifest_data = ManifestData(
            shot_name=shot_name,
            houdini_version=hou.applicationVersionString(),
            generated_at=datetime.now().isoformat(),
            frame_start=frame_start,
            frame_end=frame_end,
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
        log.append(f"    Info:     {render_info_path}")
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
