"""Tests for auditor module."""

import pytest

pytestmark = pytest.mark.houdini


class TestAuditStage:
    def test_cornell_box_scene(self):
        from pxr import Usd
        from src.auditor import audit_stage

        stage = Usd.Stage.Open(
            "/home/menser/Dropbox/ai/code/houdini_remote_render/tests/minimal_test_scene.usda"
        )
        report = audit_stage(stage)

        assert report.has_render_settings is True
        assert report.has_camera is True
        assert report.has_render_products is True
        assert report.instance_count == 0
        assert len(report.warnings) == 0

    def test_empty_stage_warns(self):
        from pxr import Usd
        from src.auditor import audit_stage

        stage = Usd.Stage.CreateInMemory()
        stage.DefinePrim("/World", "Xform")
        report = audit_stage(stage)

        assert report.has_render_settings is False
        assert report.has_camera is False
        assert len(report.warnings) >= 2


class TestEnsureRenderSettings:
    def test_creates_settings_when_missing(self):
        from pxr import Usd
        from src.auditor import ensure_render_settings, audit_stage

        stage = Usd.Stage.CreateInMemory()
        stage.DefinePrim("/World", "Xform")

        ensure_render_settings(stage)

        report = audit_stage(stage)
        assert report.has_render_settings is True

    def test_does_not_duplicate(self):
        from pxr import Usd
        from src.auditor import ensure_render_settings

        stage = Usd.Stage.Open(
            "/home/menser/Dropbox/ai/code/houdini_remote_render/tests/minimal_test_scene.usda"
        )
        # Should not create a second one
        ensure_render_settings(stage)

        count = sum(1 for p in stage.Traverse() if p.GetTypeName() == "RenderSettings")
        assert count == 1
