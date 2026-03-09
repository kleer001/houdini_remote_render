"""Tests for cache_manifest module."""

import os
import tempfile

from src.cache_manifest import CacheManifestData, write_cache_manifest


class TestWriteCacheManifest:
    def test_writes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = CacheManifestData(
                shot_name="test_shot",
                folder_name="test_shot_P1T1_v001",
                houdini_version="21.0.631",
                generated_at="2026-03-09T14:00:00",
            )
            write_cache_manifest(path, data)
            assert os.path.isfile(path)

    def test_contains_shot_info(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = CacheManifestData(
                shot_name="explosion",
                folder_name="explosion_P1T1_v001",
                houdini_version="21.0.631",
                generated_at="2026-03-09T14:00:00",
            )
            write_cache_manifest(path, data)

            with open(path) as f:
                content = f.read()
            assert "explosion" in content
            assert "21.0.631" in content
            assert "Remote File Cache" in content

    def test_includes_frame_range(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = CacheManifestData(
                shot_name="test",
                frame_start=1001,
                frame_end=1200,
                frame_inc=1,
                substeps=2,
            )
            write_cache_manifest(path, data)

            with open(path) as f:
                content = f.read()
            assert "1001" in content
            assert "1200" in content
            assert "200" in content  # frame count

    def test_includes_cache_setup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = CacheManifestData(
                shot_name="test",
                cache_format=".vdb",
                cache_node_path="/obj/geo1/filecache1",
                cache_output_pattern="Cache/test.$F4.vdb",
            )
            write_cache_manifest(path, data)

            with open(path) as f:
                content = f.read()
            assert ".vdb" in content
            assert "/obj/geo1/filecache1" in content

    def test_includes_warnings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = CacheManifestData(
                shot_name="test",
                warnings=["Background save was forced off"],
            )
            write_cache_manifest(path, data)

            with open(path) as f:
                content = f.read()
            assert "Background save was forced off" in content

    def test_no_warnings_section_when_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = CacheManifestData(shot_name="test")
            write_cache_manifest(path, data)

            with open(path) as f:
                content = f.read()
            assert "Warnings" not in content

    def test_newline_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "manifest.txt")
            data = CacheManifestData(shot_name="test")
            write_cache_manifest(path, data)

            with open(path, "rb") as f:
                raw = f.read()
            assert b"\r\n" not in raw
