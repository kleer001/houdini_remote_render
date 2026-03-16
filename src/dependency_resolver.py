"""Resolve upstream cache dependencies for a Karma USD Packager node.

Discovers Remote File Cache nodes upstream of a LOP render packager —
both through direct wiring and "virtual wires" (Object Merge, file-on-disk
coupling, expression references, code scanning). Builds a DAG of cacheable
units and topologically sorts them for correct execution order.

All discovery functions require ``hou`` (imported lazily inside functions).
The DAG data structures and topological sort are pure Python — CI-testable
without Houdini.
"""

import re
from dataclasses import dataclass, field


@dataclass
class CacheableUnit:
    """A single cache job discovered in the dependency graph."""

    node_path: str
    """Houdini node path, e.g. ``/obj/geo1/remote_cache1``."""

    filecache_path: str = ""
    """Path to the internal filecache node (inside the HDA)."""

    node_type: str = ""
    """Node type name, e.g. ``remote_file_cache``."""

    output_path: str = ""
    """Resolved cache output path (for file-coupling detection)."""

    label: str = ""
    """Human-readable label for display."""

    frame_start: int = 1
    frame_end: int = 1
    frame_inc: int = 1

    file_type: str = ".bgeo.sc"

    dependencies: list[str] = field(default_factory=list)
    """Node paths of other CacheableUnits this unit depends on."""


@dataclass
class VirtualWire:
    """A dependency edge not represented by a visible network wire."""

    source: str
    """Node path of the dependency (upstream)."""

    target: str
    """Node path of the dependent (downstream)."""

    wire_type: str
    """One of: object_merge, file_coupling, expression_ref, code_ref."""

    detail: str = ""
    """Human-readable detail, e.g. parm name or matched path."""


@dataclass
class DependencyDAG:
    """Complete dependency graph for a packaging operation."""

    cache_units: dict[str, CacheableUnit] = field(default_factory=dict)
    """Keyed by node_path."""

    execution_order: list[str] = field(default_factory=list)
    """Topologically sorted node_paths (dependencies first)."""

    render_node_path: str = ""
    """The Karma packager node that triggered the resolve."""

    virtual_wires: list[VirtualWire] = field(default_factory=list)

    warnings: list[str] = field(default_factory=list)


class CyclicDependencyError(Exception):
    """Raised when the dependency graph contains a cycle."""


def topological_sort(units: dict[str, CacheableUnit]) -> list[str]:
    """Return node_paths in execution order (dependencies first).

    Uses Kahn's algorithm (BFS). Raises ``CyclicDependencyError`` if the
    graph contains a cycle.

    Args:
        units: Mapping of node_path -> CacheableUnit. Each unit's
            ``dependencies`` list contains node_paths of units it depends on.
            Dependencies referencing paths not in *units* are silently ignored.

    Returns:
        List of node_paths in topological order.
    """
    if not units:
        return []

    # Build adjacency list and in-degree map.
    # Edge: dependency -> dependent (dependency must run first).
    in_degree: dict[str, int] = {path: 0 for path in units}
    dependents: dict[str, list[str]] = {path: [] for path in units}

    for path, unit in units.items():
        for dep in unit.dependencies:
            if dep not in units:
                continue
            in_degree[path] += 1
            dependents[dep].append(path)

    # Seed queue with nodes that have no dependencies.
    queue = [path for path, deg in in_degree.items() if deg == 0]
    # Sort for deterministic output when multiple nodes have the same
    # in-degree (makes tests stable).
    queue.sort()

    result: list[str] = []

    while queue:
        node = queue.pop(0)
        result.append(node)
        for dep in sorted(dependents[node]):
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)

    if len(result) != len(units):
        sorted_set = set(result)
        cycle_members = [p for p in units if p not in sorted_set]
        raise CyclicDependencyError(
            f"Cyclic dependency among: {', '.join(cycle_members)}"
        )

    return result


def build_dag(
    cache_units: dict[str, CacheableUnit],
    virtual_wires: list[VirtualWire] | None = None,
    render_node_path: str = "",
    warnings: list[str] | None = None,
) -> DependencyDAG:
    """Build a DependencyDAG from discovered cache units.

    Computes the topological sort. Raises ``CyclicDependencyError`` on cycles.

    Args:
        cache_units: Discovered cacheable units keyed by node_path.
        virtual_wires: Optional virtual wire list (for diagnostics).
        render_node_path: Path of the Karma packager node.
        warnings: Optional discovery warnings.

    Returns:
        A fully populated DependencyDAG.
    """
    execution_order = topological_sort(cache_units)

    return DependencyDAG(
        cache_units=cache_units,
        execution_order=execution_order,
        render_node_path=render_node_path,
        virtual_wires=virtual_wires or [],
        warnings=warnings or [],
    )


