"""Tests for mantra_validator module."""

from src.mantra_validator import validate_mantra_node, validate_output_picture


class FakeNode:
    """Minimal mock of a hou.RopNode."""
    def __init__(self, type_name="ifd"):
        self._type_name = type_name

    def type(self):
        return self

    def name(self):
        return self._type_name


class TestValidateMantraNode:
    def test_valid_ifd(self):
        ok, msg = validate_mantra_node(FakeNode("ifd"))
        assert ok is True
        assert msg == ""

    def test_valid_ifd_versioned(self):
        ok, msg = validate_mantra_node(FakeNode("ifd::2.0"))
        assert ok is True
        assert msg == ""

    def test_none_node(self):
        ok, msg = validate_mantra_node(None)
        assert ok is False
        assert "No Mantra" in msg

    def test_wrong_type(self):
        ok, msg = validate_mantra_node(FakeNode("null"))
        assert ok is False
        assert "null" in msg
        assert "ifd" in msg

    def test_wrong_type_filecache(self):
        ok, msg = validate_mantra_node(FakeNode("filecache"))
        assert ok is False
        assert "filecache" in msg


class TestValidateOutputPicture:
    def test_valid_path(self):
        ok, msg = validate_output_picture("/path/to/render.$F4.exr")
        assert ok is True

    def test_empty_path(self):
        ok, msg = validate_output_picture("")
        assert ok is False
        assert "empty" in msg.lower()

    def test_whitespace_path(self):
        ok, msg = validate_output_picture("   ")
        assert ok is False

    def test_none_path(self):
        ok, msg = validate_output_picture(None)
        assert ok is False
