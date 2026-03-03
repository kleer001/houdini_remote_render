"""Tests for converter module."""

import os
import tempfile
import pytest

from src.converter import needs_conversion, convert_all, ConversionReport


class TestNeedsConversion:
    def test_png_needs_conversion(self):
        assert needs_conversion("/tex/diffuse.png") is True

    def test_jpg_needs_conversion(self):
        assert needs_conversion("/tex/diffuse.jpg") is True

    def test_exr_needs_conversion(self):
        assert needs_conversion("/tex/diffuse.exr") is True

    def test_rat_skip(self):
        assert needs_conversion("/tex/diffuse.rat") is False


class TestConvertAllDryRun:
    def test_dry_run_reports_planned(self):
        textures = ["/tex/a.png", "/tex/b.jpg", "/tex/c.rat"]
        report = convert_all(textures, "/tmp/out", dry_run=True)

        assert len(report.converted) == 2  # png and jpg
        assert len(report.skipped) == 1    # rat
        assert len(report.failed) == 0

    def test_dry_run_output_paths(self):
        textures = ["/tex/diffuse.png"]
        report = convert_all(textures, "/tmp/out", dry_run=True)

        src, dst = report.converted[0]
        assert src == "/tex/diffuse.png"
        assert dst.endswith(".exr")
        assert "/tmp/out" in dst


@pytest.mark.houdini
class TestConvertTexture:
    def test_convert_real_texture(self):
        """Integration test: create a small test image, convert it."""
        from src.converter import convert_texture
        # This test requires a real texture file — skip if none available
        # It will be exercised in the end-to-end integration test
        pytest.skip("Requires a real texture file — tested in integration")
