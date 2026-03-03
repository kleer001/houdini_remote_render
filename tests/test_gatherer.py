"""Tests for gatherer module."""

import os
import tempfile
import pytest

from src.gatherer import (
    gather_textures,
    gather_caches,
    make_cache_relative_path,
)


class TestGatherTextures:
    def test_copies_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source files
            src_dir = os.path.join(tmpdir, "source")
            os.makedirs(src_dir)
            src_file = os.path.join(src_dir, "diffuse.exr")
            with open(src_file, "w") as f:
                f.write("fake texture data")

            staging = os.path.join(tmpdir, "staging")
            path_map = gather_textures([src_file], staging)

            assert src_file in path_map
            dst = path_map[src_file]
            assert os.path.isfile(dst)
            assert "textures" in dst

    def test_creates_textures_subdir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = os.path.join(tmpdir, "test.exr")
            with open(src_file, "w") as f:
                f.write("data")

            staging = os.path.join(tmpdir, "staging")
            gather_textures([src_file], staging)
            assert os.path.isdir(os.path.join(staging, "textures"))


class TestGatherCaches:
    def test_copies_cache_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = os.path.join(tmpdir, "sim.0001.vdb")
            with open(src_file, "w") as f:
                f.write("fake vdb")

            cache_dir = os.path.join(tmpdir, "Cache")
            path_map = gather_caches([src_file], cache_dir)

            assert src_file in path_map
            assert os.path.isfile(path_map[src_file])

    def test_preserves_filename(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = os.path.join(tmpdir, "particle.0042.bgeo.sc")
            with open(src_file, "w") as f:
                f.write("data")

            cache_dir = os.path.join(tmpdir, "Cache")
            path_map = gather_caches([src_file], cache_dir)

            dst = path_map[src_file]
            assert os.path.basename(dst) == "particle.0042.bgeo.sc"


class TestMakeCacheRelativePath:
    def test_relative_to_scenes(self):
        cache = "/shot/Cache/sim.vdb"
        wrapper = "/shot/Scenes/shot_001.usda"
        result = make_cache_relative_path(cache, wrapper)
        assert result == "../Cache/sim.vdb"

    def test_same_directory(self):
        cache = "/shot/Scenes/inline.usd"
        wrapper = "/shot/Scenes/shot_001.usda"
        result = make_cache_relative_path(cache, wrapper)
        assert result == "inline.usd"
