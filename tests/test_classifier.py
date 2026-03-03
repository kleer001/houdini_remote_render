"""Tests for classifier module."""

import pytest

from src.classifier import detect_udim_pattern, _get_extension

pytestmark = pytest.mark.houdini


class TestGetExtension:
    """These tests don't need Houdini but are co-located for simplicity."""

    def test_simple_extension(self):
        assert _get_extension("/foo/bar.png") == ".png"

    def test_compound_bgeo(self):
        assert _get_extension("/foo/bar.bgeo.sc") == ".bgeo.sc"

    def test_exr(self):
        assert _get_extension("/textures/diffuse.exr") == ".exr"

    def test_case_insensitive(self):
        assert _get_extension("/foo/BAR.PNG") == ".png"


class TestDetectUdimPattern:
    def test_finds_udim(self):
        paths = [
            "/tex/wood.<UDIM>.exr",
            "/tex/diffuse_color.png",
        ]
        patterns = detect_udim_pattern(paths)
        assert "/tex/wood.<UDIM>.exr" in patterns
        assert len(patterns) == 1

    def test_no_udim(self):
        paths = ["/tex/diffuse.png", "/tex/normal.exr"]
        patterns = detect_udim_pattern(paths)
        assert len(patterns) == 0


class TestClassifyDependencies:
    def test_minimal_scene(self):
        from src.classifier import classify_dependencies

        deps = classify_dependencies(
            "/home/menser/Dropbox/ai/code/houdini_remote_render/tests/minimal_test_scene.usda"
        )

        # Textures don't exist on disk, so they show up as unresolved
        assert len(deps.unresolved) == 2
        assert any("diffuse_color.png" in p for p in deps.unresolved)
        assert any("<UDIM>" in p for p in deps.unresolved)

        # UDIM pattern should be detected
        assert len(deps.udim_patterns) == 1
        assert "<UDIM>" in deps.udim_patterns[0]

        # No sublayers or caches in our test scene
        assert len(deps.sublayers) == 0
        assert len(deps.caches) == 0
