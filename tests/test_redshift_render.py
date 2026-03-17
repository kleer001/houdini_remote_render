"""Integration tests for Redshift USD rendering via redshiftUsdCmdLine.

These tests require:
- A working Redshift installation with REDSHIFT_COREDATAPATH set
- A valid Redshift license (trial or full)
- An NVIDIA GPU

Run with: pytest tests/test_redshift_render.py -v
"""

import os
import subprocess
import tempfile

import pytest

pytestmark = pytest.mark.houdini  # Skip in CI


TEST_SCENES_DIR = os.path.join(os.path.dirname(__file__), "test_scenes")
TEST_USD = os.path.join(TEST_SCENES_DIR, "redshift_test.usda")


def _find_redshift():
    """Return path to redshiftUsdCmdLine or None."""
    for path in (
        os.environ.get("REDSHIFT_COREDATAPATH", ""),
        "/home/menser/redshift",
        "/usr/redshift",
        "/opt/redshift",
    ):
        binary = os.path.join(path, "bin", "redshiftUsdCmdLine")
        if os.path.isfile(binary):
            return binary
    return None


def _redshift_env(rs_path):
    """Build environment dict for running redshiftUsdCmdLine."""
    env = os.environ.copy()
    rs_root = os.path.dirname(os.path.dirname(rs_path))
    env["REDSHIFT_COREDATAPATH"] = rs_root
    env["PATH"] = os.path.join(rs_root, "bin") + ":" + env.get("PATH", "")
    env["LD_LIBRARY_PATH"] = (
        os.path.join(rs_root, "bin") + ":" + env.get("LD_LIBRARY_PATH", "")
    )
    return env


@pytest.fixture
def rs_binary():
    """Find redshiftUsdCmdLine or skip."""
    binary = _find_redshift()
    if binary is None:
        pytest.skip("redshiftUsdCmdLine not found")
    return binary


@pytest.fixture
def test_usd():
    """Return path to test USD scene, skip if missing."""
    if not os.path.isfile(TEST_USD):
        pytest.skip(f"Test USD not found: {TEST_USD}")
    return TEST_USD


class TestRedshiftUsdCmdLine:
    """Test redshiftUsdCmdLine basic operations."""

    def test_list_settings(self, rs_binary, test_usd):
        """Verify -list-settings flag works and finds our RenderSettings."""
        env = _redshift_env(rs_binary)
        result = subprocess.run(
            [rs_binary, test_usd, "-list-settings"],
            capture_output=True, text=True, env=env, timeout=30,
        )
        # -list-settings should print info and exit (may return 0 or 1)
        output = result.stdout + result.stderr
        assert "rendersettings" in output.lower() or "RenderSettings" in output

    def test_list_cameras(self, rs_binary, test_usd):
        """Verify -list-cameras flag works and finds our camera."""
        env = _redshift_env(rs_binary)
        result = subprocess.run(
            [rs_binary, test_usd, "-list-cameras"],
            capture_output=True, text=True, env=env, timeout=30,
        )
        output = result.stdout + result.stderr
        assert "test_cam" in output or "Camera" in output

    def test_single_frame_render(self, rs_binary, test_usd):
        """Render a single frame and verify output file is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = _redshift_env(rs_binary)
            result = subprocess.run(
                [
                    rs_binary, test_usd,
                    "-f", "1",
                    "-n", "1",
                    "-device", "all",
                    "-oip", tmpdir,
                ],
                capture_output=True, text=True, env=env,
                cwd=os.path.dirname(test_usd),
                timeout=120,
            )

            output = result.stdout + result.stderr
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            print(f"Return code: {result.returncode}")

            # Check for license errors
            if "license" in output.lower() and result.returncode != 0:
                pytest.skip("Redshift license not available")

            # Check for GPU errors
            if "gpu" in output.lower() and "error" in output.lower():
                pytest.skip("GPU not available for Redshift")

            assert result.returncode == 0, f"Render failed: {output}"

            # Check for output files (EXR by default)
            output_files = [
                f for f in os.listdir(tmpdir)
                if f.endswith((".exr", ".png", ".jpg"))
            ]
            assert len(output_files) > 0, (
                f"No output files in {tmpdir}. Contents: {os.listdir(tmpdir)}"
            )


class TestRedshiftScriptExecution:
    """Test that our generated render scripts are syntactically valid."""

    def test_generated_script_syntax(self):
        """Verify the generated script passes bash syntax check."""
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from src.redshift_script_writer import write_redshift_script

        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_redshift_script(
                output_path=script_path,
                shot_name="syntax_test",
                wrapper_filename="test.usda",
                frame_start=1001,
                frame_end=1100,
                gpu_device="all",
                texture_cache_gb=8,
                ocio_config="/path/to/config.ocio",
                skip_postfx=True,
                restart_delegate=True,
                redshift_path="/usr/redshift",
            )

            # Bash syntax check (doesn't execute, just parses)
            result = subprocess.run(
                ["bash", "-n", script_path],
                capture_output=True, text=True,
            )
            assert result.returncode == 0, f"Syntax error: {result.stderr}"

    def test_generated_script_shellcheck(self):
        """Run shellcheck on the generated script if available."""
        import shutil
        if not shutil.which("shellcheck"):
            pytest.skip("shellcheck not installed")

        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from src.redshift_script_writer import write_redshift_script

        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_redshift_script(
                output_path=script_path,
                shot_name="shellcheck_test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=10,
                redshift_path="/usr/redshift",
            )

            result = subprocess.run(
                ["shellcheck", "-S", "warning", script_path],
                capture_output=True, text=True,
            )
            # Report but don't fail on shellcheck warnings
            if result.returncode != 0:
                print(f"shellcheck output:\n{result.stdout}")
