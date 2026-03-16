"""Integration tests for Remote File Cache with headless Houdini.

These tests require $HFS set and hython/hbatch available. They:
1. Create minimal .hip scenes via hython (box + filecache::2.0)
2. Generate run_cache.sh using cache_script_writer
3. Execute via bash (which runs hbatch)
4. Verify output cache files exist

Skipped in CI via the houdini marker: `pytest -m "not houdini"`
"""

import glob
import os
import subprocess
import tempfile
import textwrap

import pytest

pytestmark = pytest.mark.houdini

from src.cache_script_writer import write_cache_script


def _hython():
    """Return path to hython binary."""
    hfs = os.environ.get("HFS", "")
    return os.path.join(hfs, "bin", "hython") if hfs else "hython"


def _create_test_hip(hip_path, cache_dir, frame_start=1, frame_end=1, basename="test"):
    """Create a minimal .hip with box -> filecache via hython subprocess.

    The hip contains /obj/test_geo with a box wired into filecache::2.0.
    Cache basedir is set to an absolute path so output location is predictable.
    """
    script = textwrap.dedent(f"""\
        import hou
        obj = hou.node("/obj")
        geo = obj.createNode("geo", "test_geo")
        for child in geo.children():
            child.destroy()
        box = geo.createNode("box", "box1")
        fc = geo.createNode("filecache::2.0", "filecache1")
        fc.setInput(0, box)
        fc.parm("filemethod").set(0)
        fc.parm("basedir").set("{cache_dir}")
        fc.parm("basename").set("{basename}")
        fc.parm("enableversion").set(0)
        fc.parm("trange").set(1)
        fc.parm("f1").set({frame_start})
        fc.parm("f2").set({frame_end})
        fc.parm("f3").set(1)
        fc.parm("savebackground").set(0)
        fc.parm("loadfromdisk").set(0)
        fc.parm("timedependent").set(1)
        hou.hipFile.save("{hip_path}")
    """)

    script_file = hip_path + ".setup.py"
    with open(script_file, "w") as f:
        f.write(script)

    try:
        result = subprocess.run(
            [_hython(), script_file],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"hython setup failed (rc={result.returncode}):\n"
                f"{result.stderr}\n{result.stdout}"
            )
    finally:
        if os.path.exists(script_file):
            os.unlink(script_file)


def _resolve_hip_path(hip_path):
    """Return actual .hip path — Indie saves as .hiplc, Apprentice as .hipnc."""
    if os.path.exists(hip_path):
        return hip_path
    for ext in (".hiplc", ".hipnc"):
        alt = hip_path.rsplit(".hip", 1)[0] + ext
        if os.path.exists(alt):
            return alt
    raise FileNotFoundError(
        f"hython did not create {hip_path} (or .hiplc/.hipnc variant)"
    )


def _build_cache_dir(tmpdir, frame_start=1, frame_end=1, basename="test"):
    """Build a minimal cache package directory.

    Returns:
        (hip_path, script_path, output_dir)
        output_dir is where filecache::2.0 writes files:
        basedir/basename/ (it creates a subdirectory named after basename).
    """
    scenes_dir = os.path.join(tmpdir, "Scenes")
    cache_dir = os.path.join(tmpdir, "Cache")
    scripts_dir = os.path.join(tmpdir, "Scripts")
    os.makedirs(scenes_dir)
    os.makedirs(cache_dir)
    os.makedirs(scripts_dir)

    requested_hip = os.path.join(scenes_dir, "test.hip")
    _create_test_hip(requested_hip, cache_dir, frame_start, frame_end, basename)

    actual_hip = _resolve_hip_path(requested_hip)
    hip_filename = os.path.basename(actual_hip)

    script_path = os.path.join(scripts_dir, "run_cache.sh")
    write_cache_script(
        output_path=script_path,
        shot_name="test",
        hip_filename=hip_filename,
        cache_node_path="/obj/test_geo/filecache1",
        frame_start=frame_start,
        frame_end=frame_end,
    )

    # filecache::2.0 outputs to basedir/basename/basename.NNNN.bgeo.sc
    output_dir = os.path.join(cache_dir, basename)

    return actual_hip, script_path, output_dir


def _run_script(script_path):
    """Run a cache script with $HFS/bin on PATH, return (returncode, output)."""
    env = os.environ.copy()
    hfs = env.get("HFS", "")
    if hfs:
        env["PATH"] = os.path.join(hfs, "bin") + ":" + env.get("PATH", "")

    result = subprocess.run(
        ["bash", script_path],
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
    )
    return result.returncode, result.stdout + result.stderr


class TestHbatchCache:
    """Tests that create .hip files via hython and run hbatch."""

    def test_single_frame_cache(self):
        """Cache a single frame, verify .bgeo.sc output exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _, script_path, cache_dir = _build_cache_dir(tmpdir)

            rc, output = _run_script(script_path)
            assert rc == 0, f"run_cache.sh failed:\n{output}"

            bgeo_files = glob.glob(os.path.join(cache_dir, "test.*.bgeo.sc"))
            assert len(bgeo_files) >= 1, (
                f"No .bgeo.sc files in {cache_dir}. "
                f"Contents: {os.listdir(cache_dir)}"
            )

    def test_multi_frame_cache(self):
        """Cache 3 frames, verify numbered outputs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _, script_path, cache_dir = _build_cache_dir(
                tmpdir, frame_start=1, frame_end=3
            )

            rc, output = _run_script(script_path)
            assert rc == 0, f"run_cache.sh failed:\n{output}"

            for frame in (1, 2, 3):
                pattern = os.path.join(cache_dir, f"test.{frame:04d}.bgeo.sc")
                assert glob.glob(pattern), (
                    f"Missing frame {frame}. "
                    f"Contents: {os.listdir(cache_dir)}"
                )

    def test_cache_file_nonempty(self):
        """Cached .bgeo.sc has non-trivial size (a box is real geometry)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _, script_path, cache_dir = _build_cache_dir(tmpdir)

            rc, output = _run_script(script_path)
            assert rc == 0, f"run_cache.sh failed:\n{output}"

            bgeo_files = glob.glob(os.path.join(cache_dir, "test.*.bgeo.sc"))
            assert bgeo_files, f"No cache files in {cache_dir}"
            for path in bgeo_files:
                size = os.path.getsize(path)
                assert size > 100, f"{path} suspiciously small ({size} bytes)"
