"""Tests for platform_utils module."""

import os
import tempfile
import pytest

from src.platform_utils import normalize_path, path_join, ensure_dir, check_disk_space


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

    def test_creates_placeholder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "newdir")
            ensure_dir(target)
            assert os.path.isfile(os.path.join(target, ".placeholder"))


class TestCheckDiskSpace:
    def test_returns_three_ints(self):
        total, used, free = check_disk_space("/tmp")
        assert isinstance(total, int)
        assert isinstance(used, int)
        assert isinstance(free, int)

    def test_values_are_positive(self):
        total, used, free = check_disk_space("/tmp")
        assert total > 0
        assert used > 0
        assert free > 0

    def test_total_equals_used_plus_free(self):
        total, used, free = check_disk_space("/tmp")
        assert total == used + free


class TestDetectRedshift:
    def test_returns_none_when_unset(self, monkeypatch):
        monkeypatch.delenv("REDSHIFT_COREDATAPATH", raising=False)
        from src.platform_utils import detect_redshift
        # Result depends on whether /usr/redshift or /opt/redshift exist
        result = detect_redshift()
        assert result is None or os.path.isdir(result)

    def test_returns_path_when_set(self, monkeypatch, tmp_path):
        monkeypatch.setenv("REDSHIFT_COREDATAPATH", str(tmp_path))
        from src.platform_utils import detect_redshift
        assert detect_redshift() == str(tmp_path)

    def test_returns_none_for_nonexistent_path(self, monkeypatch):
        monkeypatch.setenv("REDSHIFT_COREDATAPATH", "/nonexistent/path")
        from src.platform_utils import detect_redshift
        result = detect_redshift()
        # Falls back to common paths, which may or may not exist
        if result is not None:
            assert os.path.isdir(result)


class TestRedshiftEnvBlock:
    def test_with_path(self):
        from src.platform_utils import redshift_env_block
        block = redshift_env_block("/usr/redshift")
        assert "REDSHIFT_COREDATAPATH" in block
        assert "/usr/redshift" in block
        assert "LD_LIBRARY_PATH" in block
        assert "redshift_LICENSE" in block

    def test_without_path(self):
        from src.platform_utils import redshift_env_block
        block = redshift_env_block(None)
        assert "not known at packaging time" in block


class TestCopyLauncher:
    def test_copies_run_render(self, tmp_path):
        from src.platform_utils import copy_launcher
        dest = copy_launcher("run_render.py", str(tmp_path))
        assert os.path.isfile(dest)
        with open(dest) as f:
            assert "render_info.txt" in f.read()

    def test_copies_run_cache(self, tmp_path):
        from src.platform_utils import copy_launcher
        dest = copy_launcher("run_cache.py", str(tmp_path))
        assert os.path.isfile(dest)

    def test_copies_run_all(self, tmp_path):
        from src.platform_utils import copy_launcher
        dest = copy_launcher("run_all.py", str(tmp_path))
        assert os.path.isfile(dest)

    def test_nonexistent_launcher_raises(self, tmp_path):
        from src.platform_utils import copy_launcher
        with pytest.raises(FileNotFoundError):
            copy_launcher("does_not_exist.py", str(tmp_path))


@pytest.mark.houdini
class TestGetImaketxPath:
    def test_finds_imaketx(self):
        from src.platform_utils import get_imaketx_path
        path = get_imaketx_path()
        assert os.path.isfile(path)
        assert "imaketx" in os.path.basename(path)


@pytest.mark.houdini
class TestGetHipDir:
    def test_returns_hip_directory(self):
        from src.platform_utils import get_hip_dir
        hip_dir = get_hip_dir()
        assert isinstance(hip_dir, str)
        assert "/" in hip_dir
