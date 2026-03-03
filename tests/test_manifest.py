"""Tests for manifest module."""

import os
import tempfile

from src.manifest import ManifestData, write_manifest


class TestWriteManifest:
    def test_writes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = ManifestData(
                shot_name="test_shot",
                houdini_version="21.0.631",
                generated_at="2026-03-03T12:00:00",
                usdz_path="Scenes/test_shot.usdz",
                wrapper_path="Scenes/test_shot.usda",
            )
            write_manifest(path, data)
            assert os.path.isfile(path)

    def test_contains_shot_info(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = ManifestData(
                shot_name="hero_shot",
                houdini_version="21.0.631",
                generated_at="2026-03-03T12:00:00",
            )
            write_manifest(path, data)

            with open(path) as f:
                content = f.read()
            assert "hero_shot" in content
            assert "21.0.631" in content

    def test_includes_textures(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = ManifestData(
                shot_name="test",
                textures_converted=[("/old/tex.png", "/new/tex.exr")],
                textures_skipped=["/skip/tex.rat"],
            )
            write_manifest(path, data)

            with open(path) as f:
                content = f.read()
            assert "tex.png" in content
            assert "tex.exr" in content
            assert "tex.rat" in content
            assert "Skipped" in content

    def test_includes_warnings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = ManifestData(
                shot_name="test",
                warnings=["High instance count"],
            )
            write_manifest(path, data)

            with open(path) as f:
                content = f.read()
            assert "High instance count" in content

    def test_newline_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = ManifestData(shot_name="test")
            write_manifest(path, data)

            with open(path, "rb") as f:
                raw = f.read()
            # Should use \n, not \r\n
            assert b"\r\n" not in raw
