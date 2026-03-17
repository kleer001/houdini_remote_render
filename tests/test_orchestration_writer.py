"""Tests for orchestration_writer module."""

import os
import stat
import tempfile

from src.orchestration_writer import write_orchestration_script


class TestWriteOrchestrationScript:

    def test_writes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_all.sh")
            write_orchestration_script(
                output_path=path,
                shot_name="test",
                cache_scripts=[("fluid", "run_cache_001_fluid.sh")],
            )
            assert os.path.isfile(path)

    def test_is_executable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_all.sh")
            write_orchestration_script(
                output_path=path,
                shot_name="test",
                cache_scripts=[("fluid", "run_cache_001_fluid.sh")],
            )
            assert os.stat(path).st_mode & stat.S_IEXEC

    def test_contains_all_cache_steps(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_all.sh")
            write_orchestration_script(
                output_path=path,
                shot_name="sim_shot",
                cache_scripts=[
                    ("fluid", "run_cache_001_fluid.sh"),
                    ("mesh", "run_cache_002_mesh.sh"),
                ],
            )
            with open(path) as f:
                content = f.read()
            assert "run_cache_001_fluid.sh" in content
            assert "run_cache_002_mesh.sh" in content
            assert "Cache: fluid" in content
            assert "Cache: mesh" in content

    def test_render_is_last_step(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_all.sh")
            write_orchestration_script(
                output_path=path,
                shot_name="test",
                cache_scripts=[("fluid", "run_cache_001_fluid.sh")],
                render_script_filename="run_render.sh",
            )
            with open(path) as f:
                content = f.read()
            # Render should be step 2/2 (1 cache + 1 render)
            assert "[2/2] Render" in content
            assert "run_render.sh" in content

    def test_step_numbering(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_all.sh")
            write_orchestration_script(
                output_path=path,
                shot_name="test",
                cache_scripts=[
                    ("a", "run_cache_001_a.sh"),
                    ("b", "run_cache_002_b.sh"),
                    ("c", "run_cache_003_c.sh"),
                ],
            )
            with open(path) as f:
                content = f.read()
            assert "[1/4] Cache: a" in content
            assert "[2/4] Cache: b" in content
            assert "[3/4] Cache: c" in content
            assert "[4/4] Render" in content

    def test_hfs_sourcing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_all.sh")
            write_orchestration_script(
                output_path=path,
                shot_name="test",
                cache_scripts=[("x", "run_cache_001_x.sh")],
                hfs_path="/opt/hfs21.0",
            )
            with open(path) as f:
                content = f.read()
            assert "houdini_setup_bash" in content
            assert "/opt/hfs21.0" in content

    def test_set_e(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_all.sh")
            write_orchestration_script(
                output_path=path,
                shot_name="test",
                cache_scripts=[],
            )
            with open(path) as f:
                content = f.read()
            assert "set -e" in content

    def test_newline_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_all.sh")
            write_orchestration_script(
                output_path=path,
                shot_name="test",
                cache_scripts=[("x", "run_cache_001_x.sh")],
            )
            with open(path, "rb") as f:
                raw = f.read()
            assert b"\r\n" not in raw

    def test_shot_name_in_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_all.sh")
            write_orchestration_script(
                output_path=path,
                shot_name="my_explosion",
                cache_scripts=[("debris", "run_cache_001_debris.sh")],
            )
            with open(path) as f:
                content = f.read()
            assert "my_explosion" in content


class TestPythonLauncherCopied:
    def test_run_all_py_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_all.sh")
            write_orchestration_script(
                output_path=path,
                shot_name="test",
                cache_scripts=[("sim", "run_cache_001_sim.sh")],
            )
            py = os.path.join(tmpdir, "Scripts", "run_all.py")
            assert os.path.isfile(py)
