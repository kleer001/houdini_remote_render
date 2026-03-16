"""Houdini-dependent tests for dependency_resolver discovery functions.

Creates test scenes via hython and verifies that resolve_dependencies()
correctly discovers cache nodes and virtual wires.

Skipped in CI: pytest -m "not houdini"
"""

import json
import os
import subprocess
import tempfile
import textwrap

import pytest

pytestmark = pytest.mark.houdini


def _hython():
    hfs = os.environ.get("HFS", "")
    return os.path.join(hfs, "bin", "hython") if hfs else "hython"


def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_hython(script_text, timeout=120):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(script_text)
        script_path = f.name
    try:
        r = subprocess.run(
            [_hython(), script_path],
            capture_output=True, text=True, timeout=timeout,
        )
        return r.returncode, r.stdout, r.stderr
    finally:
        os.unlink(script_path)


class TestResolverLive:
    """Verify resolve_dependencies() with live Houdini nodes."""

    @pytest.fixture(scope="class")
    def resolver_results(self, tmp_path_factory):
        """Run a single hython script that creates multiple test scenes
        and exercises the resolver. Results written to JSON."""
        tmpdir = str(tmp_path_factory.mktemp("resolver"))
        output_json = os.path.join(tmpdir, "results.json")
        repo = _repo_root()
        hda_path = os.path.join(repo, "hda", "remote_file_cache.hdalc")
        karma_hda = os.path.join(repo, "hda", "karma_usd_packager.hdalc")

        script = textwrap.dedent(f"""\
            import hou, json, sys, os
            sys.path.insert(0, "{repo}")
            from src.dependency_resolver import (
                resolve_dependencies, format_dag_summary,
            )

            results = {{}}

            # Install HDAs
            hda_path = "{hda_path}"
            hou.hda.installFile(hda_path)
            defs = hou.hda.definitionsInFile(hda_path)
            cache_type = defs[0].nodeTypeName()

            # Also install Karma packager if available
            karma_hda = "{karma_hda}"
            karma_type = None
            if os.path.exists(karma_hda):
                hou.hda.installFile(karma_hda)
                kdefs = hou.hda.definitionsInFile(karma_hda)
                if kdefs:
                    karma_type = kdefs[0].nodeTypeName()

            # =====================================================
            # Scenario 1: Single cache -> sopimport -> LOP stage
            # =====================================================
            obj = hou.node("/obj")
            geo1 = obj.createNode("geo", "geo1")
            for c in geo1.children():
                c.destroy()
            box = geo1.createNode("box", "box1")
            cache1 = geo1.createNode(cache_type, "cache_fluid")
            cache1.setInput(0, box)

            # Create a LOP network with sopimport
            stage = hou.node("/stage")
            si = stage.createNode("sopimport", "import_fluid")
            si.parm("soppath").set(cache1.path())

            # Create a null as the "karma packager" stand-in
            # (resolve_dependencies just needs a LOP node to walk from)
            karma_standin = stage.createNode("null", "karma_standin")
            karma_standin.setInput(0, si)

            dag = resolve_dependencies(karma_standin)

            results["scenario1"] = {{
                "num_cache_units": len(dag.cache_units),
                "execution_order": dag.execution_order,
                "cache_labels": [
                    dag.cache_units[p].label
                    for p in dag.execution_order
                ],
                "cache_frame_starts": [
                    dag.cache_units[p].frame_start
                    for p in dag.execution_order
                ],
                "num_virtual_wires": len(dag.virtual_wires),
                "num_warnings": len(dag.warnings),
                "summary": format_dag_summary(dag),
            }}

            # =====================================================
            # Scenario 2: Two caches, second depends on first via
            #              Object Merge (cross-geo virtual wire)
            # =====================================================
            geo2 = obj.createNode("geo", "geo2")
            for c in geo2.children():
                c.destroy()
            # Object Merge pulls from cache1's output in geo1
            om = geo2.createNode("object_merge", "merge_from_geo1")
            om.parm("objpath1").set(cache1.path())
            cache2 = geo2.createNode(cache_type, "cache_mesh")
            cache2.setInput(0, om)

            stage2 = stage
            si2 = stage2.createNode("sopimport", "import_mesh")
            si2.parm("soppath").set(cache2.path())
            karma2 = stage2.createNode("null", "karma_standin2")
            karma2.setInput(0, si2)

            dag2 = resolve_dependencies(karma2)

            results["scenario2"] = {{
                "num_cache_units": len(dag2.cache_units),
                "execution_order": dag2.execution_order,
                "cache_labels": [
                    dag2.cache_units[p].label
                    for p in dag2.execution_order
                ],
                "num_virtual_wires": len(dag2.virtual_wires),
                "virtual_wire_types": [
                    vw.wire_type for vw in dag2.virtual_wires
                ],
                "summary": format_dag_summary(dag2),
            }}

            # Check dependency direction: cache_fluid must be before cache_mesh
            if len(dag2.execution_order) == 2:
                fluid_idx = None
                mesh_idx = None
                for i, p in enumerate(dag2.execution_order):
                    if "cache_fluid" in p:
                        fluid_idx = i
                    if "cache_mesh" in p:
                        mesh_idx = i
                results["scenario2"]["fluid_before_mesh"] = (
                    fluid_idx is not None
                    and mesh_idx is not None
                    and fluid_idx < mesh_idx
                )
            else:
                results["scenario2"]["fluid_before_mesh"] = False

            # =====================================================
            # Scenario 3: No cache nodes upstream (pure geo -> LOP)
            # =====================================================
            geo3 = obj.createNode("geo", "geo3")
            for c in geo3.children():
                c.destroy()
            box3 = geo3.createNode("box", "box3")
            null3 = geo3.createNode("null", "OUT")
            null3.setInput(0, box3)

            stage3 = stage
            si3 = stage3.createNode("sopimport", "import_box")
            si3.parm("soppath").set(null3.path())
            karma3 = stage3.createNode("null", "karma_standin3")
            karma3.setInput(0, si3)

            dag3 = resolve_dependencies(karma3)

            results["scenario3"] = {{
                "num_cache_units": len(dag3.cache_units),
                "execution_order": dag3.execution_order,
            }}

            with open("{output_json}", "w") as f:
                json.dump(results, f)
        """)

        rc, stdout, stderr = _run_hython(script)
        assert rc == 0, (
            f"Resolver hython failed (rc={rc}):\n{stdout}\n{stderr}"
        )
        assert os.path.isfile(output_json), (
            f"No JSON output.\nstdout: {stdout}\nstderr: {stderr}"
        )

        with open(output_json) as f:
            return json.load(f)

    # --- Scenario 1: single cache ---

    def test_single_cache_found(self, resolver_results):
        assert resolver_results["scenario1"]["num_cache_units"] == 1

    def test_single_cache_label(self, resolver_results):
        labels = resolver_results["scenario1"]["cache_labels"]
        assert "cache_fluid" in labels

    def test_single_cache_summary_has_render(self, resolver_results):
        assert "Render" in resolver_results["scenario1"]["summary"]

    # --- Scenario 2: two caches with Object Merge dependency ---

    def test_two_caches_found(self, resolver_results):
        assert resolver_results["scenario2"]["num_cache_units"] == 2

    def test_object_merge_wire_detected(self, resolver_results):
        assert resolver_results["scenario2"]["num_virtual_wires"] >= 1
        assert "object_merge" in resolver_results["scenario2"]["virtual_wire_types"]

    def test_fluid_before_mesh(self, resolver_results):
        assert resolver_results["scenario2"]["fluid_before_mesh"]

    def test_two_cache_summary_shows_both(self, resolver_results):
        summary = resolver_results["scenario2"]["summary"]
        assert "cache_fluid" in summary
        assert "cache_mesh" in summary

    # --- Scenario 3: no caches ---

    def test_no_caches_returns_empty(self, resolver_results):
        assert resolver_results["scenario3"]["num_cache_units"] == 0
        assert resolver_results["scenario3"]["execution_order"] == []
