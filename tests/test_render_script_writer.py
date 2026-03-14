"""Tests for render_script_writer module."""

import os
import stat
import tempfile

from src.render_script_writer import write_render_script


class TestWriteRenderScript:
    def test_writes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_render_script(
                output_path=path,
                shot_name="test_shot",
                wrapper_filename="test_shot.usda",
                frame_start=1,
                frame_end=1,
            )
            assert os.path.isfile(path)

    def test_is_executable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_render_script(
                output_path=path,
                shot_name="test_shot",
                wrapper_filename="test_shot.usda",
                frame_start=1,
                frame_end=1,
            )
            st = os.stat(path)
            assert st.st_mode & stat.S_IEXEC

    def test_contains_husk_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_render_script(
                output_path=path,
                shot_name="explosion",
                wrapper_filename="explosion.usda",
                frame_start=1001,
                frame_end=1100,
            )
            with open(path) as f:
                content = f.read()

            assert "#!/bin/bash" in content
            assert "husk" in content
            assert "cd Scenes" in content
            assert '"explosion.usda"' in content
            assert "-f 1001" in content
            assert "-n 100" in content
            assert "--renderer BRAY_HdKarma" in content

    def test_smart_defaults_sequence(self):
        """Sequences auto-add --restart-delegate 1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_render_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=100,
            )
            with open(path) as f:
                content = f.read()
            assert "--restart-delegate 1" in content

    def test_smart_defaults_single_frame(self):
        """Single frame does NOT auto-add --restart-delegate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_render_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=1,
            )
            with open(path) as f:
                content = f.read()
            assert "--restart-delegate" not in content

    def test_always_includes_make_output_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_render_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=1,
            )
            with open(path) as f:
                content = f.read()
            assert "--make-output-path" in content

    def test_always_includes_headlight_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_render_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=1,
            )
            with open(path) as f:
                content = f.read()
            assert "--headlight none" in content

    def test_engine_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_render_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=1,
                engine="xpu",
            )
            with open(path) as f:
                content = f.read()
            assert "--engine xpu" in content

    def test_exr_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_render_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=1,
                exr_mode=0,
            )
            with open(path) as f:
                content = f.read()
            assert "--exrmode 0" in content

    def test_autotile(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_render_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=1,
                autotile=True,
            )
            with open(path) as f:
                content = f.read()
            assert "--autotile" in content

    def test_timelimit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_render_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=1,
                timelimit=3600.0,
            )
            with open(path) as f:
                content = f.read()
            assert "--timelimit 3600.0" in content

    def test_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_render_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=1,
                snapshot=30.0,
            )
            with open(path) as f:
                content = f.read()
            assert "--snapshot 30.0" in content

    def test_oiio_mem_pct(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_render_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=1,
                oiio_mem_pct=50,
            )
            with open(path) as f:
                content = f.read()
            assert "--oiio-max-memory-percent 50" in content

    def test_extra_flags(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_render_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=1,
                extra_flags=["--verbose", "--custom-flag value"],
            )
            with open(path) as f:
                content = f.read()
            assert "--verbose" in content
            assert "--custom-flag value" in content

    def test_newline_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_render_script(
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
            write_render_script(
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

    def test_hfs_path_sources_environment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_render_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=1,
                hfs_path="/opt/hfs21.0",
            )
            with open(path) as f:
                content = f.read()
            assert "/opt/hfs21.0" in content
            assert "houdini_setup_bash" in content

    def test_no_hfs_path_includes_fallback_comment(self):
        """When HFS not detected, script notes husk must be on PATH."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            # Clear HFS from env for this test
            old_hfs = os.environ.pop("HFS", None)
            try:
                write_render_script(
                    output_path=path,
                    shot_name="test",
                    wrapper_filename="test.usda",
                    frame_start=1,
                    frame_end=1,
                )
            finally:
                if old_hfs is not None:
                    os.environ["HFS"] = old_hfs
            with open(path) as f:
                content = f.read()
            assert "husk must be on PATH" in content

    def test_explicit_restart_delegate_overrides_smart_default(self):
        """Explicit restart_delegate=5 overrides auto-1 for sequences."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_render_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=100,
                restart_delegate=5,
            )
            with open(path) as f:
                content = f.read()
            assert "--restart-delegate 5" in content
            assert "--restart-delegate 1" not in content

    def test_explicit_restart_delegate_zero_disables(self):
        """Explicit restart_delegate=0 suppresses auto-add for sequences."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_render_script(
                output_path=path,
                shot_name="test",
                wrapper_filename="test.usda",
                frame_start=1,
                frame_end=100,
                restart_delegate=0,
            )
            with open(path) as f:
                content = f.read()
            assert "--restart-delegate 0" in content
            assert "--restart-delegate 1" not in content
