"""Tests for cache_info_writer module."""

import os
import tempfile

from src.cache_info_writer import write_cache_info


class TestWriteCacheInfo:
    def test_writes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "cache_info.txt")
            write_cache_info(
                output_path=path,
                shot_name="test_shot",
                folder_name="test_shot_P1T1_v001",
                frame_start=1001,
                frame_end=1200,
                frame_inc=1,
                substeps=1,
                cache_format=".bgeo.sc",
                cache_node_path="/obj/geo1/filecache1",
                cache_output_pattern="Cache/test.$F4.bgeo.sc",
                hip_filename="test_shot.hip",
                houdini_version="21.0.631",
            )
            assert os.path.isfile(path)

    def test_contains_all_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "cache_info.txt")
            write_cache_info(
                output_path=path,
                shot_name="explosion",
                folder_name="explosion_P1T1_v001",
                frame_start=1001,
                frame_end=1200,
                frame_inc=1,
                substeps=2,
                cache_format=".vdb",
                cache_node_path="/obj/geo1/filecache1",
                cache_output_pattern="Cache/explosion.$F4.vdb",
                hip_filename="explosion.hip",
                houdini_version="21.0.631",
            )

            with open(path) as f:
                content = f.read()

            assert "shot_name=explosion" in content
            assert "startframe=1001" in content
            assert "endframe=1200" in content
            assert "framecount=200" in content
            assert "substeps=2" in content
            assert "cache_format=.vdb" in content
            assert "cache_node=/obj/geo1/filecache1" in content
            assert "hipfile=Scenes/explosion.hip" in content
            assert "houdini_version=21.0.631" in content
            assert "generated_at=" in content

    def test_frame_count_calculation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "cache_info.txt")
            write_cache_info(
                output_path=path,
                shot_name="test",
                folder_name="test_P1T1_v001",
                frame_start=1,
                frame_end=10,
                frame_inc=2,
                substeps=1,
                cache_format=".bgeo.sc",
                cache_node_path="/obj/geo1/fc",
                cache_output_pattern="Cache/test.$F4.bgeo.sc",
                hip_filename="test.hip",
            )

            with open(path) as f:
                content = f.read()
            assert "framecount=5" in content

    def test_newline_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "cache_info.txt")
            write_cache_info(
                output_path=path,
                shot_name="test",
                folder_name="test_P1T1_v001",
                frame_start=1,
                frame_end=10,
                frame_inc=1,
                substeps=1,
                cache_format=".bgeo.sc",
                cache_node_path="/obj/geo1/fc",
                cache_output_pattern="Cache/test.$F4.bgeo.sc",
                hip_filename="test.hip",
            )

            with open(path, "rb") as f:
                raw = f.read()
            assert b"\r\n" not in raw
