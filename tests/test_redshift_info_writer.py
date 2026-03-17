"""Tests for redshift_info_writer module."""

import os
import tempfile

from src.redshift_info_writer import write_redshift_info


class TestWriteRedshiftInfo:
    def test_writes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "render_info.txt")
            write_redshift_info(
                output_path=path,
                shot_name="test_shot",
                folder_name="test_shot_P1T1_v001",
                frame_start=1001,
                frame_end=1200,
                frame_inc=1,
                resolution=(1920, 1080),
                camera="/cameras/main",
                houdini_version="21.0.596",
            )
            assert os.path.isfile(path)

    def test_contains_all_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "render_info.txt")
            write_redshift_info(
                output_path=path,
                shot_name="explosion",
                folder_name="explosion_P1T1_v001",
                frame_start=1001,
                frame_end=1200,
                frame_inc=1,
                resolution=(1920, 1080),
                camera="/cameras/main",
                gpu_device="0",
                texture_cache_gb=8,
                ocio_config="/path/config.ocio",
                usd_file="explosion.usda",
                aov_count=5,
                houdini_version="21.0.596",
            )

            with open(path) as f:
                content = f.read()

            assert "shot_name=explosion" in content
            assert "renderer=redshift" in content
            assert "command=redshiftUsdCmdLine" in content
            assert "startframe=1001" in content
            assert "endframe=1200" in content
            assert "framecount=200" in content
            assert "resolution=1920x1080" in content
            assert "camera=/cameras/main" in content
            assert "gpu_device=0" in content
            assert "texture_cache_gb=8" in content
            assert "ocio_config=/path/config.ocio" in content
            assert "usd_file=explosion.usda" in content
            assert "aov_count=5" in content
            assert "houdini_version=21.0.596" in content
            assert "generated_at=" in content

    def test_frame_count_calculation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "render_info.txt")
            write_redshift_info(
                output_path=path,
                shot_name="test",
                folder_name="test_P1T1_v001",
                frame_start=1,
                frame_end=10,
                frame_inc=2,
                resolution=(1280, 720),
                camera="/cam",
            )

            with open(path) as f:
                content = f.read()
            assert "framecount=5" in content

    def test_optional_fields_absent(self):
        """Optional fields should not appear when not provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "render_info.txt")
            write_redshift_info(
                output_path=path,
                shot_name="test",
                folder_name="test_P1T1_v001",
                frame_start=1,
                frame_end=10,
                frame_inc=1,
                resolution=(1280, 720),
                camera="/cam",
            )

            with open(path) as f:
                content = f.read()
            assert "texture_cache_gb=" not in content
            assert "ocio_config=" not in content

    def test_newline_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "render_info.txt")
            write_redshift_info(
                output_path=path,
                shot_name="test",
                folder_name="test_P1T1_v001",
                frame_start=1,
                frame_end=10,
                frame_inc=1,
                resolution=(1280, 720),
                camera="/cam",
            )

            with open(path, "rb") as f:
                raw = f.read()
            assert b"\r\n" not in raw

    def test_default_gpu_device(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "render_info.txt")
            write_redshift_info(
                output_path=path,
                shot_name="test",
                folder_name="test_P1T1_v001",
                frame_start=1,
                frame_end=10,
                frame_inc=1,
                resolution=(1280, 720),
                camera="/cam",
            )

            with open(path) as f:
                content = f.read()
            assert "gpu_device=all" in content

    def test_no_hipfile_field(self):
        """USD-based packaging should not have a hipfile field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "render_info.txt")
            write_redshift_info(
                output_path=path,
                shot_name="test",
                folder_name="test_P1T1_v001",
                frame_start=1,
                frame_end=10,
                frame_inc=1,
                resolution=(1280, 720),
                camera="/cam",
            )

            with open(path) as f:
                content = f.read()
            assert "hipfile=" not in content
