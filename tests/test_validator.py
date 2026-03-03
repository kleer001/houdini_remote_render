"""Tests for validator module."""

import os
import tempfile
import pytest

from src.validator import validate_shot_name, validate_shot_structure


class TestValidateShotName:
    def test_valid_name(self):
        ok, msg = validate_shot_name("shot_001")
        assert ok is True
        assert msg == ""

    def test_empty_name(self):
        ok, msg = validate_shot_name("")
        assert ok is False
        assert "empty" in msg.lower()

    def test_default_placeholder(self):
        ok, msg = validate_shot_name("SHOT_NAME_HERE")
        assert ok is False
        assert "placeholder" in msg.lower()

    def test_illegal_chars(self):
        for char in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
            ok, msg = validate_shot_name(f"shot{char}001")
            assert ok is False, f"Should reject '{char}'"
            assert "illegal" in msg.lower()

    def test_whitespace_only(self):
        ok, msg = validate_shot_name("   ")
        assert ok is False


class TestValidateShotStructure:
    def test_all_dirs_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for d in ("Output", "Textures", "Cache", "Scenes", "Scripts"):
                os.makedirs(os.path.join(tmpdir, d))
            ok, msg = validate_shot_structure(tmpdir)
            assert ok is True

    def test_creates_placeholders(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for d in ("Output", "Textures", "Cache", "Scenes", "Scripts"):
                os.makedirs(os.path.join(tmpdir, d))
            validate_shot_structure(tmpdir)
            for d in ("Output", "Textures", "Cache", "Scenes", "Scripts"):
                assert os.path.isfile(os.path.join(tmpdir, d, ".placeholder"))

    def test_missing_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ok, msg = validate_shot_structure(tmpdir)
            assert ok is False
            assert "Missing" in msg

    def test_nonexistent_root(self):
        ok, msg = validate_shot_structure("/nonexistent/path/xyz")
        assert ok is False
        assert "does not exist" in msg

    def test_partial_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "Output"))
            os.makedirs(os.path.join(tmpdir, "Scenes"))
            ok, msg = validate_shot_structure(tmpdir)
            assert ok is False
            assert "Cache" in msg
            assert "Scripts" in msg


@pytest.mark.houdini
class TestValidateHipSaved:
    def test_returns_tuple(self):
        from src.validator import validate_hip_saved
        ok, msg = validate_hip_saved()
        assert isinstance(ok, bool)
        assert isinstance(msg, str)


@pytest.mark.houdini
class TestValidateRopConnection:
    def test_returns_tuple(self):
        import hou
        from src.validator import validate_rop_connection
        # Use a node from the current scene
        node = hou.node("/obj/Test_Scene__Cornell_Box/karmarendersettings")
        if node:
            ok, msg = validate_rop_connection(node)
            assert isinstance(ok, bool)
