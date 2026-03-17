"""Tests for redshift_script_writer module."""

import os
import stat
import tempfile

from src.redshift_script_writer import write_redshift_script


class TestWriteRedshiftScript:
    def test_writes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_redshift_script(
                output_path=path,
                shot_name="test_shot",
                wrapper_filename="test_shot.usda",
                frame_start=1001,
                frame_end=1200,
            )
            assert os.path.isfile(path)

    def test_is_executable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_redshift_script(
                output_path=path,
                shot_name="test_shot",
                wrapper_filename="test_shot.usda",
                frame_start=1001,
                frame_end=1200,
            )
            st = os.stat(path)
            assert st.st_mode & stat.S_IEXEC

    def test_contains_redshift_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_redshift_script(
                output_path=path,
                shot_name="explosion",
                wrapper_filename="explosion.usda",
                frame_start=1001,
                frame_end=1200,
            )

            with open(path) as f:
                content = f.read()

            assert "#!/bin/bash" in content
            assert "redshiftUsdCmdLine" in content
            assert "explosion.usda" in content
            # Should NOT use husk or mantra
            assert "husk" not in content
            assert "mantra" not in content
            assert "hbatch" not in content

    def test_frame_range_flags(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_redshift_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1001,
                frame_end=1200,
                frame_inc=2,
            )

            with open(path) as f:
                content = f.read()

            assert "-f 1001" in content
            # 1001 to 1200 inc 2 = 100 frames
            assert "-n 100" in content
            assert "-i 2" in content

    def test_frame_count_calculation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_redshift_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=10,
                frame_inc=1,
            )

            with open(path) as f:
                content = f.read()

            assert "-f 1" in content
            assert "-n 10" in content
            # frame_inc=1 is default, should not appear as -i flag
            assert "-i 1" not in content

    def test_gpu_device_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_redshift_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=10,
                gpu_device="0",
            )

            with open(path) as f:
                content = f.read()

            assert "-device 0" in content

    def test_default_gpu_all(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_redshift_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=10,
            )

            with open(path) as f:
                content = f.read()

            assert "-device all" in content

    def test_texture_cache_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_redshift_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=10,
                texture_cache_gb=8,
            )

            with open(path) as f:
                content = f.read()

            assert "-texturecachebudget 8" in content

    def test_skip_postfx_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_redshift_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=10,
                skip_postfx=True,
            )

            with open(path) as f:
                content = f.read()

            assert "-skippostfx" in content

    def test_no_skip_postfx_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_redshift_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=10,
            )

            with open(path) as f:
                content = f.read()

            assert "-skippostfx" not in content

    def test_ocio_config_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_redshift_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=10,
                ocio_config="/path/to/config.ocio",
            )

            with open(path) as f:
                content = f.read()

            assert "-ocioconfig" in content
            assert "/path/to/config.ocio" in content

    def test_restart_delegate_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_redshift_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=10,
                restart_delegate=True,
            )

            with open(path) as f:
                content = f.read()

            assert "-restart-delegate" in content

    def test_cd_scenes(self):
        """Script must cd into Scenes/ so productName paths resolve correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_redshift_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=10,
            )

            with open(path) as f:
                content = f.read()

            assert "cd Scenes" in content

    def test_mkdir_output(self):
        """Script must mkdir -p ../Output since redshiftUsdCmdLine won't."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_redshift_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=10,
            )

            with open(path) as f:
                content = f.read()

            assert "mkdir -p ../Output" in content

    def test_redshift_env_block(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_redshift_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=10,
                redshift_path="/usr/redshift",
            )

            with open(path) as f:
                content = f.read()

            assert "REDSHIFT_COREDATAPATH" in content
            assert "/usr/redshift" in content

    def test_newline_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_redshift_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=10,
            )

            with open(path, "rb") as f:
                raw = f.read()
            assert b"\r\n" not in raw

    def test_contains_shot_info(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_redshift_script(
                output_path=path,
                shot_name="my_render",
                wrapper_filename="my_render.usda",
                frame_start=1,
                frame_end=240,
            )

            with open(path) as f:
                content = f.read()

            assert "my_render" in content
            assert "1-240" in content

    def test_extra_flags(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_redshift_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=10,
                extra_flags=["-crop 0 0 960 540", "-hybrid 1"],
            )

            with open(path) as f:
                content = f.read()

            assert "-crop 0 0 960 540" in content
            assert "-hybrid 1" in content

    def test_verbose_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_redshift_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=10,
                verbose=5,
            )

            with open(path) as f:
                content = f.read()

            assert "-V 5" in content

    def test_default_verbose_not_in_flags(self):
        """Default verbose=2 should not add -V flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_redshift_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=10,
            )

            with open(path) as f:
                content = f.read()

            assert "-V " not in content


class TestPythonLauncherCopied:
    def test_run_render_py_created_alongside_sh(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_redshift_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=10,
            )
            py = os.path.join(tmpdir, "Scripts", "run_render.py")
            assert os.path.isfile(py)

    def test_launcher_is_standalone(self):
        """The launcher should not import from src/."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_redshift_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=10,
            )
            py = os.path.join(tmpdir, "Scripts", "run_render.py")
            with open(py) as f:
                content = f.read()
            assert "from src" not in content
            assert "import src" not in content
