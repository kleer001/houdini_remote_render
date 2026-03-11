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


class TestEnsureRenderVars:
    def test_patches_product_without_ordered_vars(self):
        from pxr import Usd, UsdRender, Sdf
        from src.auditor import ensure_render_vars

        stage = Usd.Stage.CreateInMemory()
        stage.DefinePrim("/Render", "Scope")
        stage.DefinePrim("/Render/Products", "Scope")
        UsdRender.Product.Define(stage, "/Render/Products/renderproduct")

        patched = ensure_render_vars(stage)

        assert patched == 1
        product = UsdRender.Product(stage.GetPrimAtPath("/Render/Products/renderproduct"))
        targets = product.GetOrderedVarsRel().GetTargets()
        assert len(targets) == 2

        beauty = UsdRender.Var(stage.GetPrimAtPath(targets[0]))
        assert beauty.GetDataTypeAttr().Get() == "color3f"
        assert beauty.GetSourceNameAttr().Get() == "Ci"

        alpha = UsdRender.Var(stage.GetPrimAtPath(targets[1]))
        assert alpha.GetDataTypeAttr().Get() == "float"
        assert alpha.GetSourceNameAttr().Get() == "a"

    def test_skips_product_with_existing_ordered_vars(self):
        from pxr import Usd
        from src.auditor import ensure_render_vars

        stage = Usd.Stage.Open(
            "/home/menser/Dropbox/ai/code/houdini_remote_render/tests/minimal_test_scene.usda"
        )
        patched = ensure_render_vars(stage)

        assert patched == 0
