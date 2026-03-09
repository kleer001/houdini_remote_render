"""Tests for cache_validator module."""

from src.cache_validator import validate_cache_node, validate_frame_range, validate_output_path


class FakeNode:
    """Minimal mock of a hou.SopNode."""
    def __init__(self, type_name="filecache"):
        self._type_name = type_name

    def type(self):
        return self

    def name(self):
        return self._type_name


class TestValidateCacheNode:
    def test_valid_filecache(self):
        ok, msg = validate_cache_node(FakeNode("filecache"))
        assert ok is True
        assert msg == ""

    def test_valid_filecache_versioned(self):
        ok, msg = validate_cache_node(FakeNode("filecache::2.0"))
        assert ok is True
        assert msg == ""

    def test_none_node(self):
        ok, msg = validate_cache_node(None)
        assert ok is False
        assert "No File Cache" in msg

    def test_wrong_type(self):
        ok, msg = validate_cache_node(FakeNode("null"))
        assert ok is False
        assert "null" in msg
        assert "filecache" in msg


class TestValidateFrameRange:
    def test_valid_range(self):
        ok, msg = validate_frame_range(1001, 1200, 1)
        assert ok is True
        assert msg == ""

    def test_single_frame(self):
        ok, msg = validate_frame_range(1001, 1001, 1)
        assert ok is True

    def test_start_after_end(self):
        ok, msg = validate_frame_range(1200, 1001, 1)
        assert ok is False
        assert "after" in msg.lower()

    def test_zero_increment(self):
        ok, msg = validate_frame_range(1001, 1200, 0)
        assert ok is False
        assert "increment" in msg.lower()

    def test_negative_increment(self):
        ok, msg = validate_frame_range(1001, 1200, -1)
        assert ok is False


class TestValidateOutputPath:
    def test_valid_path(self):
        ok, msg = validate_output_path("/path/to/output.$F4.bgeo.sc")
        assert ok is True

    def test_empty_path(self):
        ok, msg = validate_output_path("")
        assert ok is False
        assert "empty" in msg.lower()

    def test_whitespace_path(self):
        ok, msg = validate_output_path("   ")
        assert ok is False
