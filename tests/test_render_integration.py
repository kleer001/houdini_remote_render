"""Integration tests that render with standalone husk.

These tests require $HFS set and husk available. They create a minimal
USD scene as raw text (no pxr dependency), generate a render script,
run husk, and verify the output EXR.

Skipped in CI via the houdini marker: `pytest -m "not houdini"`
"""

import os
import subprocess
import tempfile

import pytest

pytestmark = pytest.mark.houdini

# Minimal renderable USD scene — sphere + camera + dome light + render settings.
# 320x240, 16 samples for fast test renders.
_MINIMAL_USDA = """\
#usda 1.0
(
    startTimeCode = {frame_start}
    endTimeCode = {frame_end}
)

def Xform "World"
{{
    def Sphere "sphere"
    {{
        double radius = 1.0
    }}

    def Camera "camera"
    {{
        float focalLength = 50
        double3 xformOp:translate = (0, 0, 10)
        uniform token[] xformOpOrder = ["xformOp:translate"]
    }}

    def DomeLight "domeLight"
    {{
    }}
}}

def Scope "Render"
{{
    def RenderSettings "settings"
    {{
        int2 resolution = (320, 240)
        rel camera = </World/camera>
        rel products = [</Render/product>]
        int karma:global:pathtracedsamples = 16
    }}

    def RenderProduct "product"
    {{
        token productName = "../Output/test.<F4>.exr"
        rel orderedVars = [</Render/product/beauty>]

        def RenderVar "beauty"
        {{
            token dataType = "color3f"
            string driver:parameters:aov:name = "C"
        }}
    }}
}}
"""


def _build_shot_dir(tmpdir, frame_start=1, frame_end=1):
    """Build a minimal shot directory and return (scene_path, script_path, output_dir)."""
    scenes_dir = os.path.join(tmpdir, "Scenes")
    output_dir = os.path.join(tmpdir, "Output")
    scripts_dir = os.path.join(tmpdir, "Scripts")
    os.makedirs(scenes_dir)
    os.makedirs(output_dir)
    os.makedirs(scripts_dir)

    scene_path = os.path.join(scenes_dir, "test.usda")
    with open(scene_path, "w") as f:
        f.write(_MINIMAL_USDA.format(frame_start=frame_start, frame_end=frame_end))

    from src.render_script_writer import write_render_script

    script_path = os.path.join(scripts_dir, "run_render.sh")
    write_render_script(
        output_path=script_path,
        shot_name="test",
        wrapper_filename="test.usda",
        frame_start=frame_start,
        frame_end=frame_end,
    )

    return scene_path, script_path, output_dir


def _run_script(script_path):
    """Run a render script and return (returncode, stdout+stderr)."""
    result = subprocess.run(
        ["bash", script_path],
        capture_output=True,
        text=True,
        timeout=300,
    )
    return result.returncode, result.stdout + result.stderr


class TestHuskRender:
    """Tests that invoke standalone husk via the generated render script."""

    def test_single_frame_render(self):
        """Render a single frame, verify EXR output exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _, script_path, output_dir = _build_shot_dir(tmpdir)

            rc, output = _run_script(script_path)
            assert rc == 0, f"run_render.sh failed:\n{output}"

            exr_path = os.path.join(output_dir, "test.0001.exr")
            assert os.path.isfile(exr_path), f"Missing {exr_path}"
            assert os.path.getsize(exr_path) > 1000, "EXR suspiciously small"

    def test_multi_frame_render(self):
        """Render 3 frames, verify numbered EXR outputs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _, script_path, output_dir = _build_shot_dir(
                tmpdir, frame_start=1, frame_end=3
            )

            rc, output = _run_script(script_path)
            assert rc == 0, f"run_render.sh failed:\n{output}"

            for frame in (1, 2, 3):
                exr_path = os.path.join(output_dir, f"test.{frame:04d}.exr")
                assert os.path.isfile(exr_path), f"Missing frame {frame}"
                assert os.path.getsize(exr_path) > 1000, f"Frame {frame} too small"

    def test_restart_delegate_in_sequence(self):
        """--restart-delegate auto-added for sequences."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _, script_path, _ = _build_shot_dir(
                tmpdir, frame_start=1, frame_end=3
            )
            with open(script_path) as f:
                content = f.read()
            assert "--restart-delegate 1" in content

    def test_no_restart_delegate_single_frame(self):
        """--restart-delegate NOT added for single frame."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _, script_path, _ = _build_shot_dir(tmpdir)
            with open(script_path) as f:
                content = f.read()
            assert "--restart-delegate" not in content

    def test_hfs_sourced_in_script(self):
        """Script sources the Houdini environment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _, script_path, _ = _build_shot_dir(tmpdir)
            with open(script_path) as f:
                content = f.read()
            assert "houdini_setup_bash" in content

    def test_output_resolution(self):
        """Rendered EXR matches the 320x240 resolution via iinfo."""
        hfs = os.environ.get("HFS", "")
        iinfo = os.path.join(hfs, "bin", "iinfo") if hfs else "iinfo"

        with tempfile.TemporaryDirectory() as tmpdir:
            _, script_path, output_dir = _build_shot_dir(tmpdir)

            rc, output = _run_script(script_path)
            assert rc == 0, f"run_render.sh failed:\n{output}"

            exr_path = os.path.join(output_dir, "test.0001.exr")
            result = subprocess.run(
                [iinfo, exr_path],
                capture_output=True,
                text=True,
            )
            assert "320 x 240" in result.stdout, (
                f"Expected 320x240 in iinfo output:\n{result.stdout}"
            )
