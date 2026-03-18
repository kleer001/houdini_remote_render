"""HDA-embedded Python entry points for remote_mantra_render.

Wraps a Mantra ROP with remote packaging capabilities.
Generates IFD files with embedded geometry/shaders for license-free
remote rendering via the mantra standalone renderer.
"""

import os
import sys
import time
from datetime import datetime


def _ensure_src_path(node):
    """Ensure the src/ directory is on sys.path for imports.

    Derives the repo root from the HDA's library file path:
    src/hda/remote_mantra_render.hdalc -> repo root is two levels up.
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
    """Normalize version to 3-digit zero-padded with 'v' prefix."""
    n = int(raw)
    return f"v{n:03d}"


def _build_folder_name(node):
    """Build the output folder name: SHOT_P<pod>T<team>_v<NNN>."""
    shot = node.parm("shot_name").eval()
    pod = node.parm("pod_number").eval()
    team = node.parm("team_number").eval()
    ver = _format_version(str(node.parm("ver").eval()))
    return f"{shot}_P{pod}T{team}_{ver}"


def _log(node, msg):
    """Append a message to the log_output parameter."""
    parm = node.parm("log_output")
    current = parm.eval()
    if current:
        parm.set(current + "\n" + msg)
    else:
        parm.set(msg)


def _get_mantra_node(node):
    """Return the internal Mantra ROP node (mantra1)."""
    return node.node("mantra1")


def _has_ui():
    """Return True if hou.ui is available (False in headless/hython)."""
    import hou
    return hasattr(hou, "ui") and hou.ui is not None


# ---------- Parameter callbacks ----------

def on_shot_name_changed(kwargs):
    """Called when the shot_name parameter changes."""
    node = kwargs["node"]
    node.parm("verified").set(0)

    _ensure_src_path(node)
    from src.validator import validate_shot_name

    name = node.parm("shot_name").eval()
    if name:
        ok, msg = validate_shot_name(name)
        if not ok:
            _log(node, f"[!] {msg}")


def on_field_changed(kwargs):
    """Called when any shot info field changes."""
    node = kwargs["node"]
    node.parm("verified").set(0)


# ---------- Verify ----------

def on_verify_clicked(kwargs):
    """Dry-run validation — checks everything without writing files."""
    import hou

    node = kwargs["node"]
    node.parm("log_output").set("")
    _ensure_src_path(node)

    from src.validator import validate_shot_name, validate_hip_saved
    from src.mantra_validator import validate_mantra_node, validate_output_picture, warn_output_picture
    from src.cache_validator import validate_frame_range

    _log(node, "=" * 50)
    _log(node, "VERIFY — Remote Mantra Render")
    _log(node, "=" * 50)
    _log(node, "")

    failures = 0

    # 1. Shot name
    shot_name = node.parm("shot_name").eval()
    ok, msg = validate_shot_name(shot_name)
    if ok:
        _log(node, f"[OK] Shot name: {shot_name}")
    else:
        _log(node, f"[FAIL] Shot name: {msg}")
        failures += 1

    # 2. HIP saved
    ok, msg = validate_hip_saved()
    if ok and msg:
        _log(node, f"[WARN] {msg}")
    elif ok:
        _log(node, "[OK] HIP file is saved.")
    else:
        _log(node, f"[FAIL] {msg}")
        failures += 1

    # 3. Mantra ROP node
    mantra = _get_mantra_node(node)
    ok, msg = validate_mantra_node(mantra)
    if ok:
        _log(node, f"[OK] Mantra ROP: {mantra.path()}")
    else:
        _log(node, f"[FAIL] {msg}")
        failures += 1
        _log(node, "")
        _log(node, f"Verify complete: {failures} failure(s).")
        return

    # 4. Frame range
    f_start = mantra.parm("f1").eval()
    f_end = mantra.parm("f2").eval()
    f_inc = mantra.parm("f3").eval()
    ok, msg = validate_frame_range(f_start, f_end, f_inc)
    if ok:
        frame_count = int((f_end - f_start) / f_inc) + 1
        _log(node, f"[OK] Frame range: {int(f_start)}-{int(f_end)} ({frame_count} frames)")
    else:
        _log(node, f"[FAIL] Frame range: {msg}")
        failures += 1

    # 5. Output picture
    output_picture = mantra.parm("vm_picture").eval()
    ok, msg = validate_output_picture(output_picture)
    if ok:
        _log(node, f"[OK] Output: {output_picture}")
        # Check for hyphen-before-$F pitfall (uses unexpanded path)
        try:
            raw_pic = mantra.parm("vm_picture").unexpandedString()
        except Exception:
            raw_pic = output_picture
        pic_warn = warn_output_picture(raw_pic)
        if pic_warn:
            _log(node, f"[WARN] {pic_warn}")
    else:
        _log(node, f"[FAIL] Output: {msg}")
        failures += 1

    # 6. Camera check
    camera = mantra.parm("camera").eval()
    if not camera:
        _log(node, "[WARN] No camera assigned — Mantra will use the default camera.")

    # 7. Frame range mode check
    trange = mantra.parm("trange").eval()
    if trange == 0:
        _log(node, "[WARN] Render set to 'Current Frame' — will use frame range from packaging.")

    # 8. Shot directory check
    folder_name = _build_folder_name(node)
    shot_root = os.path.join(_get_hip_dir(), folder_name)
    if os.path.exists(shot_root):
        _log(node, f"[WARN] Output folder already exists: {folder_name}/")

    _log(node, "")
    if failures == 0:
        _log(node, "Verify PASSED — ready to package.")
        node.parm("verified").set(1)
    else:
        _log(node, f"Verify FAILED — {failures} issue(s) to fix.")
        node.parm("verified").set(0)


# ---------- Package ----------

def on_package_clicked(kwargs):
    """Full packaging — generates IFDs, gathers textures, writes scripts."""
    import hou

    node = kwargs["node"]
    node.parm("log_output").set("")
    _ensure_src_path(node)

    from src.validator import validate_shot_name, validate_hip_saved
    from src.mantra_validator import validate_mantra_node, validate_output_picture
    from src.cache_validator import validate_frame_range
    from src.mantra_ifd_writer import generate_ifds
    from src.mantra_texture_gatherer import scan_ifds_for_textures, gather_textures
    from src.cache_scene_writer import backup_hip_as_zip
    from src.mantra_info_writer import write_mantra_info
    from src.mantra_script_writer import write_mantra_script
    from src.mantra_manifest import MantraManifestData, write_mantra_manifest
    from src.mantra_auditor import audit_mantra_rop
    from src.platform_utils import ensure_dir, check_disk_space

    t_start = time.time()
    warnings = []

    _log(node, "=" * 50)
    _log(node, "PACKAGE — Remote Mantra Render (IFD)")
    _log(node, "=" * 50)
    _log(node, "")

    # --- Step 1: Validate ---
    _log(node, "[1/9] Validating...")

    shot_name = node.parm("shot_name").eval()
    ok, msg = validate_shot_name(shot_name)
    if not ok:
        _log(node, f"  [FAIL] {msg}")
        if _has_ui():
            hou.ui.displayMessage(msg, title="Package Failed")
        return

    ok, msg = validate_hip_saved()
    if not ok:
        _log(node, f"  [FAIL] {msg}")
        if _has_ui():
            hou.ui.displayMessage(msg, title="Package Failed")
        return
    if msg:
        warnings.append(msg)
        _log(node, f"  [WARN] {msg}")

    mantra = _get_mantra_node(node)
    ok, msg = validate_mantra_node(mantra)
    if not ok:
        _log(node, f"  [FAIL] {msg}")
        if _has_ui():
            hou.ui.displayMessage(msg, title="Package Failed")
        return

    f_start = mantra.parm("f1").eval()
    f_end = mantra.parm("f2").eval()
    f_inc = mantra.parm("f3").eval()
    ok, msg = validate_frame_range(f_start, f_end, f_inc)
    if not ok:
        _log(node, f"  [FAIL] {msg}")
        if _has_ui():
            hou.ui.displayMessage(msg, title="Package Failed")
        return

    output_picture_eval = mantra.parm("vm_picture").eval()
    ok, msg = validate_output_picture(output_picture_eval)
    if not ok:
        _log(node, f"  [FAIL] {msg}")
        if _has_ui():
            hou.ui.displayMessage(msg, title="Package Failed")
        return

    # Get unexpanded picture path to preserve $F4 in metadata
    try:
        output_picture_raw = mantra.parm("vm_picture").unexpandedString()
    except Exception:
        output_picture_raw = output_picture_eval

    # Audit the Mantra ROP for metadata
    audit = audit_mantra_rop(mantra)
    warnings.extend(audit.warnings)

    _log(node, "  All checks passed.")

    # --- Step 2: Create directories ---
    _log(node, "[2/9] Creating directories...")

    hip_dir = _get_hip_dir()
    folder_name = _build_folder_name(node)
    shot_root = os.path.join(hip_dir, folder_name)

    if os.path.exists(shot_root):
        if _has_ui():
            result = hou.ui.displayMessage(
                f"Folder '{folder_name}' already exists. Overwrite?",
                buttons=("Overwrite", "Cancel"),
                severity=hou.severityType.Warning,
                title="Folder Exists",
            )
            if result == 1:
                _log(node, "  Cancelled by user.")
                return
        else:
            _log(node, "  [WARN] Folder exists — overwriting (headless mode).")

    for subdir in ("Output", "IFDs", "Textures", "Scripts"):
        ensure_dir(os.path.join(shot_root, subdir))

    _log(node, f"  Created: {folder_name}/")

    # Disk space check
    _, _, free = check_disk_space(shot_root)
    free_mb = free / (1024 * 1024)
    if free_mb < 100:
        w = f"Low disk space: {free_mb:.0f} MB free"
        warnings.append(w)
        _log(node, f"  [WARN] {w}")

    # --- Step 3: Backup .hip ---
    _log(node, "[3/9] Backing up .hip file...")

    zip_path = os.path.join(shot_root, f"{shot_name}_original.hip.zip")
    backup_hip_as_zip(zip_path)
    zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    _log(node, f"  Backup: {zip_size_mb:.1f} MB")

    # --- Step 4: Generate IFDs ---
    _log(node, "[4/9] Generating IFDs (this may take a while)...")

    ifd_dir = os.path.join(shot_root, "IFDs")
    output_filename = os.path.basename(output_picture_raw) if output_picture_raw else "render.$F4.exr"
    output_pattern = f"Output/{output_filename}"

    # Output path baked into IFD — relative to CWD (which will be IFDs/)
    ifd_output_picture = f"../Output/{output_filename}"

    ifd_paths = generate_ifds(
        mantra_node=mantra,
        ifd_dir=ifd_dir,
        shot_name=shot_name,
        output_picture=ifd_output_picture,
        frame_start=int(f_start),
        frame_end=int(f_end),
        frame_inc=int(f_inc),
    )

    ifd_total_size = sum(os.path.getsize(p) for p in ifd_paths)
    ifd_total_size_mb = ifd_total_size / (1024 * 1024)
    _log(node, f"  Generated {len(ifd_paths)} IFDs ({ifd_total_size_mb:.1f} MB)")

    expected_count = int((f_end - f_start) / f_inc) + 1
    if len(ifd_paths) < expected_count:
        w = f"Expected {expected_count} IFDs but only {len(ifd_paths)} were generated"
        warnings.append(w)
        _log(node, f"  [WARN] {w}")

    # --- Step 5: Gather textures ---
    _log(node, "[5/9] Scanning IFDs for textures...")

    texture_paths = scan_ifds_for_textures(ifd_paths)
    textures_dir = os.path.join(shot_root, "Textures")

    if texture_paths:
        copied = gather_textures(texture_paths, textures_dir)
        textures_size = sum(os.path.getsize(p) for p in copied.values())
        textures_size_mb = textures_size / (1024 * 1024)
        _log(node, f"  Gathered {len(copied)} textures ({textures_size_mb:.1f} MB)")
    else:
        textures_size_mb = 0.0
        _log(node, "  No textures found.")

    # --- Step 6: Write run_render.sh ---
    _log(node, "[6/9] Writing run_render.sh...")

    ifd_printf_pattern = f"{shot_name}.%04d.ifd"
    script_path = os.path.join(shot_root, "Scripts", "run_render.sh")
    write_mantra_script(
        output_path=script_path,
        shot_name=shot_name,
        ifd_pattern=ifd_printf_pattern,
        frame_start=int(f_start),
        frame_end=int(f_end),
        frame_inc=int(f_inc),
    )
    _log(node, "  Written and made executable.")

    # --- Step 7: Write render_info.txt ---
    _log(node, "[7/9] Writing render_info.txt...")

    rop_node_path = mantra.path()
    houdini_version = hou.applicationVersionString()

    info_path = os.path.join(shot_root, "render_info.txt")
    write_mantra_info(
        output_path=info_path,
        shot_name=shot_name,
        folder_name=folder_name,
        frame_start=f_start,
        frame_end=f_end,
        frame_inc=f_inc,
        resolution=audit.resolution,
        pixel_samples=audit.pixel_samples,
        render_engine=audit.render_engine,
        camera=audit.camera,
        rop_node_path=rop_node_path,
        output_picture=output_pattern,
        ifd_count=len(ifd_paths),
        ifd_pattern=ifd_printf_pattern,
        texture_count=len(texture_paths),
        textures_size_mb=textures_size_mb,
        houdini_version=houdini_version,
    )
    _log(node, "  Written.")

    # --- Step 8: Write manifest ---
    _log(node, "[8/9] Writing manifest...")

    elapsed = time.time() - t_start

    manifest_data = MantraManifestData(
        shot_name=shot_name,
        folder_name=folder_name,
        houdini_version=houdini_version,
        generated_at=datetime.now().isoformat(timespec="seconds"),
        elapsed_seconds=elapsed,
        frame_start=int(f_start),
        frame_end=int(f_end),
        frame_inc=int(f_inc),
        resolution=audit.resolution,
        pixel_samples=audit.pixel_samples,
        render_engine=audit.render_engine,
        camera=audit.camera,
        aov_count=audit.aov_count,
        rop_node_path=rop_node_path,
        output_picture=output_pattern,
        ifd_count=len(ifd_paths),
        ifd_total_size_mb=ifd_total_size_mb,
        ifd_pattern=ifd_printf_pattern,
        texture_count=len(texture_paths),
        textures_size_mb=textures_size_mb,
        backup_zip_path=f"{shot_name}_original.hip.zip",
        backup_zip_size_mb=zip_size_mb,
        warnings=warnings,
    )

    manifest_path = os.path.join(shot_root, f"{shot_name}_manifest.txt")
    write_mantra_manifest(manifest_path, manifest_data)
    _log(node, "  Written.")

    # --- Step 9: Done ---
    elapsed = time.time() - t_start
    _log(node, "")
    _log(node, "=" * 50)
    _log(node, f"PACKAGE COMPLETE — {elapsed:.1f}s")
    _log(node, f"Output: {folder_name}/")
    _log(node, f"IFDs: {len(ifd_paths)} files ({ifd_total_size_mb:.1f} MB)")
    _log(node, f"Textures: {len(texture_paths)} files ({textures_size_mb:.1f} MB)")
    _log(node, "=" * 50)

    if warnings:
        _log(node, "")
        for w in warnings:
            _log(node, f"  ! {w}")