def format_dag_summary(dag: DependencyDAG) -> str:
    """Format the DAG as a human-readable summary for the verify log.

    Returns a multi-line string suitable for display in the HDA's log output.
    """
    lines: list[str] = []
    n = len(dag.execution_order)

    if n == 0:
        lines.append("  No upstream cache jobs found.")
        return "\n".join(lines)

    lines.append(f"  Found {n} cache job(s):")
    lines.append("")

    for i, path in enumerate(dag.execution_order, 1):
        unit = dag.cache_units[path]
        lines.append(f"  {i}. {unit.node_path}")
        lines.append(
            f"     frames {unit.frame_start}-{unit.frame_end}, "
            f"{unit.file_type}"
        )
        if unit.dependencies:
            dep_labels = []
            for dep_path in unit.dependencies:
                dep_unit = dag.cache_units.get(dep_path)
                if dep_unit:
                    dep_labels.append(dep_unit.label or dep_path.rsplit("/", 1)[-1])
                else:
                    dep_labels.append(dep_path)
            lines.append(f"     depends on: {', '.join(dep_labels)}")

    if dag.virtual_wires:
        lines.append("")
        lines.append("  Virtual wires:")
        for vw in dag.virtual_wires:
            src_label = vw.source.rsplit("/", 1)[-1]
            tgt_label = vw.target.rsplit("/", 1)[-1]
            detail = f" ({vw.detail})" if vw.detail else ""
            lines.append(
                f"     {tgt_label} -> {src_label} ({vw.wire_type}{detail})"
            )

    total = n + 1  # caches + render
    lines.append("")
    lines.append("  Execution order:")
    for i, path in enumerate(dag.execution_order, 1):
        unit = dag.cache_units[path]
        label = unit.label or path.rsplit("/", 1)[-1]
        lines.append(f"     {i}. Cache: {label}")
    lines.append(f"     {total}. Render")

    if dag.warnings:
        lines.append("")
        lines.append("  Warnings:")
        for w in dag.warnings:
            lines.append(f"     ! {w}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Path normalization (pure Python, CI-testable)
# ---------------------------------------------------------------------------

# Common cache file extensions, longest first to avoid partial matches.
_CACHE_EXTENSIONS = (
    ".bgeo.sc", ".bgeo.gz", ".bgeo.lzma", ".bgeo",
    ".vdb", ".abc", ".usd", ".usdc", ".usda",
)

_FRAME_PATTERN = re.compile(
    r"(?:\.\$F\d*|\.\d{3,}|\.#+)$"
)


def normalize_cache_path(path: str) -> str:
    """Strip frame numbers and extension to get a base pattern for matching.

    >>> normalize_cache_path("/tmp/cache/fluid/fluid.0001.bgeo.sc")
    '/tmp/cache/fluid/fluid'
    >>> normalize_cache_path("/tmp/cache/fluid/fluid.$F4.bgeo.sc")
    '/tmp/cache/fluid/fluid'
    """
    for ext in _CACHE_EXTENSIONS:
        if path.endswith(ext):
            path = path[: -len(ext)]
            break
    return _FRAME_PATTERN.sub("", path)


# ---------------------------------------------------------------------------
# Discovery functions (require hou — imported lazily)
# ---------------------------------------------------------------------------

_MAX_WALK_DEPTH = 50


def resolve_dependencies(karma_node) -> DependencyDAG:
    """Discover all upstream cache dependencies for a Karma packager node.

    Walks the LOP network, crosses into SOPs via SOP Import / SOP Create,
    expands via virtual wires, and builds a dependency DAG of cacheable units.

    Args:
        karma_node: The Karma USD Packager ``hou.LopNode``.

    Returns:
        A :class:`DependencyDAG` with cache units in execution order.
    """
    warnings: list[str] = []

    # Ring 1: Walk LOP inputs
    lop_nodes: set = set()
    _walk_inputs(karma_node, lop_nodes)

    # Ring 2: Find SOP entry points from LOPs
    sop_entry_points = _find_sop_references(lop_nodes, warnings)

    # Ring 3: Walk SOP inputs from each entry point
    all_sop_nodes: set = set()
    for sop in sop_entry_points:
        _walk_inputs(sop, all_sop_nodes)

    # Ring 4a: Expand via Object Merge references (adds nodes + wires)
    virtual_wires = _expand_object_merges(all_sop_nodes)

    # Ring 4b: Detect remaining virtual wires (edges only, no new nodes)
    virtual_wires.extend(_detect_file_coupling_wires(all_sop_nodes))
    virtual_wires.extend(
        _detect_expression_ref_wires(all_sop_nodes, warnings)
    )
    virtual_wires.extend(_detect_code_ref_wires(all_sop_nodes, warnings))

    # Ring 5: Find cache nodes
    cache_units = _find_cache_nodes(all_sop_nodes)

    if not cache_units:
        return build_dag({}, virtual_wires, karma_node.path(), warnings)

    # Determine inter-cache dependencies
    _resolve_inter_cache_deps(cache_units, all_sop_nodes, virtual_wires)

    return build_dag(cache_units, virtual_wires, karma_node.path(), warnings)


def _walk_inputs(node, visited: set, depth: int = 0) -> None:
    """Recursively walk wired inputs, collecting all nodes."""
    if depth > _MAX_WALK_DEPTH or node in visited:
        return
    visited.add(node)
    for inp in node.inputs():
        if inp is not None:
            _walk_inputs(inp, visited, depth + 1)


def _find_sop_references(lop_nodes: set, warnings: list[str]) -> set:
    """Find SOP nodes referenced by the discovered LOP nodes."""
    import hou

    sop_nodes: set = set()

    for node in lop_nodes:
        type_name = node.type().name()

        if type_name == "sopimport":
            parm = node.parm("soppath")
            if parm:
                ref = parm.evalAsNode()
                if ref is not None:
                    sop_nodes.add(ref)

        elif type_name in ("sopcreate", "sopmodify"):
            # Embedded SOP subnet — collect children that are SOPs.
            for child in node.children():
                if child.type().category() == hou.sopNodeTypeCategory():
                    sop_nodes.add(child)

    return sop_nodes


def _expand_object_merges(sop_nodes: set) -> list[VirtualWire]:
    """Follow Object Merge references, expanding *sop_nodes* in-place.

    Returns virtual wires for every Object Merge -> referenced node edge.
    Iterates until no new nodes are discovered.
    """
    wires: list[VirtualWire] = []
    processed: set[str] = set()

    for _ in range(_MAX_WALK_DEPTH):
        to_process = [
            n for n in sop_nodes
            if n.type().name() == "object_merge"
            and n.path() not in processed
        ]
        if not to_process:
            break

        new_nodes: set = set()
        for om_node in to_process:
            processed.add(om_node.path())
            num_obj = om_node.parm("numobj")
            if num_obj is None:
                continue
            for i in range(1, int(num_obj.eval()) + 1):
                parm = om_node.parm(f"objpath{i}")
                if parm is None:
                    continue
                ref_node = parm.evalAsNode()
                if ref_node is None:
                    continue
                wires.append(VirtualWire(
                    source=ref_node.path(),
                    target=om_node.path(),
                    wire_type="object_merge",
                    detail=f"objpath{i}",
                ))
                if ref_node not in sop_nodes:
                    new_nodes.add(ref_node)

        if not new_nodes:
            break

        for node in new_nodes:
            _walk_inputs(node, sop_nodes)

    return wires


def _detect_file_coupling_wires(sop_nodes: set) -> list[VirtualWire]:
    """Detect File Cache write -> File SOP read on the same path pattern."""
    wires: list[VirtualWire] = []

    # Collect writers (filecache / remote_file_cache output paths).
    writers: dict[str, str] = {}  # normalized_path -> node_path
    # Collect readers (File SOP input paths).
    readers: dict[str, str] = {}

    for node in sop_nodes:
        type_name = node.type().name()

        if type_name.startswith("filecache"):
            parm = node.parm("sopoutput")
            if parm:
                norm = normalize_cache_path(parm.eval())
                if norm:
                    writers[norm] = node.path()

        elif type_name == "remote_file_cache":
            fc = node.node("filecache1")
            if fc:
                parm = fc.parm("sopoutput")
                if parm:
                    norm = normalize_cache_path(parm.eval())
                    if norm:
                        writers[norm] = node.path()

        elif type_name == "file":
            parm = node.parm("file")
            if parm:
                norm = normalize_cache_path(parm.eval())
                if norm:
                    readers[norm] = node.path()

    for norm_path, reader_path in readers.items():
        if norm_path in writers:
            writer_path = writers[norm_path]
            wires.append(VirtualWire(
                source=writer_path,
                target=reader_path,
                wire_type="file_coupling",
                detail=norm_path,
            ))

    return wires


# Regex for HScript channel references: ch("path"), chs("path"), etc.
_CH_PATTERN = re.compile(r"""ch[sfie]?\(\s*["']([^"']+)["']\s*\)""")


def _detect_expression_ref_wires(
    sop_nodes: set,
    warnings: list[str],
) -> list[VirtualWire]:
    """Detect cross-network ch()/chs() expression references."""
    import hou

    wires: list[VirtualWire] = []

    for node in sop_nodes:
        node_obj_root = _get_obj_container(node)

        for parm in node.parms():
            try:
                expr = parm.expression()
            except hou.OperationFailed:
                continue

            for match in _CH_PATTERN.findall(expr):
                # Extract node path (strip the trailing parm name).
                parts = match.rsplit("/", 1)
                if len(parts) < 2:
                    continue
                ref_node_path = parts[0]

                # Resolve the path.
                if ref_node_path.startswith("/"):
                    ref_node = hou.node(ref_node_path)
                else:
                    ref_node = node.node(ref_node_path)

                if ref_node is None or ref_node.path() == node.path():
                    continue

                # Only track cross-OBJ-container references — same-network
                # refs are already captured by wired connections.
                ref_obj_root = _get_obj_container(ref_node)
                if ref_obj_root == node_obj_root:
                    continue

                wires.append(VirtualWire(
                    source=ref_node.path(),
                    target=node.path(),
                    wire_type="expression_ref",
                    detail=f"{parm.name()}: {expr[:60]}",
                ))

    return wires


def _get_obj_container(node):
    """Walk up to the /obj/ child level and return that container node."""
    while node is not None:
        parent = node.parent()
        if parent is not None and parent.path() == "/obj":
            return node
        node = parent
    return None


# Regex for op: references in VEX and hou.node() in Python.
_OP_PATTERN = re.compile(r"""op:(/[^\s"'`,\)]+)""")
_HOU_NODE_PATTERN = re.compile(r"""hou\.node\(\s*["']([^"']+)["']\s*\)""")


def _detect_code_ref_wires(
    sop_nodes: set,
    warnings: list[str],
) -> list[VirtualWire]:
    """Scan wrangle snippets and Python SOPs for node references."""
    import hou

    wires: list[VirtualWire] = []

    for node in sop_nodes:
        type_name = node.type().name()
        code = None

        if type_name == "attribwrangle":
            parm = node.parm("snippet")
            if parm:
                code = parm.eval()
        elif type_name == "python":
            parm = node.parm("python")
            if parm:
                code = parm.eval()

        if not code:
            continue

        # op: references (VEX and Python)
        for match in _OP_PATTERN.findall(code):
            ref_node = hou.node(match)
            if ref_node is not None and ref_node.path() != node.path():
                wires.append(VirtualWire(
                    source=ref_node.path(),
                    target=node.path(),
                    wire_type="code_ref",
                    detail=f"op:{match}",
                ))

        # hou.node() references (Python SOPs only)
        if type_name == "python":
            for match in _HOU_NODE_PATTERN.findall(code):
                ref_node = hou.node(match)
                if ref_node is not None and ref_node.path() != node.path():
                    wires.append(VirtualWire(
                        source=ref_node.path(),
                        target=node.path(),
                        wire_type="code_ref",
                        detail=f'hou.node("{match}")',
                    ))

    return wires


def _find_cache_nodes(sop_nodes: set) -> dict[str, CacheableUnit]:
    """Filter *sop_nodes* for Remote File Cache HDA instances."""
    units: dict[str, CacheableUnit] = {}

    for node in sop_nodes:
        if not node.type().name().startswith("remote_file_cache"):
            continue

        fc = node.node("filecache1")
        if fc is None:
            continue

        units[node.path()] = CacheableUnit(
            node_path=node.path(),
            filecache_path=fc.path(),
            node_type=node.type().name(),
            output_path=fc.parm("sopoutput").eval(),
            label=node.name(),
            frame_start=int(fc.parm("f1").eval()),
            frame_end=int(fc.parm("f2").eval()),
            frame_inc=int(fc.parm("f3").eval()),
            file_type=fc.parm("filetype").evalAsString(),
        )

    return units


def _resolve_inter_cache_deps(
    cache_units: dict[str, CacheableUnit],
    sop_nodes: set,
    virtual_wires: list[VirtualWire],
) -> None:
    """Determine dependency order among cache nodes via BFS.

    For each cache node, walks upstream through wired inputs and virtual
    wire sources.  Other cache nodes encountered are recorded as direct
    dependencies (BFS stops at cache boundaries to avoid transitivity).

    Mutates *cache_units* in-place, populating ``dependencies``.
    """
    import hou

    cache_paths = set(cache_units.keys())

    # Build upstream adjacency: node_path -> set of upstream paths.
    upstream: dict[str, set[str]] = {}
    for node in sop_nodes:
        ups: set[str] = set()
        for inp in node.inputs():
            if inp is not None:
                ups.add(inp.path())
        upstream[node.path()] = ups

    # Add virtual wire edges (target depends on source).
    for vw in virtual_wires:
        upstream.setdefault(vw.target, set()).add(vw.source)

    # BFS from each cache node.
    for cache_path in cache_paths:
        deps: set[str] = set()
        visited: set[str] = set()

        # Seed with direct upstream nodes of the cache node.
        queue: list[str] = list(upstream.get(cache_path, []))

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            if current in cache_paths:
                deps.add(current)
                continue  # Don't traverse past another cache node.

            # Continue BFS upstream.
            queue.extend(upstream.get(current, []))

        cache_units[cache_path].dependencies = sorted(deps)
