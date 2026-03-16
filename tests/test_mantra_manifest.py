"""Tests for mantra_manifest module."""

import os
import tempfile

from src.mantra_manifest import MantraManifestData, write_mantra_manifest


class TestWriteMantraManifest:
    def test_writes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = MantraManifestData(
                shot_name="test_shot",
                folder_name="test_shot_P1T1_v001",
                houdini_version="21.0.631",
                generated_at="2026-03-16T14:00:00",
            )
            write_mantra_manifest(path, data)
            assert os.path.isfile(path)

    def test_contains_shot_info(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = MantraManifestData(
                shot_name="explosion",
                folder_name="explosion_P1T1_v001",
                houdini_version="21.0.631",
                generated_at="2026-03-16T14:00:00",
            )
            write_mantra_manifest(path, data)

            with open(path) as f:
                content = f.read()
            assert "explosion" in content
            assert "21.0.631" in content
            assert "Remote Mantra Render" in content

    def test_includes_frame_range(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = MantraManifestData(
                shot_name="test",
                frame_start=1001,
                frame_end=1200,
                frame_inc=1,
            )
            write_mantra_manifest(path, data)

            with open(path) as f:
                content = f.read()
            assert "1001" in content
            assert "1200" in content
            assert "200" in content  # frame count

    def test_includes_render_setup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = MantraManifestData(
                shot_name="test",
                render_engine="pbr",
                resolution=(1920, 1080),
                pixel_samples=(4, 4),
                camera="/obj/cam1",
                aov_count=3,
                rop_node_path="/out/mantra1",
                output_picture="Output/test.$F4.exr",
            )
            write_mantra_manifest(path, data)

            with open(path) as f:
                content = f.read()
            assert "pbr" in content
            assert "1920x1080" in content
            assert "4x4" in content
            assert "/obj/cam1" in content
            assert "/out/mantra1" in content

    def test_includes_warnings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = MantraManifestData(
                shot_name="test",
                warnings=["No camera assigned"],
            )
            write_mantra_manifest(path, data)

            with open(path) as f:
                content = f.read()
            assert "No camera assigned" in content

    def test_no_warnings_section_when_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = MantraManifestData(shot_name="test")
            write_mantra_manifest(path, data)

            with open(path) as f:
                content = f.read()
            assert "Warnings" not in content

    def test_newline_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = MantraManifestData(shot_name="test")
            write_mantra_manifest(path, data)

            with open(path, "rb") as f:
                raw = f.read()
            assert b"\r\n" not in raw
