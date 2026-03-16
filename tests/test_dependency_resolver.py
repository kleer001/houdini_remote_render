"""Tests for dependency_resolver — DAG structures and topological sort.

Pure Python, no Houdini dependency. CI-safe.
"""

import pytest

from src.dependency_resolver import (
    CacheableUnit,
    CyclicDependencyError,
    DependencyDAG,
    VirtualWire,
    build_dag,
    format_dag_summary,
    normalize_cache_path,
    topological_sort,
)


# ---------------------------------------------------------------------------
# topological_sort
# ---------------------------------------------------------------------------

class TestTopologicalSort:

    def test_empty(self):
        assert topological_sort({}) == []

    def test_single_node_no_deps(self):
        units = {"/obj/geo/fc1": CacheableUnit(node_path="/obj/geo/fc1")}
        assert topological_sort(units) == ["/obj/geo/fc1"]

    def test_linear_chain(self):
        """A -> B -> C: A must run first, then B, then C."""
        units = {
            "/a": CacheableUnit(node_path="/a", dependencies=[]),
            "/b": CacheableUnit(node_path="/b", dependencies=["/a"]),
            "/c": CacheableUnit(node_path="/c", dependencies=["/b"]),
        }
        result = topological_sort(units)
        assert result == ["/a", "/b", "/c"]

    def test_diamond(self):
        """A -> B, A -> C, B -> D, C -> D."""
        units = {
            "/a": CacheableUnit(node_path="/a"),
            "/b": CacheableUnit(node_path="/b", dependencies=["/a"]),
            "/c": CacheableUnit(node_path="/c", dependencies=["/a"]),
            "/d": CacheableUnit(node_path="/d", dependencies=["/b", "/c"]),
        }
        result = topological_sort(units)
        assert result[0] == "/a"
        assert result[-1] == "/d"
        assert result.index("/b") < result.index("/d")
        assert result.index("/c") < result.index("/d")

    def test_independent_nodes(self):
        """Two nodes with no relationship — both valid, deterministic order."""
        units = {
            "/x": CacheableUnit(node_path="/x"),
            "/y": CacheableUnit(node_path="/y"),
        }
        result = topological_sort(units)
        assert set(result) == {"/x", "/y"}
        # Deterministic: sorted alphabetically when equal in-degree.
        assert result == ["/x", "/y"]

    def test_cycle_raises(self):
        """A -> B -> A should raise CyclicDependencyError."""
        units = {
            "/a": CacheableUnit(node_path="/a", dependencies=["/b"]),
            "/b": CacheableUnit(node_path="/b", dependencies=["/a"]),
        }
        with pytest.raises(CyclicDependencyError, match="Cyclic dependency"):
            topological_sort(units)

    def test_self_cycle_raises(self):
        units = {
            "/a": CacheableUnit(node_path="/a", dependencies=["/a"]),
        }
        with pytest.raises(CyclicDependencyError):
            topological_sort(units)

    def test_three_node_cycle_raises(self):
        units = {
            "/a": CacheableUnit(node_path="/a", dependencies=["/c"]),
            "/b": CacheableUnit(node_path="/b", dependencies=["/a"]),
            "/c": CacheableUnit(node_path="/c", dependencies=["/b"]),
        }
        with pytest.raises(CyclicDependencyError):
            topological_sort(units)

    def test_ignores_external_dependencies(self):
        """Dependencies referencing paths not in the units dict are skipped."""
        units = {
            "/a": CacheableUnit(node_path="/a", dependencies=["/nonexistent"]),
        }
        assert topological_sort(units) == ["/a"]

    def test_mixed_external_and_real_deps(self):
        units = {
            "/a": CacheableUnit(node_path="/a"),
            "/b": CacheableUnit(
                node_path="/b", dependencies=["/a", "/external"]
            ),
        }
        result = topological_sort(units)
        assert result == ["/a", "/b"]

    def test_wide_fan_in(self):
        """Many nodes feeding into one."""
        deps = {
            f"/src{i}": CacheableUnit(node_path=f"/src{i}")
            for i in range(5)
        }
        deps["/sink"] = CacheableUnit(
            node_path="/sink",
            dependencies=[f"/src{i}" for i in range(5)],
        )
        result = topological_sort(deps)
        assert result[-1] == "/sink"
        assert set(result[:-1]) == {f"/src{i}" for i in range(5)}


# ---------------------------------------------------------------------------
# build_dag
# ---------------------------------------------------------------------------

