"""Tests for mantra_script_writer module."""

import os
import stat
import tempfile

from src.mantra_script_writer import write_mantra_script


class TestWriteMantraScript:
    def test_writes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_mantra_script(
                output_path=path,
                shot_name="test_shot",
                hip_filename="test_shot.hip",
                rop_node_path="/out/mantra1",
                frame_start=1001,
                frame_end=1200,
            )
            assert os.path.isfile(path)

    def test_is_executable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_mantra_script(
                output_path=path,
                shot_name="test_shot",
                hip_filename="test_shot.hip",
                rop_node_path="/out/mantra1",
                frame_start=1001,
                frame_end=1200,
            )
            st = os.stat(path)
            assert st.st_mode & stat.S_IEXEC

    def test_contains_hbatch_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_mantra_script(
                output_path=path,
                shot_name="explosion",
                hip_filename="explosion.hip",
                rop_node_path="/out/mantra1",
                frame_start=1001,
                frame_end=1200,
            )

            with open(path) as f:
                content = f.read()

            assert "#!/bin/bash" in content
            assert "hbatch" in content
            assert "explosion.hip" in content
            assert "/out/mantra1" in content
            assert "render" in content

    def test_contains_frame_range(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_mantra_script(
                output_path=path,
                shot_name="test",
                hip_filename="test.hip",
                rop_node_path="/out/mantra1",
                frame_start=1001,
                frame_end=1200,
                frame_inc=2,
            )

            with open(path) as f:
                content = f.read()

            assert "1001" in content
            assert "1200" in content
            assert "-f 1001 1200 -i 2" in content

    def test_contains_shot_info(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_mantra_script(
                output_path=path,
                shot_name="my_render",
                hip_filename="my_render.hip",
                rop_node_path="/out/mantra1",
                frame_start=1,
                frame_end=240,
            )

            with open(path) as f:
                content = f.read()

            assert "my_render" in content
            assert "1-240" in content

    def test_newline_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_mantra_script(
                output_path=path,
                shot_name="test",
                hip_filename="test.hip",
                rop_node_path="/out/mantra1",
                frame_start=1,
                frame_end=10,
            )

            with open(path, "rb") as f:
                raw = f.read()
            assert b"\r\n" not in raw

    def test_cd_scenes(self):
        """Verify the script cd's into Scenes/ before calling hbatch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_mantra_script(
                output_path=path,
                shot_name="test",
                hip_filename="test.hip",
                rop_node_path="/out/mantra1",
                frame_start=1,
                frame_end=10,
            )

            with open(path) as f:
                content = f.read()

            assert "cd Scenes" in content
