"""Houdini-dependent tests for cache_auditor and cache_scene_writer.

These tests run hython subprocesses to exercise the audit and scene-writing
pipeline with live Houdini nodes.  Each test class batches assertions into a
single hython invocation to avoid repeated ~10s startup costs.

Skipped in CI: pytest -m "not houdini"
"""

import glob
import json
import os
import subprocess
import tempfile
import textwrap

import pytest

pytestmark = pytest.mark.houdini


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _hython():
    """Return path to hython binary."""
    hfs = os.environ.get("HFS", "")
    return os.path.join(hfs, "bin", "hython") if hfs else "hython"


def _repo_root():
    """Return repo root (parent of tests/)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _resolve_hip_path(hip_path):
    """Return actual .hip path — Indie saves as .hiplc, Apprentice as .hipnc."""
    if os.path.exists(hip_path):
        return hip_path
    for ext in (".hiplc", ".hipnc"):
        alt = hip_path.rsplit(".hip", 1)[0] + ext
        if os.path.exists(alt):
            return alt
    raise FileNotFoundError(f"No .hip variant found for {hip_path}")


def _run_hython(script_text, timeout=120):
    """Write script to temp file, run via hython, return (rc, stdout, stderr)."""
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


# ---------------------------------------------------------------------------
# Group 1: cache_auditor with live filecache::2.0 nodes
# ---------------------------------------------------------------------------

class TestCacheAuditorLive:
    """Verify audit_file_cache() correctly reads filecache::2.0 parameters."""

    @pytest.fixture(scope="class")
    def audit_results(self, tmp_path_factory):
        """Run a single hython subprocess that creates multiple filecache
        configurations, audits each, and writes all results to one JSON."""
        tmpdir = str(tmp_path_factory.mktemp("audit"))
        output_json = os.path.join(tmpdir, "results.json")
        repo = _repo_root()

        script = textwrap.dedent(f"""\
            import hou, json, sys
            sys.path.insert(0, "{repo}")
            from src.cache_auditor import audit_file_cache
            from dataclasses import asdict

            results = {{}}

            obj = hou.node("/obj")
            geo = obj.createNode("geo", "test_geo")
            for child in geo.children():
                child.destroy()
            box = geo.createNode("box", "box1")

            # --- constructed: standard settings ---
            fc = geo.createNode("filecache::2.0", "fc_constructed")
            fc.setInput(0, box)
            fc.parm("filemethod").set(0)
            fc.parm("basedir").set("/tmp/test_cache")
            fc.parm("basename").set("myshot")
            fc.parm("enableversion").set(1)
            fc.parm("version").set(3)
            fc.parm("trange").set(1)
            fc.parm("f1").set(1)
            fc.parm("f2").set(240)
            fc.parm("f3").set(1)
            fc.parm("savebackground").set(0)
            fc.parm("loadfromdisk").set(0)
            fc.parm("timedependent").set(1)
            fc.parm("cachesim").set(1)
            r = audit_file_cache(fc)
            d = asdict(r)
            d["frame_count"] = r.frame_count
            results["constructed"] = d

            # --- explicit: explicit file path ---
            fc2 = geo.createNode("filecache::2.0", "fc_explicit")
            fc2.setInput(0, box)
            fc2.parm("filemethod").set(1)
            fc2.parm("file").set("/path/to/cache/myshot.$F4.bgeo.sc")
            fc2.parm("trange").set(1)
            fc2.parm("f1").set(1)
            fc2.parm("f2").set(100)
            fc2.parm("f3").set(1)
            fc2.parm("savebackground").set(0)
            fc2.parm("loadfromdisk").set(0)
            r2 = audit_file_cache(fc2)
            results["explicit"] = asdict(r2)

            # --- savebg: save-in-background warning ---
            fc3 = geo.createNode("filecache::2.0", "fc_savebg")
            fc3.setInput(0, box)
            fc3.parm("savebackground").set(1)
            fc3.parm("loadfromdisk").set(0)
            fc3.parm("trange").set(1)
            fc3.parm("f1").set(1)
            fc3.parm("f2").set(10)
            fc3.parm("f3").set(1)
            r3 = audit_file_cache(fc3)
            results["savebg"] = asdict(r3)

            # --- loadfromdisk: load-from-disk warning ---
            fc4 = geo.createNode("filecache::2.0", "fc_loadfromdisk")
            fc4.setInput(0, box)
            fc4.parm("savebackground").set(0)
            fc4.parm("loadfromdisk").set(1)
            fc4.parm("trange").set(1)
            fc4.parm("f1").set(1)
            fc4.parm("f2").set(10)
            fc4.parm("f3").set(1)
            r4 = audit_file_cache(fc4)
            results["loadfromdisk"] = asdict(r4)

            # --- badrange: start > end warning ---
            # Float parms like f1/f2 have default expressions ($FSTART/$FEND).
            # parm.set() is silently ignored when an expression is active,
            # so we must delete keyframes first.
            fc5 = geo.createNode("filecache::2.0", "fc_badrange")
            fc5.setInput(0, box)
            fc5.parm("savebackground").set(0)
            fc5.parm("loadfromdisk").set(0)
            fc5.parm("trange").set(1)
            for p in ("f1", "f2", "f3"):
                fc5.parm(p).deleteAllKeyframes()
            fc5.parm("f1").set(100)
            fc5.parm("f2").set(1)
            fc5.parm("f3").set(1)
            r5 = audit_file_cache(fc5)
            results["badrange"] = asdict(r5)

            # --- frameinc: frame count with non-unit increment ---
            fc6 = geo.createNode("filecache::2.0", "fc_frameinc")
            fc6.setInput(0, box)
            fc6.parm("savebackground").set(0)
            fc6.parm("loadfromdisk").set(0)
            fc6.parm("trange").set(1)
            for p in ("f1", "f2", "f3"):
                fc6.parm(p).deleteAllKeyframes()
            fc6.parm("f1").set(1)
            fc6.parm("f2").set(10)
            fc6.parm("f3").set(2)
            r6 = audit_file_cache(fc6)
            d6 = asdict(r6)
            d6["frame_count"] = r6.frame_count
            results["frameinc"] = d6

            with open("{output_json}", "w") as f:
                json.dump(results, f)
        """)

        rc, stdout, stderr = _run_hython(script)
        assert rc == 0, f"Auditor hython failed (rc={rc}):\n{stdout}\n{stderr}"
        assert os.path.isfile(output_json), f"No JSON output.\nstdout: {stdout}"

        with open(output_json) as f:
            return json.load(f)

    # --- constructed path assertions ---

    def test_constructed_method(self, audit_results):
        assert audit_results["constructed"]["file_method"] == "constructed"

    def test_constructed_base_name(self, audit_results):
        assert audit_results["constructed"]["base_name"] == "myshot"

    def test_constructed_base_dir(self, audit_results):
        assert audit_results["constructed"]["base_dir"] == "/tmp/test_cache"

    def test_constructed_frame_range(self, audit_results):
        r = audit_results["constructed"]
        assert r["frame_start"] == 1
        assert r["frame_end"] == 240
        assert r["frame_inc"] == 1

    def test_constructed_version(self, audit_results):
        r = audit_results["constructed"]
        assert r["version_enabled"] == 1
        assert r["version"] == 3

    def test_constructed_output_path_nonempty(self, audit_results):
        path = audit_results["constructed"]["output_path"]
        assert path, "sopoutput should be non-empty"
        assert "myshot" in path

    def test_constructed_no_warnings(self, audit_results):
        assert audit_results["constructed"]["warnings"] == []

    def test_constructed_frame_count(self, audit_results):
        assert audit_results["constructed"]["frame_count"] == 240

    # --- explicit path assertions ---

    def test_explicit_method(self, audit_results):
        assert audit_results["explicit"]["file_method"] == "explicit"

    def test_explicit_path_contains_name(self, audit_results):
        assert "myshot" in audit_results["explicit"]["explicit_path"]

    # --- warning assertions ---

    def test_warning_savebackground(self, audit_results):
        warnings = audit_results["savebg"]["warnings"]
        assert any("Save in Background" in w for w in warnings)

    def test_warning_loadfromdisk(self, audit_results):
        warnings = audit_results["loadfromdisk"]["warnings"]
        assert any("Load from Disk" in w for w in warnings)

    def test_warning_bad_frame_range(self, audit_results):
        warnings = audit_results["badrange"]["warnings"]
        assert any("after frame end" in w for w in warnings)

    # --- frame count with increment ---

    def test_frame_count_with_increment(self, audit_results):
        # f1=1, f2=10, f3=2 -> frames 1,3,5,7,9 -> 5 frames
        assert audit_results["frameinc"]["frame_count"] == 5


# ---------------------------------------------------------------------------
# Group 2: cache_scene_writer with HDA
# ---------------------------------------------------------------------------

class TestCacheSceneWriterLive:
    """Verify save_portable_hip() rewrites and restores parameters correctly."""

    @pytest.fixture(scope="class")
    def writer_results(self, tmp_path_factory):
        """Run a single hython subprocess that installs the HDA, creates a
        scene, calls save_portable_hip(), checks restoration, reloads the
        portable hip, and writes all results to JSON."""
        tmpdir = str(tmp_path_factory.mktemp("writer"))
        output_json = os.path.join(tmpdir, "results.json")
        repo = _repo_root()
        hda_path = os.path.join(repo, "hda", "remote_file_cache.hdalc")

        script = textwrap.dedent(f"""\
            import hou, json, sys, os
            sys.path.insert(0, "{repo}")
            from src.cache_scene_writer import save_portable_hip

            results = {{}}

            # Install HDA
            hda_path = "{hda_path}"
            hou.hda.installFile(hda_path)
            defs = hou.hda.definitionsInFile(hda_path)
            hda_type = defs[0].nodeTypeName()
            results["hda_type"] = hda_type

            # Create scene
            obj = hou.node("/obj")
            geo = obj.createNode("geo", "test_geo")
            for child in geo.children():
                child.destroy()
            box = geo.createNode("box", "box1")
            hda_node = geo.createNode(hda_type, "remote_cache1")
            hda_node.setInput(0, box)

            # Save initial hip (needed for path reference)
            initial_hip = os.path.join("{tmpdir}", "initial.hip")
            hou.hipFile.save(initial_hip)

            # Get internal filecache
            fc = hda_node.node("filecache1")
            results["fc_found"] = fc is not None
            if fc is None:
                results["hda_children"] = [c.name() for c in hda_node.children()]
                with open("{output_json}", "w") as f:
                    json.dump(results, f)
                sys.exit(0)

            results["fc_path"] = fc.path()

            # Snapshot original expressions before save_portable_hip
            orig_basedir_expr = None
            try:
                orig_basedir_expr = fc.parm("basedir").expression()
            except hou.OperationFailed:
                pass
            results["orig_basedir_expr"] = orig_basedir_expr

            orig_hip_path = hou.hipFile.path()
            results["orig_hip_path"] = orig_hip_path

            # --- Call save_portable_hip (constructed mode, default) ---
            portable_dir = os.path.join("{tmpdir}", "Scenes")
            os.makedirs(portable_dir, exist_ok=True)
            portable_path = os.path.join(portable_dir, "portable.hip")
            save_portable_hip(fc, portable_path)

            # --- Post-call: check restoration ---
            restored_basedir_expr = None
            try:
                restored_basedir_expr = fc.parm("basedir").expression()
            except hou.OperationFailed:
                pass
            results["restored_basedir_expr"] = restored_basedir_expr
            results["hip_path_after"] = hou.hipFile.path()
            results["hda_matches_def"] = hda_node.matchesCurrentDefinition()

            # Find actual portable hip (Indie -> .hiplc)
            portable_actual = portable_path
            if not os.path.exists(portable_actual):
                for ext in (".hiplc", ".hipnc"):
                    alt = portable_path.rsplit(".hip", 1)[0] + ext
                    if os.path.exists(alt):
                        portable_actual = alt
                        break

            results["portable_exists"] = os.path.exists(portable_actual)
            results["portable_path"] = portable_actual
            results["portable_size"] = (
                os.path.getsize(portable_actual)
                if os.path.exists(portable_actual) else 0
            )

            # --- Reload portable hip and check rewritten values ---
            if os.path.exists(portable_actual):
                hou.hipFile.load(portable_actual, suppress_save_prompt=True)
                fc_r = hou.node(results["fc_path"])
                results["reloaded_fc_found"] = fc_r is not None

                if fc_r is not None:
                    # basedir should be $HIP/../Cache (raw string, no expression)
                    try:
                        results["reloaded_basedir_raw"] = (
                            fc_r.parm("basedir").unexpandedString()
                        )
                    except hou.OperationFailed:
                        results["reloaded_basedir_raw"] = fc_r.parm("basedir").eval()
                    results["reloaded_savebackground"] = (
                        fc_r.parm("savebackground").eval()
                    )
                    results["reloaded_loadfromdisk"] = (
                        fc_r.parm("loadfromdisk").eval()
                    )
            else:
                results["reloaded_fc_found"] = False

            with open("{output_json}", "w") as f:
                json.dump(results, f)
        """)

        rc, stdout, stderr = _run_hython(script)
        assert rc == 0, f"Writer hython failed (rc={rc}):\n{stdout}\n{stderr}"
        assert os.path.isfile(output_json), f"No JSON output.\nstdout: {stdout}"

        with open(output_json) as f:
            return json.load(f)

    def test_internal_filecache_found(self, writer_results):
        assert writer_results["fc_found"], (
            f"filecache1 not found. Children: {writer_results.get('hda_children')}"
        )

    def test_portable_hip_created(self, writer_results):
        assert writer_results["portable_exists"]
        assert writer_results["portable_size"] > 0

    def test_basedir_rewritten_in_portable(self, writer_results):
        raw = writer_results.get("reloaded_basedir_raw", "")
        assert "$HIP/../Cache" in raw, f"Expected $HIP/../Cache, got: {raw}"

    def test_savebackground_off_in_portable(self, writer_results):
        assert writer_results.get("reloaded_savebackground") == 0

    def test_loadfromdisk_off_in_portable(self, writer_results):
        assert writer_results.get("reloaded_loadfromdisk") == 0

    def test_original_expression_restored(self, writer_results):
        orig = writer_results["orig_basedir_expr"]
        restored = writer_results["restored_basedir_expr"]
        assert orig == restored, (
            f"Expression not restored. Original: {orig!r}, After: {restored!r}"
        )

    def test_hip_path_restored(self, writer_results):
        assert writer_results["orig_hip_path"] == writer_results["hip_path_after"]

    def test_hda_relocked(self, writer_results):
        assert writer_results["hda_matches_def"]


# ---------------------------------------------------------------------------
# Group 3: End-to-end — package via save_portable_hip, execute, verify output
# ---------------------------------------------------------------------------

class TestEndToEndCache:
    """Full pipeline: HDA scene -> save_portable_hip -> run_cache.sh -> .bgeo.sc."""

    def test_package_and_execute(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_json = os.path.join(tmpdir, "results.json")
            repo = _repo_root()
            hda_path = os.path.join(repo, "hda", "remote_file_cache.hdalc")
            shot_root = os.path.join(tmpdir, "package")

            # Phase 1: create scene with HDA, package via hython
            script = textwrap.dedent(f"""\
                import hou, json, sys, os
                sys.path.insert(0, "{repo}")
                from src.cache_scene_writer import save_portable_hip
                from src.cache_script_writer import write_cache_script

                # Install HDA
                hou.hda.installFile("{hda_path}")
                defs = hou.hda.definitionsInFile("{hda_path}")
                hda_type = defs[0].nodeTypeName()

                # Create scene: box -> HDA
                obj = hou.node("/obj")
                geo = obj.createNode("geo", "test_geo")
                for child in geo.children():
                    child.destroy()
                box = geo.createNode("box", "box1")
                hda_node = geo.createNode(hda_type, "remote_cache1")
                hda_node.setInput(0, box)

                # Configure frame range on internal filecache.
                # Must unlock HDA, delete expressions, set raw values so
                # the portable hip has explicit frame range values.
                fc = hda_node.node("filecache1")
                hda_node.allowEditingOfContents()
                for pname in ("trange", "f1", "f2", "f3"):
                    fc.parm(pname).deleteAllKeyframes()
                fc.parm("trange").set(1)
                fc.parm("f1").set(1)
                fc.parm("f2").set(1)
                fc.parm("f3").set(1)
                # Don't re-lock — save_portable_hip handles lock lifecycle

                # Save initial hip (path reference for save_portable_hip)
                hou.hipFile.save(os.path.join("{tmpdir}", "initial.hip"))

                # Create package directories
                for d in ("Cache", "Scenes", "Scripts"):
                    os.makedirs(os.path.join("{shot_root}", d), exist_ok=True)

                # Save portable hip
                portable_path = os.path.join("{shot_root}", "Scenes", "test.hip")
                save_portable_hip(fc, portable_path)

                # Resolve actual filename (Indie -> .hiplc)
                actual = portable_path
                if not os.path.exists(actual):
                    for ext in (".hiplc", ".hipnc"):
                        alt = portable_path.rsplit(".hip", 1)[0] + ext
                        if os.path.exists(alt):
                            actual = alt
                            break

                hip_filename = os.path.basename(actual)
                cache_node_path = fc.path()

                # Write run_cache.sh
                script_path = os.path.join("{shot_root}", "Scripts", "run_cache.sh")
                write_cache_script(
                    output_path=script_path,
                    shot_name="test",
                    hip_filename=hip_filename,
                    cache_node_path=cache_node_path,
                    frame_start=1,
                    frame_end=1,
                )

                with open("{output_json}", "w") as f:
                    json.dump({{
                        "hip_filename": hip_filename,
                        "cache_node_path": cache_node_path,
                        "script_path": script_path,
                        "portable_exists": os.path.exists(actual),
                    }}, f)
            """)

            rc, stdout, stderr = _run_hython(script)
            assert rc == 0, (
                f"Packaging hython failed (rc={rc}):\n{stdout}\n{stderr}"
            )

            with open(output_json) as f:
                results = json.load(f)
            assert results["portable_exists"], "Portable hip not created"

            # Phase 2: execute run_cache.sh
            env = os.environ.copy()
            hfs = env.get("HFS", "")
            if hfs:
                env["PATH"] = os.path.join(hfs, "bin") + ":" + env.get("PATH", "")

            r = subprocess.run(
                ["bash", results["script_path"]],
                capture_output=True, text=True, timeout=300, env=env,
            )
            assert r.returncode == 0, (
                f"run_cache.sh failed (rc={r.returncode}):\n"
                f"{r.stdout}\n{r.stderr}"
            )

            # Phase 3: verify .bgeo.sc output exists somewhere under Cache/
            cache_dir = os.path.join(shot_root, "Cache")
            bgeo_files = glob.glob(
                os.path.join(cache_dir, "**", "*.bgeo.sc"), recursive=True
            )
            assert bgeo_files, (
                f"No .bgeo.sc files under {cache_dir}.\n"
                f"Tree: {list(os.walk(cache_dir))}\n"
                f"Script output: {r.stdout}\n{r.stderr}"
            )
            for path in bgeo_files:
                assert os.path.getsize(path) > 100, f"{path} too small"
