"""Tests for mantra_info_writer module (IFD-based)."""

import os
import tempfile

from src.mantra_info_writer import write_mantra_info


class TestWriteMantraInfo:
    def test_writes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "render_info.txt")
            write_mantra_info(
                output_path=path,
                shot_name="test_shot",
                folder_name="test_shot_P1T1_v001",
                frame_start=1001,
                frame_end=1200,
                frame_inc=1,
                resolution=(1920, 1080),
                pixel_samples=(3, 3),
                render_engine="micropoly",
                camera="/obj/cam1",
                rop_node_path="/out/mantra1",
                output_picture="Output/test.$F4.exr",
                ifd_count=200,
                ifd_pattern="test_shot.%04d.ifd",
                houdini_version="21.0.631",
            )
            assert os.path.isfile(path)

    def test_contains_all_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "render_info.txt")
            write_mantra_info(
                output_path=path,
                shot_name="explosion",
                folder_name="explosion_P1T1_v001",
                frame_start=1001,
                frame_end=1200,
                frame_inc=1,
                resolution=(1920, 1080),
                pixel_samples=(4, 4),
                render_engine="pbr",
                camera="/obj/cam1",
                rop_node_path="/out/mantra1",
                output_picture="Output/explosion.$F4.exr",
                ifd_count=200,
                ifd_pattern="explosion.%04d.ifd",
                texture_count=5,
                textures_size_mb=12.5,
                houdini_version="21.0.631",
            )

            with open(path) as f:
                content = f.read()

            assert "shot_name=explosion" in content
            assert "renderer=mantra" in content
            assert "method=ifd" in content
            assert "render_engine=pbr" in content
            assert "startframe=1001" in content
            assert "endframe=1200" in content
            assert "framecount=200" in content
            assert "resolution=1920x1080" in content
            assert "pixel_samples=4x4" in content
            assert "camera=/obj/cam1" in content
            assert "rop_node=/out/mantra1" in content
            assert "ifd_count=200" in content
            assert "ifd_pattern=explosion.%04d.ifd" in content
            assert "texture_count=5" in content
            assert "textures_size_mb=12.50" in content
            assert "houdini_version=21.0.631" in content
            assert "generated_at=" in content

    def test_frame_count_calculation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "render_info.txt")
            write_mantra_info(
                output_path=path,
                shot_name="test",
                folder_name="test_P1T1_v001",
                frame_start=1,
                frame_end=10,
                frame_inc=2,
                resolution=(1280, 720),
                pixel_samples=(3, 3),
                render_engine="micropoly",
                camera="/obj/cam1",
                rop_node_path="/out/mantra1",
                output_picture="Output/test.$F4.exr",
                ifd_count=5,
                ifd_pattern="test.%04d.ifd",
            )

            with open(path) as f:
                content = f.read()
            assert "framecount=5" in content

    def test_no_hipfile_field(self):
        """IFD-based packaging should not have a hipfile field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "render_info.txt")
            write_mantra_info(
                output_path=path,
                shot_name="test",
                folder_name="test_P1T1_v001",
                frame_start=1,
                frame_end=10,
                frame_inc=1,
                resolution=(1280, 720),
                pixel_samples=(3, 3),
                render_engine="micropoly",
                camera="/obj/cam1",
                rop_node_path="/out/mantra1",
                output_picture="Output/test.$F4.exr",
                ifd_count=10,
                ifd_pattern="test.%04d.ifd",
            )

            with open(path) as f:
                content = f.read()
            assert "hipfile=" not in content

    def test_newline_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "render_info.txt")
            write_mantra_info(
                output_path=path,
                shot_name="test",
                folder_name="test_P1T1_v001",
                frame_start=1,
                frame_end=10,
                frame_inc=1,
                resolution=(1280, 720),
                pixel_samples=(3, 3),
                render_engine="micropoly",
                camera="/obj/cam1",
                rop_node_path="/out/mantra1",
                output_picture="Output/test.$F4.exr",
                ifd_count=10,
                ifd_pattern="test.%04d.ifd",
            )

            with open(path, "rb") as f:
                raw = f.read()
            assert b"\r\n" not in raw
