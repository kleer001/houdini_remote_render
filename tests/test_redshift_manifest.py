"""Tests for redshift_manifest module."""

import os
import tempfile

from src.redshift_manifest import RedshiftManifestData, write_redshift_manifest


class TestWriteRedshiftManifest:
    def test_writes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = RedshiftManifestData(
                shot_name="test_shot",
                folder_name="test_shot_P1T1_v001",
                houdini_version="21.0.596",
                generated_at="2026-03-16T14:00:00",
            )
            write_redshift_manifest(path, data)
            assert os.path.isfile(path)

    def test_contains_shot_info(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = RedshiftManifestData(
                shot_name="explosion",
                folder_name="explosion_P1T1_v001",
                houdini_version="21.0.596",
                generated_at="2026-03-16T14:00:00",
            )
            write_redshift_manifest(path, data)

            with open(path) as f:
                content = f.read()
            assert "explosion" in content
            assert "21.0.596" in content
            assert "Remote Redshift Render" in content

    def test_includes_frame_range(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = RedshiftManifestData(
                shot_name="test",
                frame_start=1001,
                frame_end=1200,
                frame_inc=1,
            )
            write_redshift_manifest(path, data)

            with open(path) as f:
                content = f.read()
            assert "1001" in content
            assert "1200" in content
            assert "200" in content  # frame count

    def test_includes_render_setup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = RedshiftManifestData(
                shot_name="test",
                resolution=(1920, 1080),
                camera="/cameras/main",
                aov_count=3,
                gpu_device="0",
            )
            write_redshift_manifest(path, data)

            with open(path) as f:
                content = f.read()
            assert "Redshift" in content
            assert "redshiftUsdCmdLine" in content
            assert "1920x1080" in content
            assert "/cameras/main" in content
            assert "GPU Device" in content

    def test_includes_usd_section(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = RedshiftManifestData(
                shot_name="test",
                usdz_size_mb=125.5,
                wrapper_path="Scenes/test.usda",
            )
            write_redshift_manifest(path, data)

            with open(path) as f:
                content = f.read()
            assert "USD Package" in content
            assert "125.50" in content
            assert "test.usda" in content

    def test_includes_texture_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = RedshiftManifestData(
                shot_name="test",
                texture_cache_gb=8,
            )
            write_redshift_manifest(path, data)

            with open(path) as f:
                content = f.read()
            assert "8 GB" in content

    def test_no_texture_cache_when_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = RedshiftManifestData(shot_name="test")
            write_redshift_manifest(path, data)

            with open(path) as f:
                content = f.read()
            assert "Tex Cache" not in content

    def test_includes_ocio(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = RedshiftManifestData(
                shot_name="test",
                ocio_config="/path/to/config.ocio",
            )
            write_redshift_manifest(path, data)

            with open(path) as f:
                content = f.read()
            assert "OCIO" in content
            assert "/path/to/config.ocio" in content

    def test_includes_warnings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = RedshiftManifestData(
                shot_name="test",
                warnings=["UsdPreviewSurface materials found"],
            )
            write_redshift_manifest(path, data)

            with open(path) as f:
                content = f.read()
            assert "UsdPreviewSurface" in content

    def test_no_warnings_section_when_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = RedshiftManifestData(shot_name="test")
            write_redshift_manifest(path, data)

            with open(path) as f:
                content = f.read()
            assert "Warnings" not in content

    def test_newline_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = RedshiftManifestData(shot_name="test")
            write_redshift_manifest(path, data)

            with open(path, "rb") as f:
                raw = f.read()
            assert b"\r\n" not in raw

    def test_no_ifd_fields(self):
        """USD-based packaging should not have IFD sections."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = RedshiftManifestData(shot_name="test")
            write_redshift_manifest(path, data)

            with open(path) as f:
                content = f.read()
            assert "IFD" not in content
            assert "ifd" not in content
