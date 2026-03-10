"""Karma USD Packager — pipeline entry point.

This module can be called directly for headless packaging,
or invoked from the HDA's PythonModule callbacks.
All output is relative to hip_dir ($HIP).
"""

import os
import shutil
import tempfile
import time
from datetime import datetime

from src.validator import validate_shot_name
from src.auditor import audit_stage, ensure_render_settings
from src.output_injector import inject_output_paths
from src.packager import flatten_stage, create_usdz
from src.wrapper_writer import write_wrapper
from src.manifest import ManifestData, write_manifest
from src.platform_utils import ensure_dir


def run_pipeline(
    stage,
    shot_name: str,
    hip_dir: str,
    frame_start: int = 1,
    frame_end: int = 1,
    output_format: str = "png",
    usdz_filename: str | None = None,
    wrapper_filename: str | None = None,
    dry_run: bool = False,
) -> list[str]:
    """Run the full packaging pipeline.

    Args:
        stage: A Usd.Stage from a LOP network.
        shot_name: Name of the shot.
        hip_dir: Directory containing the .hip file ($HIP).
        frame_start: First frame to render.
        frame_end: Last frame to render.
        output_format: Image format — "png" or "exr".
        usdz_filename: Override USDZ filename (default: {shot_name}.usdz).
        wrapper_filename: Override wrapper filename (default: {shot_name}.usda).
        dry_run: If True, only validate and audit without producing files.

    Returns:
        List of log messages.
    """
    log = []
    t0 = time.time()

    usdz_filename = usdz_filename or f"{shot_name}.usdz"
    wrapper_filename = wrapper_filename or f"{shot_name}.usda"

    # 1. Validate
    ok, msg = validate_shot_name(shot_name)
    if not ok:
        raise ValueError(msg)
    log.append(f"Shot name: {shot_name}")
    log.append(f"HIP dir: {hip_dir}")

    # 2. Audit
    report = audit_stage(stage)
    ensure_render_settings(stage)
    log.append(f"Stage audit: {sum(1 for _ in stage.Traverse())} prims")
    for w in report.warnings:
        log.append(f"  ! {w}")

    if dry_run:
        log.append("=== DRY RUN COMPLETE ===")
        return log

    # 3. Create shot directories at hip_dir/shot_name/
    shot_dir = os.path.join(hip_dir, shot_name)
    for d in ("Output", "Textures", "Cache", "Scenes", "Scripts"):
        ensure_dir(os.path.join(shot_dir, d))

    # 4. Inject output paths
    inject_output_paths(
        stage, shot_name,
        output_format=output_format,
        frame_start=frame_start,
        frame_end=frame_end,
    )
    log.append(f"Output paths injected (format: {output_format}, frames: {frame_start}-{frame_end})")

    # 5. Flatten & USDZ
    staging_dir = tempfile.mkdtemp(prefix="usd_packager_")
    flat_path = flatten_stage(stage, staging_dir)

    scenes_dir = os.path.join(shot_dir, "Scenes")
    usdz_path = os.path.join(scenes_dir, usdz_filename)
    create_usdz(flat_path, usdz_path)
    shutil.rmtree(staging_dir, ignore_errors=True)
    usdz_size = os.path.getsize(usdz_path) / (1024 * 1024)
    log.append(f"USDZ: {usdz_path} ({usdz_size:.2f} MB)")

    # 6. Wrapper
    wrapper_path = os.path.join(scenes_dir, wrapper_filename)
    write_wrapper(usdz_filename, {}, wrapper_path)
    log.append(f"Wrapper: {wrapper_path}")

    # 6b. Write render_info.txt for farm scripts
    render_info_path = os.path.join(shot_dir, "render_info.txt")
    frame_count = frame_end - frame_start + 1
    with open(render_info_path, "w") as f:
        f.write(f"startframe={frame_start}\n")
        f.write(f"endframe={frame_end}\n")
        f.write(f"framecount={frame_count}\n")
        f.write(f"usdfile=Scenes/{wrapper_filename}\n")
    log.append(f"Render info: {render_info_path}")

    # 7. Manifest
    manifest_path = os.path.join(shot_dir, f"{shot_name}_manifest.txt")

    try:
        import hou
        houdini_version = hou.applicationVersionString()
    except ImportError:
        houdini_version = "unknown"

    elapsed = time.time() - t0
    manifest_data = ManifestData(
        shot_name=shot_name,
        houdini_version=houdini_version,
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
    log.append(f"Manifest: {manifest_path}")

    log.append(f"=== PACKAGING COMPLETE ({elapsed:.1f}s) ===")
    return log
