"""Tests for mantra_script_writer module (IFD-based)."""

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
                ifd_pattern="test_shot.%04d.ifd",
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
                ifd_pattern="test_shot.%04d.ifd",
                frame_start=1001,
                frame_end=1200,
            )
            st = os.stat(path)
            assert st.st_mode & stat.S_IEXEC

    def test_contains_mantra_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_mantra_script(
                output_path=path,
                shot_name="explosion",
                ifd_pattern="explosion.%04d.ifd",
                frame_start=1001,
                frame_end=1200,
            )

            with open(path) as f:
                content = f.read()

            assert "#!/bin/bash" in content
            assert "mantra -V 2a" in content
            assert "explosion.%04d.ifd" in content
            # IFD-based: no hbatch
            assert "hbatch" not in content

    def test_contains_frame_range(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_mantra_script(
                output_path=path,
                shot_name="test",
                ifd_pattern="test.%04d.ifd",
                frame_start=1001,
                frame_end=1200,
                frame_inc=2,
            )

            with open(path) as f:
                content = f.read()

            assert "1001" in content
            assert "1200" in content
            assert "seq 1001 2 1200" in content

    def test_contains_shot_info(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_mantra_script(
                output_path=path,
                shot_name="my_render",
                ifd_pattern="my_render.%04d.ifd",
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
                ifd_pattern="test.%04d.ifd",
                frame_start=1,
                frame_end=10,
            )

            with open(path, "rb") as f:
                raw = f.read()
            assert b"\r\n" not in raw

    def test_cd_ifds(self):
        """Verify the script cd's into IFDs/ before rendering."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_mantra_script(
                output_path=path,
                shot_name="test",
                ifd_pattern="test.%04d.ifd",
                frame_start=1,
                frame_end=10,
            )

            with open(path) as f:
                content = f.read()

            assert "cd IFDs" in content

    def test_contains_texture_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_mantra_script(
                output_path=path,
                shot_name="test",
                ifd_pattern="test.%04d.ifd",
                frame_start=1,
                frame_end=10,
            )

            with open(path) as f:
                content = f.read()

            assert "HOUDINI_TEXTURE_PATH" in content

    def test_ifd_pattern_in_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_mantra_script(
                output_path=path,
                shot_name="shot",
                ifd_pattern="shot.%04d.ifd",
                frame_start=1,
                frame_end=10,
            )

            with open(path) as f:
                content = f.read()

            assert "shot.%04d.ifd" in content


class TestWriteMantraBat:
    def test_bat_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_mantra_script(
                output_path=path,
                shot_name="test",
                ifd_pattern="test.%04d.ifd",
                frame_start=1,
                frame_end=10,
            )
            bat = os.path.join(tmpdir, "Scripts", "run_render.bat")
            assert os.path.isfile(bat)

    def test_bat_contains_mantra(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_render.sh")
            write_mantra_script(
                output_path=path,
                shot_name="test",
                ifd_pattern="test.%04d.ifd",
                frame_start=1001,
                frame_end=1200,
                hfs_path="C:\\Program Files\\Houdini",
            )
            bat = os.path.join(tmpdir, "Scripts", "run_render.bat")
            with open(bat) as f:
                content = f.read()
            assert "mantra" in content
            assert "for /L" in content
            assert "@echo off" in content
