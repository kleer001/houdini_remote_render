"""Tests for install.py."""

import json
import os
import stat
import tempfile

from install import (
    build_package_json,
    check_status,
    get_repo_root,
    install,
    uninstall,
    PACKAGE_FILENAME,
)
from pathlib import Path


class TestBuildPackageJson:
    def test_has_otlscan_path(self):
        repo = Path("/fake/repo")
        data = build_package_json(repo)
        env = data["env"][0]
        assert "HOUDINI_OTLSCAN_PATH" in env
        assert env["HOUDINI_OTLSCAN_PATH"]["value"] == "/fake/repo/src/hda"
        assert env["HOUDINI_OTLSCAN_PATH"]["method"] == "append"

    def test_has_path(self):
        repo = Path("/fake/repo")
        data = build_package_json(repo)
        assert data["path"] == "/fake/repo"

    def test_uses_posix_paths(self):
        repo = Path("/some/path/with/dirs")
        data = build_package_json(repo)
        assert "\\" not in data["path"]
        assert "\\" not in data["env"][0]["HOUDINI_OTLSCAN_PATH"]["value"]


class TestInstallUninstall:
    def test_install_returns_success_tuple(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pref_dir = Path(tmpdir)
            success, msg = install(pref_dir, Path("/fake/repo"))
            assert success is True
            assert PACKAGE_FILENAME in msg

    def test_install_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pref_dir = Path(tmpdir)
            install(pref_dir, Path("/fake/repo"))

            package_file = pref_dir / "packages" / PACKAGE_FILENAME
            assert package_file.exists()

    def test_install_creates_packages_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pref_dir = Path(tmpdir)
            install(pref_dir, Path("/fake/repo"))

            assert (pref_dir / "packages").is_dir()

    def test_install_writes_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pref_dir = Path(tmpdir)
            install(pref_dir, Path("/fake/repo"))

            package_file = pref_dir / "packages" / PACKAGE_FILENAME
            with open(package_file) as f:
                data = json.load(f)
            assert data["env"][0]["HOUDINI_OTLSCAN_PATH"]["value"] == "/fake/repo/src/hda"

    def test_install_uses_unix_newlines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pref_dir = Path(tmpdir)
            install(pref_dir, Path("/fake/repo"))

            package_file = pref_dir / "packages" / PACKAGE_FILENAME
            with open(package_file, "rb") as f:
                raw = f.read()
            assert b"\r\n" not in raw

    def test_install_returns_failure_on_permission_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pref_dir = Path(tmpdir)
            # Make the directory read-only so mkdir/write fails
            os.chmod(tmpdir, stat.S_IRUSR | stat.S_IXUSR)
            try:
                success, msg = install(pref_dir, Path("/fake/repo"))
                assert success is False
                assert "Failed" in msg
            finally:
                os.chmod(tmpdir, stat.S_IRWXU)

    def test_uninstall_removes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pref_dir = Path(tmpdir)
            install(pref_dir, Path("/fake/repo"))
            success, msg = uninstall(pref_dir)
            assert success is True

            package_file = pref_dir / "packages" / PACKAGE_FILENAME
            assert not package_file.exists()

    def test_uninstall_returns_false_if_not_installed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pref_dir = Path(tmpdir)
            success, msg = uninstall(pref_dir)
            assert success is False
            assert "Not installed" in msg

    def test_reinstall_overwrites(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pref_dir = Path(tmpdir)
            install(pref_dir, Path("/old/repo"))
            install(pref_dir, Path("/new/repo"))

            package_file = pref_dir / "packages" / PACKAGE_FILENAME
            with open(package_file) as f:
                data = json.load(f)
            assert data["env"][0]["HOUDINI_OTLSCAN_PATH"]["value"] == "/new/repo/src/hda"


class TestCheckStatus:
    def test_not_installed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            status = check_status(Path(tmpdir))
            assert status["installed"] is False
            assert status["hda_dir"] is None

    def test_installed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pref_dir = Path(tmpdir)
            install(pref_dir, Path("/my/repo"))

            status = check_status(pref_dir)
            assert status["installed"] is True
            assert status["hda_dir"] == "/my/repo/src/hda"

    def test_corrupt_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pref_dir = Path(tmpdir)
            packages_dir = pref_dir / "packages"
            packages_dir.mkdir()
            package_file = packages_dir / PACKAGE_FILENAME
            package_file.write_text("not valid json")

            status = check_status(pref_dir)
            assert status["installed"] is True
            assert status["hda_dir"] is None


class TestGetRepoRoot:
    def test_returns_parent_of_install_py(self):
        root = get_repo_root()
        assert (root / "install.py").exists()
        assert (root / "src" / "hda").is_dir()
