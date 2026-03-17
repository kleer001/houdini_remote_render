"""End-to-end tests for the Redshift USD Packager pipeline.

Tests the full packaging workflow: validate → audit → flatten → USDZ →
wrapper → render script → info → manifest.

Requires Houdini (hython) but NOT Redshift — tests the packaging logic
only, not actual rendering.
"""

import os
import sys
import tempfile

import pytest

pytestmark = pytest.mark.houdini


@pytest.fixture
def setup_stage():
    """Create a minimal USD stage suitable for Redshift packaging."""
    import hou
    from pxr import Usd, Sdf, Gf, UsdGeom, UsdRender

    stage = Usd.Stage.CreateInMemory()

    # Sphere geometry
    sphere = UsdGeom.Sphere.Define(stage, "/geometry/sphere")
    sphere.GetRadiusAttr().Set(1.0)

    # Dome light
    light = stage.DefinePrim("/lights/dome", "DomeLight")

    # Camera
    cam = UsdGeom.Camera.Define(stage, "/cameras/main")

    # RenderSettings with redshift: attributes
    rs = UsdRender.Settings.Define(stage, "/Render/rendersettings")
    rs.GetResolutionAttr().Set(Gf.Vec2i(320, 240))
    rs_prim = rs.GetPrim()
    rs_prim.CreateAttribute("redshift:global:SamplesMin", Sdf.ValueTypeNames.Int).Set(4)
    rs_prim.CreateAttribute("redshift:global:SamplesMax", Sdf.ValueTypeNames.Int).Set(16)
    rs.GetCameraRel().SetTargets(["/cameras/main"])

    # RenderProduct
    product = UsdRender.Product.Define(stage, "/Render/Products/beauty")
    product.GetProductNameAttr().Set("../Output/render.<F4>.exr")

    # Wire product to settings
    rs.GetProductsRel().SetTargets(["/Render/Products/beauty"])

    return stage


class TestRedshiftValidation:
    """Test Redshift stage validation with real USD API."""

    def test_validate_redshift_stage(self, setup_stage):
        from src.redshift_validator import validate_redshift_stage
        ok, msg = validate_redshift_stage(setup_stage)
        assert ok is True

    def test_validate_no_redshift_attrs(self):
        from pxr import Usd, Gf, UsdRender
        from src.redshift_validator import validate_redshift_stage

        stage = Usd.Stage.CreateInMemory()
        rs = UsdRender.Settings.Define(stage, "/Render/rs")
        rs.GetResolutionAttr().Set(Gf.Vec2i(1920, 1080))
        # No redshift: attributes

        ok, msg = validate_redshift_stage(stage)
        assert ok is False
        assert "No Redshift" in msg

    def test_audit_stage(self, setup_stage):
        from src.auditor import audit_stage
        report = audit_stage(setup_stage)
        assert report.has_render_settings
        assert report.has_camera
        assert report.has_render_products
        assert report.has_lights
        assert report.light_count == 1