class TestBuildDag:

    def test_empty(self):
        dag = build_dag({})
        assert dag.execution_order == []
        assert dag.cache_units == {}

    def test_single_unit(self):
        units = {"/a": CacheableUnit(node_path="/a", label="fluid")}
        dag = build_dag(units, render_node_path="/karma")
        assert dag.execution_order == ["/a"]
        assert dag.render_node_path == "/karma"

    def test_preserves_virtual_wires(self):
        units = {"/a": CacheableUnit(node_path="/a")}
        vw = VirtualWire(
            source="/a", target="/b", wire_type="object_merge", detail="objpath1"
        )
        dag = build_dag(units, virtual_wires=[vw])
        assert len(dag.virtual_wires) == 1
        assert dag.virtual_wires[0].wire_type == "object_merge"

    def test_preserves_warnings(self):
        units = {"/a": CacheableUnit(node_path="/a")}
        dag = build_dag(units, warnings=["something odd"])
        assert dag.warnings == ["something odd"]

    def test_cycle_propagates(self):
        units = {
            "/a": CacheableUnit(node_path="/a", dependencies=["/b"]),
            "/b": CacheableUnit(node_path="/b", dependencies=["/a"]),
        }
        with pytest.raises(CyclicDependencyError):
            build_dag(units)

    def test_dag_with_dependencies(self):
        units = {
            "/fluid": CacheableUnit(node_path="/fluid", label="fluid"),
            "/mesh": CacheableUnit(
                node_path="/mesh", label="mesh", dependencies=["/fluid"]
            ),
            "/scatter": CacheableUnit(node_path="/scatter", label="scatter"),
        }
        dag = build_dag(units, render_node_path="/karma")
        assert dag.execution_order.index("/fluid") < dag.execution_order.index("/mesh")
        assert len(dag.execution_order) == 3


# ---------------------------------------------------------------------------
# format_dag_summary
# ---------------------------------------------------------------------------

class TestFormatDagSummary:

    def test_empty_dag(self):
        dag = DependencyDAG()
        text = format_dag_summary(dag)
        assert "No upstream cache jobs found" in text

    def test_single_cache(self):
        dag = build_dag(
            {"/obj/geo/fc": CacheableUnit(
                node_path="/obj/geo/fc",
                label="fluid",
                frame_start=1,
                frame_end=240,
                file_type=".bgeo.sc",
            )},
            render_node_path="/karma",
        )
        text = format_dag_summary(dag)
        assert "1 cache job" in text
        assert "fluid" in text
        assert "1-240" in text
        assert "Render" in text

    def test_shows_dependencies(self):
        dag = build_dag({
            "/a": CacheableUnit(node_path="/a", label="sim"),
            "/b": CacheableUnit(
                node_path="/b", label="mesh", dependencies=["/a"]
            ),
        })
        text = format_dag_summary(dag)
        assert "depends on: sim" in text

    def test_shows_virtual_wires(self):
        dag = build_dag(
            {"/a": CacheableUnit(node_path="/a", label="src")},
            virtual_wires=[
                VirtualWire(
                    source="/a", target="/b",
                    wire_type="object_merge", detail="objpath1",
                )
            ],
        )
        text = format_dag_summary(dag)
        assert "Virtual wires" in text
        assert "object_merge" in text

    def test_shows_warnings(self):
        dag = build_dag(
            {"/a": CacheableUnit(node_path="/a")},
            warnings=["unparseable expression on /obj/geo/fc.basedir"],
        )
        text = format_dag_summary(dag)
        assert "Warnings" in text
        assert "unparseable" in text

    def test_execution_order_numbered(self):
        dag = build_dag({
            "/a": CacheableUnit(node_path="/a", label="first"),
            "/b": CacheableUnit(
                node_path="/b", label="second", dependencies=["/a"]
            ),
        })
        text = format_dag_summary(dag)
        assert "1. Cache: first" in text
        assert "2. Cache: second" in text
        assert "3. Render" in text


# ---------------------------------------------------------------------------
# normalize_cache_path
# ---------------------------------------------------------------------------

class TestNormalizeCachePath:

    def test_bgeo_sc_with_frame_number(self):
        assert (
            normalize_cache_path("/tmp/cache/fluid/fluid.0001.bgeo.sc")
            == "/tmp/cache/fluid/fluid"
        )

    def test_bgeo_sc_with_dollar_f4(self):
        assert (
            normalize_cache_path("/tmp/cache/fluid/fluid.$F4.bgeo.sc")
            == "/tmp/cache/fluid/fluid"
        )

    def test_bgeo_sc_with_dollar_f(self):
        assert (
            normalize_cache_path("/tmp/cache/fluid/fluid.$F.bgeo.sc")
            == "/tmp/cache/fluid/fluid"
        )

    def test_vdb_with_frame(self):
        assert (
            normalize_cache_path("/data/sim/smoke.0100.vdb")
            == "/data/sim/smoke"
        )

    def test_abc_with_frame(self):
        assert (
            normalize_cache_path("/data/geo/mesh.001001.abc")
            == "/data/geo/mesh"
        )

    def test_hash_frame_pattern(self):
        assert (
            normalize_cache_path("/tmp/cache/name.####.bgeo.sc")
            == "/tmp/cache/name"
        )

    def test_no_frame_no_extension(self):
        assert normalize_cache_path("/tmp/plain") == "/tmp/plain"

    def test_extension_only_no_frame(self):
        assert (
            normalize_cache_path("/tmp/cache/static.bgeo.sc")
            == "/tmp/cache/static"
        )

    def test_short_number_not_stripped(self):
        """Numbers with fewer than 3 digits are NOT frame patterns."""
        assert (
            normalize_cache_path("/tmp/cache/v01.bgeo.sc")
            == "/tmp/cache/v01"
        )
