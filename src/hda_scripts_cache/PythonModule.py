"""HDA-embedded Python entry points for remote_file_cache.

Wraps a File Cache SOP with remote packaging capabilities.
All paths are relative to $HIP (the directory containing the .hip file).
"""

import os
import sys
import time
from datetime import datetime


def _ensure_src_path(node):
    """Ensure the src/ directory is on sys.path for imports.

    Derives the repo root from the HDA's library file path:
    src/hda/remote_file_cache.hdalc -> repo root is two levels up.
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


def _get_filecache_node(node):
    """Return the internal filecache1 node."""
    fc = node.node("filecache1")
    return fc


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
    from src.cache_validator import (
        validate_cache_node, validate_frame_range, validate_output_path,
    )

    _log(node, "=" * 50)
    _log(node, "VERIFY — Remote File Cache")
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

    # 3. File Cache node
    fc = _get_filecache_node(node)
    ok, msg = validate_cache_node(fc)
    if ok:
        _log(node, f"[OK] File Cache node: {fc.path()}")
    else:
        _log(node, f"[FAIL] {msg}")
        failures += 1
        # Can't continue without the node
        _log(node, "")
        _log(node, f"Verify complete: {failures} failure(s).")
        return

    # 4. Frame range
    f_start = fc.parm("f1").eval()
    f_end = fc.parm("f2").eval()
    f_inc = fc.parm("f3").eval()
    ok, msg = validate_frame_range(f_start, f_end, f_inc)
    if ok:
        frame_count = int((f_end - f_start) / f_inc) + 1
        _log(node, f"[OK] Frame range: {int(f_start)}-{int(f_end)} ({frame_count} frames)")
    else:
        _log(node, f"[FAIL] Frame range: {msg}")
        failures += 1

    # 5. Output path
    output_path = fc.parm("sopoutput").eval()
    ok, msg = validate_output_path(output_path)
    if ok:
        _log(node, f"[OK] Output path: {output_path}")
    else:
        _log(node, f"[FAIL] Output path: {msg}")
        failures += 1

    # 6. Background save warning
    if fc.parm("savebackground").eval():
        _log(node, "[WARN] 'Save in Background' is ON — will be forced OFF in packaged .hip.")

    # 7. Load from disk warning
    if fc.parm("loadfromdisk").eval():
        _log(node, "[WARN] 'Load from Disk' is ON — will be forced OFF in packaged .hip.")

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
    """Full packaging — creates portable folder with .hip, scripts, metadata."""
    import hou

    node = kwargs["node"]
    node.parm("log_output").set("")
    _ensure_src_path(node)

    from src.validator import validate_shot_name, validate_hip_saved
    from src.cache_validator import (
        validate_cache_node, validate_frame_range, validate_output_path,
    )
    from src.cache_scene_writer import save_portable_hip, backup_hip_as_zip
    from src.cache_info_writer import write_cache_info
    from src.cache_script_writer import write_cache_script
    from src.cache_manifest import CacheManifestData, write_cache_manifest
    from src.platform_utils import ensure_dir, check_disk_space

    t_start = time.time()
    warnings = []

    _log(node, "=" * 50)
    _log(node, "PACKAGE — Remote File Cache")
    _log(node, "=" * 50)
    _log(node, "")

    # --- Step 1: Validate ---
    _log(node, "[1/7] Validating...")

    shot_name = node.parm("shot_name").eval()
    ok, msg = validate_shot_name(shot_name)
    if not ok:
        _log(node, f"  [FAIL] {msg}")
        hou.ui.displayMessage(msg, title="Package Failed")
        return

    ok, msg = validate_hip_saved()
    if not ok:
        _log(node, f"  [FAIL] {msg}")
        hou.ui.displayMessage(msg, title="Package Failed")
        return
    if msg:
        warnings.append(msg)
        _log(node, f"  [WARN] {msg}")

    fc = _get_filecache_node(node)
    ok, msg = validate_cache_node(fc)
    if not ok:
        _log(node, f"  [FAIL] {msg}")
        hou.ui.displayMessage(msg, title="Package Failed")
        return

    f_start = fc.parm("f1").eval()
    f_end = fc.parm("f2").eval()
    f_inc = fc.parm("f3").eval()
    ok, msg = validate_frame_range(f_start, f_end, f_inc)
    if not ok:
        _log(node, f"  [FAIL] {msg}")
        hou.ui.displayMessage(msg, title="Package Failed")
        return

    output_path = fc.parm("sopoutput").eval()
    ok, msg = validate_output_path(output_path)
    if not ok:
        _log(node, f"  [FAIL] {msg}")
        hou.ui.displayMessage(msg, title="Package Failed")
        return

    _log(node, "  All checks passed.")

    # --- Step 2: Create directories ---
    _log(node, "[2/7] Creating directories...")

    hip_dir = _get_hip_dir()
    folder_name = _build_folder_name(node)
    shot_root = os.path.join(hip_dir, folder_name)

    if os.path.exists(shot_root):
        result = hou.ui.displayMessage(
            f"Folder '{folder_name}' already exists. Overwrite?",
            buttons=("Overwrite", "Cancel"),
            severity=hou.severityType.Warning,
            title="Folder Exists",
        )
        if result == 1:
            _log(node, "  Cancelled by user.")
            return

    for subdir in ("Cache", "Scenes", "Scripts"):
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
    _log(node, "[3/7] Backing up .hip file...")

    zip_path = os.path.join(shot_root, f"{shot_name}_original.hip.zip")
    backup_hip_as_zip(zip_path)
    zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    _log(node, f"  Backup: {zip_size_mb:.1f} MB")

    # --- Step 4: Save portable .hip ---
    _log(node, "[4/7] Saving portable .hip...")

    hip_filename = f"{shot_name}.hip"
    portable_hip = os.path.join(shot_root, "Scenes", hip_filename)
    save_portable_hip(fc, portable_hip)
    hip_size_mb = os.path.getsize(portable_hip) / (1024 * 1024)
    _log(node, f"  Saved: Scenes/{hip_filename} ({hip_size_mb:.1f} MB)")

    # --- Step 5: Write cache_info.txt ---
    _log(node, "[5/7] Writing cache_info.txt...")

    cache_format = fc.parm("filetype").evalAsString()
    substeps = fc.parm("substeps").eval()
    cache_node_path = fc.path()

    info_path = os.path.join(shot_root, "cache_info.txt")

    # Build the cache output pattern for the remote location
    basename = fc.parm("basename").eval()
    cache_output_pattern = f"Cache/{basename}.$F4{cache_format}"

    houdini_version = hou.applicationVersionString()

    write_cache_info(
        output_path=info_path,
        shot_name=shot_name,
        folder_name=folder_name,
        frame_start=f_start,
        frame_end=f_end,
        frame_inc=f_inc,
        substeps=substeps,
        cache_format=cache_format,
        cache_node_path=cache_node_path,
        cache_output_pattern=cache_output_pattern,
        hip_filename=hip_filename,
        houdini_version=houdini_version,
    )
    _log(node, "  Written.")

    # --- Step 6: Write run_cache.sh ---
    _log(node, "[6/7] Writing run_cache.sh...")

    script_path = os.path.join(shot_root, "Scripts", "run_cache.sh")
    write_cache_script(
        output_path=script_path,
        shot_name=shot_name,
        hip_filename=hip_filename,
        cache_node_path=cache_node_path,
        frame_start=int(f_start),
        frame_end=int(f_end),
    )
    _log(node, "  Written and made executable.")

    # --- Step 7: Write manifest ---
    _log(node, "[7/7] Writing manifest...")

    elapsed = time.time() - t_start

    manifest_data = CacheManifestData(
        shot_name=shot_name,
        folder_name=folder_name,
        houdini_version=houdini_version,
        generated_at=datetime.now().isoformat(timespec="seconds"),
        elapsed_seconds=elapsed,
        frame_start=int(f_start),
        frame_end=int(f_end),
        frame_inc=int(f_inc),
        substeps=substeps,
        cache_format=cache_format,
        cache_node_path=cache_node_path,
        cache_output_pattern=cache_output_pattern,
        hip_path=f"Scenes/{hip_filename}",
        hip_size_mb=hip_size_mb,
        backup_zip_path=f"{shot_name}_original.hip.zip",
        backup_zip_size_mb=zip_size_mb,
        warnings=warnings,
    )

    manifest_path = os.path.join(shot_root, f"{shot_name}_manifest.txt")
    write_cache_manifest(manifest_path, manifest_data)
    _log(node, "  Written.")

    # --- Done ---
    _log(node, "")
    _log(node, "=" * 50)
    _log(node, f"PACKAGE COMPLETE — {elapsed:.1f}s")
    _log(node, f"Output: {folder_name}/")
    _log(node, "=" * 50)

    if warnings:
        _log(node, "")
        for w in warnings:
            _log(node, f"  ! {w}")


def on_update_clicked(kwargs):
    """Pull latest from git and reload all HDAs in this repo."""
    import hou
    import subprocess
    import glob
    node = kwargs["node"]

    hda_def = node.type().definition()
    hda_dir = os.path.dirname(hda_def.libraryFilePath())
    repo_root = os.path.dirname(os.path.dirname(hda_dir))

    try:
        result = subprocess.run(
            ["git", "pull"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as e:
        hou.ui.displayMessage(f"git pull failed:\n{e}", severity=hou.severityType.Error)
        return

    if result.returncode != 0:
        hou.ui.displayMessage(
            f"git pull failed:\n\n{result.stderr.strip()}",
            severity=hou.severityType.Error,
        )
        return

    hda_path = os.path.join(repo_root, "src", "hda")
    reloaded = []
    for hda_file in sorted(glob.glob(os.path.join(hda_path, "*.hda*"))):
        try:
            hou.hda.reloadFile(hda_file)
            reloaded.append(os.path.basename(hda_file))
        except Exception:
            pass

    msg = result.stdout.strip() or "Already up to date."
    if reloaded:
        msg += "\n\nReloaded:\n" + "\n".join(reloaded)
    hou.ui.displayMessage(msg, title="Update Complete")
