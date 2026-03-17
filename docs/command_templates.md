# Command Templates

What each HDA's packaging pipeline produces on disk — the directory layout, shell scripts, and the commands inside them.

---

## Package Directory Layout

All packagers create the same root structure: `$HIP/{shot}_P{pod}T{team}_v{NNN}/`

```
Karma / Redshift (LOP, with upstream caches):

    {shot}_P1T1_v001/
    ├── render_info.txt
    ├── manifest.txt
    ├── Output/                  # render frames land here
    ├── Textures/                # gathered + converted textures
    ├── Cache/                   # upstream cache output (if any)
    ├── Scenes/
    │   ├── {shot}_wrapper.usda  # thin wrapper → USDZ
    │   ├── {shot}.usdz          # flattened stage + textures
    │   └── {shot}_portable.hiplc  # (only if caches bundled)
    └── Scripts/
        ├── run_render.sh        # husk or redshiftUsdCmdLine
        ├── run_render.py        # cross-platform Python launcher
        ├── run_cache_001.sh     # (only if caches bundled)
        ├── run_cache_001.py
        ├── run_all.sh           # (only if caches bundled)
        └── run_all.py

Mantra (ROP, standalone):

    {shot}_P1T1_v001/
    ├── render_info.txt
    ├── manifest.txt
    ├── Output/                  # rendered frames
    ├── IFDs/                    # scene description files
    ├── Textures/                # gathered textures
    ├── Scenes/
    │   └── {shot}_portable.hiplc
    └── Scripts/
        ├── run_render.sh        # mantra standalone
        └── run_render.py

File Cache (SOP, standalone):

    {shot}_P1T1_v001/
    ├── cache_info.txt
    ├── manifest.txt
    ├── Cache/                   # cache output
    ├── Scenes/
    │   └── {shot}_portable.hiplc
    └── Scripts/
        ├── run_cache.sh         # hython
        └── run_cache.py
```

---

## Script Commands

Every script follows the same preamble:

```bash
set -e
cd "$(dirname "$0")/.."          # → package root
source $HFS/houdini_setup_bash   # (or Redshift env block)
```

### Karma — `run_render.sh`

**Command:** `husk`
**CWD at execution:** `Scenes/` (so `../Output/` resolves correctly)
**Requires:** Houdini license (husk)

```bash
cd Scenes

husk \
    --renderer BRAY_HdKarma \       # or BRAY_HdKarmaXPU
    --engine cpu \                   # omitted if default; "xpu" for XPU
    --make-output-path \             # auto-create Output/ dirs
    --disable-disk-check \           # Windows UNC/SMB compat
    --headlight none \               # no default headlight
    --restart-delegate 1 \           # restart every frame (sequences)
    --exrmode 1 \                    # optional: modern EXR output
    -f 1001 \                        # start frame
    -n 48 \                          # frame count (NOT end frame)
    -i 1 \                           # frame increment
    "{shot}_wrapper.usda"
```

### Mantra — `run_render.sh`

**Command:** `mantra` (standalone, free render tokens — no Houdini license)
**CWD at execution:** `IFDs/`
**Requires:** Houdini installed (mantra binary), no paid license

```bash
cd IFDs

for frame in $(seq 1001 1 1048); do
    ifd=$(printf "{shot}.%04d.ifd" "$frame")
    echo "Rendering frame $frame: $ifd"
    mantra -V 2a -j 0 -f "$ifd"
done
```

| Flag | Meaning |
|---|---|
| `-V 2a` | Verbose level 2, all message types |
| `-j 0` | Use all available CPU threads |
| `-f` | Input IFD file |

### Redshift — `run_render.sh`

**Command:** `redshiftUsdCmdLine`
**CWD at execution:** `Scenes/` (same as Karma — `../Output/` resolution)
**Requires:** Redshift installed, GPU, no Houdini license

```bash
cd Scenes
mkdir -p ../Output                   # no --make-output-path equivalent

redshiftUsdCmdLine \
    "{shot}_wrapper.usda" \
    -f 1001 \                        # start frame
    -n 48 \                          # frame count (NOT end frame)
    -i 1 \                           # frame increment (if != 1)
    -device all \                    # GPU ordinal or "all"
    -texturecachebudget 8 \          # optional: GB
    -cachepath "/tmp/rs_cache" \     # optional: texture cache dir
    -ocioconfig "/path/config.ocio"  # optional: OCIO config
```

Environment variables set before the command:
```bash
export REDSHIFT_COREDATAPATH=/usr/redshift
export PATH="$REDSHIFT_COREDATAPATH/bin:$PATH"
export LD_LIBRARY_PATH="$REDSHIFT_COREDATAPATH/lib:$LD_LIBRARY_PATH"
```

### File Cache — `run_cache.sh`

**Command:** `hython` (not hbatch — `render` only works with ROPs)
**CWD at execution:** package root (hython loads hip from `Scenes/`)
**Requires:** Houdini license (hython)

```bash
hython -c '
import hou, sys
hou.hipFile.load("Scenes/{shot}_portable.hiplc")
node = hou.node("/obj/geo1/remote_file_cache1/filecache1")
if node is None:
    print("ERROR: Node not found")
    sys.exit(1)
for p in ("trange", "f1", "f2", "f3"):
    node.parm(p).deleteAllKeyframes()
node.parm("trange").set(1)
node.parm("f1").set(1001)
node.parm("f2").set(1048)
node.parm("f3").set(1)
node.parm("execute").pressButton()
'
```

### Orchestration — `run_all.sh`

**Command:** `bash` (sequences other scripts)
**CWD at execution:** package root
**Only generated when:** Karma or Redshift package includes upstream cache dependencies

```bash
# Step 1/3: Cache — ground_scatter
echo "--- [1/3] Cache: ground_scatter ---"
bash "Scripts/run_cache_001.sh"

# Step 2/3: Cache — fluid_sim
echo "--- [2/3] Cache: fluid_sim ---"
bash "Scripts/run_cache_002.sh"

# Step 3/3: Render
echo "--- [3/3] Render ---"
bash "Scripts/run_render.sh"
```

Serial execution, `set -e` for fail-fast. Cache order follows topological sort from `dependency_resolver.py`.

---

## Cross-Platform Python Launchers

Every `.sh` script has a matching `.py` launcher (e.g. `run_render.py`). These are copied from `src/launchers/` and detect the platform at runtime — on Linux/macOS they `exec bash` the `.sh` script, on Windows they translate to the equivalent subprocess calls.
