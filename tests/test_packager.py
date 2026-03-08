"""Tests for output_injector, packager, and wrapper_writer modules."""

import os
import tempfile
import pytest

pytestmark = pytest.mark.houdini


class TestOutputInjector:
    def test_injects_product_paths(self):
        from pxr import Usd
        from src.output_injector import inject_output_paths

        stage = Usd.Stage.Open(
            "/home/menser/Dropbox/ai/code/houdini_remote_render/tests/minimal_test_scene.usda"
        )
        modified = inject_output_paths(stage, "test_shot", "../Output")

        assert len(modified) > 0
        assert "/Render/Products/beauty" in modified

        prim = stage.GetPrimAtPath("/Render/Products/beauty")
        val = prim.GetAttribute("productName").Get()
        assert "test_shot.<F4>.png" in val

    def test_custom_output_dir(self):
        from pxr import Usd
        from src.output_injector import inject_output_paths

        stage = Usd.Stage.Open(
            "/home/menser/Dropbox/ai/code/houdini_remote_render/tests/minimal_test_scene.usda"
        )
        inject_output_paths(stage, "test_shot", "../Renders")

        prim = stage.GetPrimAtPath("/Render/Products/beauty")
        attr = prim.GetAttribute("productName")
        val = attr.Get()
        assert "../Renders" in val
        assert "test_shot.<F4>.png" in val


class TestFlattenStage:
    def test_flattens_and_exports(self):
        from pxr import Usd
        from src.packager import flatten_stage

        stage = Usd.Stage.Open(
            "/home/menser/Dropbox/ai/code/houdini_remote_render/tests/minimal_test_scene.usda"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = flatten_stage(stage, tmpdir)
            assert os.path.isfile(result)
            assert result.endswith(".usda")

            # Verify it can be reopened
            flat = Usd.Stage.Open(result)
            assert flat.GetPrimAtPath("/World") is not None


class TestCreateUsdz:
    def test_creates_package(self):
        from pxr import Usd
        from src.packager import flatten_stage, create_usdz

        stage = Usd.Stage.Open(
            "/home/menser/Dropbox/ai/code/houdini_remote_render/tests/minimal_test_scene.usda"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            flat_path = flatten_stage(stage, tmpdir)
            usdz_path = os.path.join(tmpdir, "test.usdz")
            result = create_usdz(flat_path, usdz_path)

            assert os.path.isfile(usdz_path)
            assert os.path.getsize(usdz_path) > 0

    def test_dry_run(self):
        from pxr import Usd
        from src.packager import flatten_stage, create_usdz

        stage = Usd.Stage.Open(
            "/home/menser/Dropbox/ai/code/houdini_remote_render/tests/minimal_test_scene.usda"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            flat_path = flatten_stage(stage, tmpdir)
            usdz_path = os.path.join(tmpdir, "test.usdz")
            files = create_usdz(flat_path, usdz_path, dry_run=True)

            assert len(files) >= 1
            assert not os.path.exists(usdz_path)


class TestWrapperWriter:
    def test_writes_wrapper(self):
        from src.wrapper_writer import write_wrapper
        from pxr import Usd

        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "shot_001.usda")
            write_wrapper(
                usdz_relative_path="shot_001.usdz",
                cache_path_map={
                    "/World/sim": "../Cache/sim.0001.vdb",
                },
                output_usda=output,
            )

            assert os.path.isfile(output)

            # Verify contents
            with open(output) as f:
                content = f.read()
            assert "shot_001.usdz" in content
            assert "../Cache/sim.0001.vdb" in content