class TestRedshiftPackaging:
    """Test the full packaging pipeline."""

    def test_flatten_and_usdz(self, setup_stage):
        from src.packager import flatten_stage, create_usdz

        with tempfile.TemporaryDirectory() as tmpdir:
            flat_path = flatten_stage(setup_stage, tmpdir)
            assert os.path.isfile(flat_path)

            usdz_path = os.path.join(tmpdir, "test.usdz")
            create_usdz(flat_path, usdz_path)
            assert os.path.isfile(usdz_path)
            assert os.path.getsize(usdz_path) > 0

    def test_output_injection(self, setup_stage):
        from src.packager import flatten_stage
        from src.output_injector import inject_output_paths
        from pxr import Usd, UsdRender

        with tempfile.TemporaryDirectory() as tmpdir:
            flat_path = flatten_stage(setup_stage, tmpdir)
            edit_stage = Usd.Stage.Open(flat_path)
            inject_output_paths(
                edit_stage, "test_shot",
                output_format="exr",
                frame_start=1001,
                frame_end=1100,
            )
            edit_stage.GetRootLayer().Save()

            # Verify productName was set
            check_stage = Usd.Stage.Open(flat_path)
            for prim in check_stage.Traverse():
                if prim.GetTypeName() == "RenderProduct":
                    product = UsdRender.Product(prim)
                    name = product.GetProductNameAttr().Get()
                    name_str = name.path if hasattr(name, "path") else str(name)
                    assert "test_shot" in name_str
                    assert "<F4>" in name_str or ".exr" in name_str

    def test_full_package_pipeline(self, setup_stage):
        """Test the complete pipeline: flatten → inject → USDZ → wrapper → scripts."""
        from src.packager import flatten_stage, create_usdz
        from src.output_injector import inject_output_paths
        from src.auditor import ensure_render_settings
        from src.wrapper_writer import write_wrapper
        from src.redshift_script_writer import write_redshift_script
        from src.redshift_info_writer import write_redshift_info
        from src.redshift_manifest import RedshiftManifestData, write_redshift_manifest
        from src.platform_utils import ensure_dir
        from pxr import Usd

        with tempfile.TemporaryDirectory() as tmpdir:
            shot_name = "e2e_test"
            shot_root = os.path.join(tmpdir, "e2e_test_P1T1_v001")

            # Create dirs
            for d in ("Output", "Textures", "Scenes", "Scripts"):
                ensure_dir(os.path.join(shot_root, d))

            # Flatten
            staging = os.path.join(tmpdir, "staging")
            os.makedirs(staging)
            flat_path = flatten_stage(setup_stage, staging)

            # Edit flattened stage
            edit_stage = Usd.Stage.Open(flat_path)
            ensure_render_settings(edit_stage)
            inject_output_paths(edit_stage, shot_name, "exr", 1001, 1100)
            edit_stage.GetRootLayer().Save()

            # USDZ
            usdz_path = os.path.join(shot_root, "Scenes", f"{shot_name}.usdz")
            create_usdz(flat_path, usdz_path)
            assert os.path.isfile(usdz_path)

            # Wrapper
            wrapper_path = os.path.join(shot_root, "Scenes", f"{shot_name}.usda")
            write_wrapper(f"{shot_name}.usdz", {}, wrapper_path)
            assert os.path.isfile(wrapper_path)

            # Render script
            script_path = os.path.join(shot_root, "Scripts", "run_render.sh")
            write_redshift_script(
                output_path=script_path,
                shot_name=shot_name,
                wrapper_filename=f"{shot_name}.usda",
                frame_start=1001,
                frame_end=1100,
                redshift_path="/usr/redshift",
            )
            assert os.path.isfile(script_path)

            with open(script_path) as f:
                script = f.read()
            assert "redshiftUsdCmdLine" in script
            assert "e2e_test.usda" in script
            assert "-f 1001" in script
            assert "-n 100" in script

            # Info
            info_path = os.path.join(shot_root, "render_info.txt")
            write_redshift_info(
                output_path=info_path,
                shot_name=shot_name,
                folder_name="e2e_test_P1T1_v001",
                frame_start=1001,
                frame_end=1100,
                frame_inc=1,
                resolution=(320, 240),
                camera="/cameras/main",
                usd_file=f"{shot_name}.usda",
            )
            assert os.path.isfile(info_path)

            # Manifest
            manifest_path = os.path.join(shot_root, f"{shot_name}_manifest.txt")
            data = RedshiftManifestData(
                shot_name=shot_name,
                folder_name="e2e_test_P1T1_v001",
                frame_start=1001,
                frame_end=1100,
                resolution=(320, 240),
                camera="/cameras/main",
            )
            write_redshift_manifest(manifest_path, data)
            assert os.path.isfile(manifest_path)

            # Verify all expected files
            expected = [
                "Scenes/e2e_test.usdz",
                "Scenes/e2e_test.usda",
                "Scripts/run_render.sh",
                "render_info.txt",
                "e2e_test_manifest.txt",
            ]
            for rel in expected:
                full = os.path.join(shot_root, rel)
                assert os.path.isfile(full), f"Missing: {rel}"
