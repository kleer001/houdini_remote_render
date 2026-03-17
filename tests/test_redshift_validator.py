"""Tests for redshift_validator module."""

import pytest

from src.redshift_validator import validate_redshift_stage, validate_redshift_materials


class FakeAttr:
    def __init__(self, name, value=None):
        self._name = name
        self._value = value

    def GetName(self):
        return self._name

    def Get(self):
        return self._value


class FakePrim:
    def __init__(self, type_name, attrs=None, name="prim"):
        self._type_name = type_name
        self._attrs = attrs or []
        self._name = name
        self._parent = None

    def GetTypeName(self):
        return self._type_name

    def GetAttributes(self):
        return self._attrs

    def GetAttribute(self, name):
        for a in self._attrs:
            if a.GetName() == name:
                return a
        return None

    def GetName(self):
        return self._name

    def GetParent(self):
        return self._parent


class FakeStage:
    def __init__(self, prims):
        self._prims = prims

    def Traverse(self):
        return self._prims


class TestValidateRedshiftStage:
    def test_none_stage(self):
        ok, msg = validate_redshift_stage(None)
        assert ok is False
        assert "No USD stage" in msg

    def test_empty_stage(self):
        ok, msg = validate_redshift_stage(FakeStage([]))
        assert ok is False
        assert "No Redshift render settings" in msg

    def test_stage_with_non_redshift_settings(self):
        prim = FakePrim("RenderSettings", [
            FakeAttr("resolution"),
            FakeAttr("camera"),
        ])
        ok, msg = validate_redshift_stage(FakeStage([prim]))
        assert ok is False
        assert "No Redshift render settings" in msg

    def test_stage_with_redshift_settings(self):
        prim = FakePrim("RenderSettings", [
            FakeAttr("resolution"),
            FakeAttr("redshift:global:SamplesMin"),
        ])
        ok, msg = validate_redshift_stage(FakeStage([prim]))
        assert ok is True
        assert msg == ""

    def test_stage_with_multiple_prims(self):
        prims = [
            FakePrim("Camera"),
            FakePrim("RenderSettings", [
                FakeAttr("redshift:global:SamplesMax"),
            ]),
            FakePrim("Mesh"),
        ]
        ok, msg = validate_redshift_stage(FakeStage(prims))
        assert ok is True

    def test_non_rendersettings_with_redshift_attr(self):
        prim = FakePrim("Mesh", [FakeAttr("redshift:visibility")])
        ok, msg = validate_redshift_stage(FakeStage([prim]))
        assert ok is False


class TestValidateRedshiftMaterials:
    def test_no_shaders(self):
        warnings = validate_redshift_materials(FakeStage([]))
        assert warnings == []

    def test_redshift_shaders_ok(self):
        prim = FakePrim("Shader", [
            FakeAttr("info:id", "RedshiftMaterial"),
        ])
        warnings = validate_redshift_materials(FakeStage([prim]))
        assert warnings == []

    def test_preview_surface_warning(self):
        parent = FakePrim("Material", name="wood_mat")
        shader = FakePrim("Shader", [
            FakeAttr("info:id", "UsdPreviewSurface"),
        ], name="wood_shader")
        shader._parent = parent
        warnings = validate_redshift_materials(FakeStage([shader]))
        assert len(warnings) == 1
        assert "UsdPreviewSurface" in warnings[0]
        assert "wood_mat" in warnings[0]
        assert "RS 2025.3" in warnings[0]

    def test_multiple_preview_surfaces_deduped(self):
        parent = FakePrim("Material", name="brick")
        s1 = FakePrim("Shader", [FakeAttr("info:id", "UsdPreviewSurface")], name="s1")
        s1._parent = parent
        s2 = FakePrim("Shader", [FakeAttr("info:id", "UsdPreviewSurface")], name="s2")
        s2._parent = parent
        warnings = validate_redshift_materials(FakeStage([s1, s2]))
        assert len(warnings) == 1
        assert warnings[0].count("brick") == 1

    def test_mixed_shaders(self):
        rs_shader = FakePrim("Shader", [
            FakeAttr("info:id", "RedshiftStandardMaterial"),
        ])
        preview_parent = FakePrim("Material", name="fallback")
        preview = FakePrim("Shader", [
            FakeAttr("info:id", "UsdPreviewSurface"),
        ])
        preview._parent = preview_parent
        warnings = validate_redshift_materials(FakeStage([rs_shader, preview]))
        assert len(warnings) == 1
        assert "fallback" in warnings[0]

    def test_no_info_id_attr(self):
        prim = FakePrim("Shader", [])
        warnings = validate_redshift_materials(FakeStage([prim]))
        assert warnings == []
