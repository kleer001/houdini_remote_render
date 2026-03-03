"""Tests for platform_utils module."""

import os
import tempfile
import pytest

from src.platform_utils import normalize_path, path_join, ensure_dir, check_path_length


class TestNormalizePath:
    def test_forward_slashes(self):
        result = normalize_path("/tmp/foo/bar")
        assert "\\" not in result
        assert result.endswith("/tmp/foo/bar")

    def test_resolves_relative(self):
        result = normalize_path(".")
        assert os.path.isabs(result)


class TestPathJoin:
    def test_basic_join(self):
        result = path_join("/tmp", "foo", "bar")
        assert result == "/tmp/foo/bar"

    def test_forward_slashes(self):
        result = path_join("/some", "path", "here")
        assert "\\" not in result


class TestEnsureDir:
    def test_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "a", "b", "c")
            ensure_dir(target)
            assert os.path.isdir(target)

    def test_existing_dir_no_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ensure_dir(tmpdir)  # should not raise


class TestCheckPathLength:
    def test_short_path_ok(self):
        assert check_path_length("/tmp/foo") is None

    def test_long_path_warns(self):
        long_path = "/tmp/" + "a" * 250
        result = check_path_length(long_path)
        assert result is not None
        assert "exceeds" in result


@pytest.mark.houdini
class TestGetImaketxPath:
    def test_finds_imaketx(self):
        from src.platform_utils import get_imaketx_path
        path = get_imaketx_path()
        assert os.path.isfile(path)
        assert "imaketx" in os.path.basename(path)


@pytest.mark.houdini
class TestGetShotRootFromHip:
    def test_returns_grandparent(self):
        from src.platform_utils import get_shot_root_from_hip
        root = get_shot_root_from_hip()
        assert isinstance(root, str)
        assert "/" in root
