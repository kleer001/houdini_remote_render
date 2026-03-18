"""Tests for the universal Python launcher scripts."""

import os
import subprocess
import sys
import tempfile

LAUNCHERS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "src", "launchers",
)


class TestRunRenderLauncher:
    def test_file_exists(self):
        assert os.path.isfile(os.path.join(LAUNCHERS_DIR, "run_render.py"))

    def test_no_external_imports(self):
        with open(os.path.join(LAUNCHERS_DIR, "run_render.py")) as f:
            content = f.read()
        assert "from src" not in content
        assert "import src" not in content
        assert "import hou" not in content

    def test_has_dry_run_flag(self):
        with open(os.path.join(LAUNCHERS_DIR, "run_render.py")) as f:
            content = f.read()
        assert "--dry-run" in content

    def test_syntax_valid(self):
        path = os.path.join(LAUNCHERS_DIR, "run_render.py")
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", path],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

    def test_help_flag(self):
        path = os.path.join(LAUNCHERS_DIR, "run_render.py")
        result = subprocess.run(
            [sys.executable, path, "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "render_info.txt" in result.stdout

    def test_missing_info_file_exits_cleanly(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scripts_dir = os.path.join(tmpdir, "Scripts")
            os.makedirs(scripts_dir)
            # Copy launcher into Scripts/
            import shutil
            src = os.path.join(LAUNCHERS_DIR, "run_render.py")
            dst = os.path.join(scripts_dir, "run_render.py")
            shutil.copy2(src, dst)

            # No render_info.txt — should exit with error
            result = subprocess.run(
                [sys.executable, dst],
                capture_output=True, text=True,
            )
            assert result.returncode != 0
            assert "render_info.txt" in result.stderr or "render_info.txt" in result.stdout

    def test_dry_run_with_karma_info(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scripts_dir = os.path.join(tmpdir, "Scripts")
            scenes_dir = os.path.join(tmpdir, "Scenes")
            os.makedirs(scripts_dir)
            os.makedirs(scenes_dir)

            # Write a minimal render_info.txt
            info_path = os.path.join(tmpdir, "render_info.txt")
            with open(info_path, "w") as f:
                f.write("renderer=BRAY_HdKarma\n")
                f.write("usdfile=test.usda\n")
                f.write("startframe=1001\n")
                f.write("framecount=100\n")
                f.write("frameinc=1\n")

            # Copy launcher
            import shutil
            shutil.copy2(
                os.path.join(LAUNCHERS_DIR, "run_render.py"),
                os.path.join(scripts_dir, "run_render.py"),
            )

            result = subprocess.run(
                [sys.executable, os.path.join(scripts_dir, "run_render.py"), "--dry-run"],
                capture_output=True, text=True,
            )
            output = result.stdout + result.stderr
            assert "husk" in output.lower() or "DRY RUN" in output

    def test_dry_run_with_redshift_info(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scripts_dir = os.path.join(tmpdir, "Scripts")
            scenes_dir = os.path.join(tmpdir, "Scenes")
            os.makedirs(scripts_dir)
            os.makedirs(scenes_dir)

            info_path = os.path.join(tmpdir, "render_info.txt")
            with open(info_path, "w") as f:
                f.write("renderer=redshift\n")
                f.write("command=redshiftUsdCmdLine\n")
                f.write("usd_file=test.usda\n")
                f.write("startframe=1001\n")
                f.write("endframe=1100\n")
                f.write("frameinc=1\n")
                f.write("gpu_device=all\n")

            import shutil
            shutil.copy2(
                os.path.join(LAUNCHERS_DIR, "run_render.py"),
                os.path.join(scripts_dir, "run_render.py"),
            )

            result = subprocess.run(
                [sys.executable, os.path.join(scripts_dir, "run_render.py"), "--dry-run"],
                capture_output=True, text=True,
            )
            output = result.stdout + result.stderr
            assert "redshiftUsdCmdLine" in output or "Redshift" in output

    def test_dry_run_with_mantra_info(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scripts_dir = os.path.join(tmpdir, "Scripts")
            ifds_dir = os.path.join(tmpdir, "IFDs")
            os.makedirs(scripts_dir)
            os.makedirs(ifds_dir)

            info_path = os.path.join(tmpdir, "render_info.txt")
            with open(info_path, "w") as f:
                f.write("renderer=mantra\n")
                f.write("method=ifd\n")
                f.write("ifd_pattern=shot.%04d.ifd\n")
                f.write("startframe=1001\n")
                f.write("endframe=1010\n")
                f.write("frameinc=1\n")

            import shutil
            shutil.copy2(
                os.path.join(LAUNCHERS_DIR, "run_render.py"),
                os.path.join(scripts_dir, "run_render.py"),
            )

            result = subprocess.run(
                [sys.executable, os.path.join(scripts_dir, "run_render.py"), "--dry-run"],
                capture_output=True, text=True,
            )
            output = result.stdout + result.stderr
            assert "mantra" in output.lower() or "Mantra" in output


class TestRunCacheLauncher:
    def test_file_exists(self):
        assert os.path.isfile(os.path.join(LAUNCHERS_DIR, "run_cache.py"))

    def test_syntax_valid(self):
        path = os.path.join(LAUNCHERS_DIR, "run_cache.py")
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", path],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

    def test_help_flag(self):
        path = os.path.join(LAUNCHERS_DIR, "run_cache.py")
        result = subprocess.run(
            [sys.executable, path, "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "cache_info.txt" in result.stdout


class TestRunAllLauncher:
    def test_file_exists(self):
        assert os.path.isfile(os.path.join(LAUNCHERS_DIR, "run_all.py"))

    def test_syntax_valid(self):
        path = os.path.join(LAUNCHERS_DIR, "run_all.py")
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", path],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

    def test_help_flag(self):
        path = os.path.join(LAUNCHERS_DIR, "run_all.py")
        result = subprocess.run(
            [sys.executable, path, "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "cache" in result.stdout.lower()


class TestReadInfoFile:
    def test_parses_key_value(self):
        """Verify the launcher's info file parser handles all formats."""
        # Import the parse function by running it in a subprocess
        with tempfile.TemporaryDirectory() as tmpdir:
            info_path = os.path.join(tmpdir, "test_info.txt")
            with open(info_path, "w") as f:
                f.write("key1=value1\n")
                f.write("key2=value with spaces\n")
                f.write("# comment line\n")
                f.write("\n")
                f.write("key3=123\n")

            result = subprocess.run(
                [sys.executable, "-c", f"""
import sys
sys.path.insert(0, '{LAUNCHERS_DIR}')
# The launcher is standalone, so we import it as a module
import importlib.util
spec = importlib.util.spec_from_file_location("run_render", "{os.path.join(LAUNCHERS_DIR, 'run_render.py')}")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
info = mod.read_info_file("{info_path}")
assert info["key1"] == "value1"
assert info["key2"] == "value with spaces"
assert "comment" not in str(info.keys())
assert info["key3"] == "123"
print("PASS")
"""],
                capture_output=True, text=True,
            )
            assert "PASS" in result.stdout, f"Failed: {result.stderr}"
