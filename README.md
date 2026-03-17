<p align="center">
  <img src="logos/banner_light_v6_svgrepo.svg" alt="Houdini Remote Render — Package it. Ship it. Render it." width="700"/>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"/></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10+-green.svg" alt="Python 3.10+"/></a>
  <a href="https://img.shields.io/badge/MCP-Compatible-8A2BE2.svg"><img src="https://img.shields.io/badge/MCP-Compatible-8A2BE2.svg" alt="MCP Compatible"/></a>
  <a href="https://www.sidefx.com/products/houdini/"><img src="https://img.shields.io/badge/Houdini-21.0+-orange.svg" alt="Houdini 21.0+"/></a>
</p>
<p align="center">
  <a href="https://github.com/kleer001/houdini_remote_render/commits"><img src="https://img.shields.io/github/last-commit/kleer001/houdini_remote_render.svg" alt="Last Commit"/></a>
  <a href="https://github.com/kleer001/houdini_remote_render/issues"><img src="https://img.shields.io/github/issues/kleer001/houdini_remote_render.svg" alt="Issues"/></a>
  <a href="https://github.com/kleer001/houdini_remote_render/network/members"><img src="https://img.shields.io/github/forks/kleer001/houdini_remote_render.svg" alt="Forks"/></a>
  <a href="https://github.com/kleer001/houdini_remote_render/watchers"><img src="https://img.shields.io/github/watchers/kleer001/houdini_remote_render.svg" alt="Watchers"/></a>
  <a href="https://github.com/kleer001/houdini_remote_render/stargazers"><img src="https://img.shields.io/github/stars/kleer001/houdini_remote_render.svg" alt="GitHub Stars"/></a>
</p>

Package Houdini scenes into self-contained archives that render or cache anywhere — no shared filesystems, no farm managers, no missing textures.

## Install

```bash
# Linux / macOS
curl -fsSL https://raw.githubusercontent.com/kleer001/houdini_remote_render/main/scripts/bootstrap.sh | bash

# Windows (PowerShell)
irm https://raw.githubusercontent.com/kleer001/houdini_remote_render/main/scripts/bootstrap.ps1 | iex
```

Restart Houdini. Four HDAs appear in the Tab menu.

## HDAs

### Karma USD Packager (LOP)

Packages a Solaris/LOP stage into a self-contained USDZ archive for remote rendering with standalone `husk`.

1. Drop **Karma USD Packager** into your LOP network (before your Karma ROP)
2. Set **Shot Name**, click **Verify**, click **Package**
3. Copy the output folder to your render machine and run:

```bash
cd SHOT_NAME_P1T1_v001
bash Scripts/run_render.sh
```

The HDA is pass-through — it doesn't modify your live stage. It audits your scene, auto-converts textures, bundles everything into a USDZ, and generates a `husk` launch script with smart defaults.

### Remote File Cache (SOP)

Drop-in replacement for File Cache SOP with remote packaging. Same parameters, same workflow — plus a **Package for Remote** button that bundles everything needed to run the cache on another machine.

1. Drop **Remote File Cache** into your SOP network (replaces a File Cache SOP)
2. Wire geometry in, configure caching as normal
3. Go to **Remote Package** tab, set **Shot Name**, click **Verify**, click **Package**
4. Copy the output folder to your remote machine and run:

```bash
cd SHOT_NAME_P1T1_v001
bash Scripts/run_cache.sh
```

The portable `.hip` has rewritten cache paths so output lands in the package's `Cache/` directory. The generated script runs `hython` headlessly — no GUI needed.

### Redshift USD Packager (LOP)

Packages a Solaris/LOP stage for remote rendering with standalone `redshiftUsdCmdLine`. Same workflow as the Karma packager — no Houdini license required on the render machine.

1. Drop **Redshift USD Packager** into your LOP network (after your Redshift RenderSettings)
2. Set **Shot Name**, configure GPU/texture settings in the **Redshift** tab, click **Verify**, click **Package**
3. Copy the output folder to your render machine and run:

```bash
cd SHOT_NAME_P1T1_v001
bash Scripts/run_render.sh
```

The packager validates Redshift render settings (`redshift:` attributes), warns about UsdPreviewSurface materials, and generates a `redshiftUsdCmdLine` script with GPU device selection, texture cache, OCIO config, and all confirmed CLI flags.

### Mantra Render Packager (ROP)

Packages a Mantra ROP into self-contained IFD files with embedded geometry and shaders for license-free remote rendering via `mantra` standalone.

1. Drop **Remote Mantra Render** into your ROP network
2. Set **Shot Name**, click **Verify**, click **Package**
3. Copy the output folder to your render machine and run:

```bash
cd SHOT_NAME_P1T1_v001
bash Scripts/run_render.sh
```

IFDs embed geometry and VEX shaders, so the render machine only needs Houdini's free render tokens — no interactive license.

### Combined Cache + Render

When the Karma USD Packager detects upstream Remote File Cache nodes, it offers to bundle everything into one package. Click **Verify** to see the discovered dependency chain, then **Package** to build it all:

```bash
cd SHOT_NAME_P1T1_v001
bash Scripts/run_all.sh    # runs caches in dependency order, then renders
```

The dependency resolver follows both visible wires and "virtual wires" — Object Merge cross-references, file-on-disk coupling, expression references, and code-level `op:` paths — so the execution order is correct for typical production networks.

## Updating

HDAs load directly from the cloned repo:

```bash
cd /path/to/houdini_remote_render
git pull
```

Restart Houdini to pick up changes.

---

<details>
<summary><strong>Why this exists</strong></summary>

Sending a Karma render to another machine shouldn't require Deadline, a shared NFS mount, or 45 minutes of path debugging. Existing tools either:

- **Collect .hip files** but don't understand USD ([HipCollector](https://github.com/Aeoll/HipCollector))
- **Submit husk jobs** but assume shared filesystems ([HuskSubmitter](https://github.com/Tronotrond/HuskSubmitter))
- **Require pipeline infrastructure** (AYON, ShotGrid, Deadline)

This project packages everything into a portable folder: USDZ with bundled textures, a ready-to-run render script with smart defaults, and a manifest documenting what's inside. Copy it via Google Drive, Dropbox, USB stick, `scp`, or carrier pigeon.

</details>

<details>
<summary><strong>What the Karma packager handles</strong></summary>

| Problem | What the packager does |
|---|---|
| `.rat` textures not valid in USDZ | Auto-converts to `.exr` |
| `op:` COP textures are runtime-only | Bakes to PNG via render node |
| `op:` SOP geometry paths | Exports to `.usdc` via temp SOP Import |
| `opdef:` VEX shader URIs | Bakes source into USDZ, restores `opdef:` in wrapper |
| `<UDIM>` patterns can't resolve inside USDZ | Extracts tiles as loose files |
| No lights in scene | Warns that render will be black (husk has no default headlight) |
| Missing AOVs | Warns that husk will render black without Beauty AOV |
| Camera mismatch | Warns if RenderSettings camera doesn't exist |

The generated `run_render.sh` includes smart defaults:

- `--restart-delegate 1` auto-added for frame sequences (prevents memory accumulation)
- `--make-output-path` always included
- `--headlight none` always included (prevents phantom headlight)
- Houdini environment auto-sourced from `$HFS`

</details>

<details>
<summary><strong>Verified render aspects</strong></summary>

All features below have been tested end-to-end: build in Houdini, package with the HDA, render with standalone `husk`, verify output. See [Supported Render Aspects](docs/SUPPORTED_RENDER_ASPECTS.md) for details.

**Textures:** file textures, .rat auto-conversion, UDIM sets, COP procedurals, HDRI environment maps
**Materials:** MaterialX (recommended), UsdPreviewSurface, PrincipledShader (VEX, requires Houdini on render machine)
**Geometry:** volumes (VDB/fog), animated deformation, subdivision surfaces, point instances, Alembic references, time-varying topology, nested instancing
**Lighting:** dome/rect/sphere/spot lights, color temperature, per-object visibility, matte/holdout
**Motion blur:** velocity blur, deformation blur, camera motion blur
**Render script:** single-frame, multi-frame sequences, XPU (MaterialX only), all major husk flags

</details>

<details>
<summary><strong>Output structure</strong></summary>

Both HDAs produce a folder at `$HIP/{shot_name}_P{pod}T{team}_v{NNN}/`:

**Karma USD Packager:**
```
Output/              — Rendered frames land here
Textures/            — Converted textures and UDIM tiles
Cache/               — External caches (VDB, bgeo.sc, Alembic)
Scenes/              — USDZ archive + .usda wrapper
Scripts/             — run_render.sh (husk launcher)
render_info.txt      — Frame range and USD filename
{shot}_manifest.txt  — Human-readable packaging report
{hip_filename}.zip   — HIP backup
```

**Combined cache + render** (when upstream caches are detected):
```
Cache/               — All cache outputs land here
Output/              — Rendered frames
Scenes/              — USDZ + wrapper + portable .hip for caches
Scripts/
  run_all.sh         — Orchestration: caches in order, then render
  run_cache_001_*.sh — Per-cache hython scripts
  run_render.sh      — husk launcher
{shot}_manifest.txt  — Packaging report with dependency chain
```

**Redshift USD Packager:**
```
Output/              — Rendered frames land here
Textures/            — Converted textures and UDIM tiles
Cache/               — External caches (VDB, bgeo.sc, Alembic)
Scenes/              — USDZ archive + .usda wrapper
Scripts/             — run_render.sh (redshiftUsdCmdLine launcher)
render_info.txt      — Frame range, GPU device, USD filename
{shot}_manifest.txt  — Human-readable packaging report
{hip_filename}.zip   — HIP backup
```

**Mantra Render Packager:**
```
Output/              — Rendered frames land here
IFDs/                — Generated IFD files (embedded geometry + shaders)
Textures/            — Gathered textures
Scripts/             — run_render.sh (mantra standalone launcher)
render_info.txt      — Frame range, IFD pattern, engine
{shot}_manifest.txt  — Human-readable packaging report
{shot}_original.hip.zip — HIP backup
```

**Remote File Cache** (standalone):
```
Cache/               — Cache output lands here when run remotely
Scenes/              — Portable .hip file
Scripts/             — run_cache.sh (hython launcher)
cache_info.txt       — Machine-readable metadata
{shot}_manifest.txt  — Human-readable report
{shot}_original.hip.zip — HIP backup
```

</details>

<details>
<summary><strong>Installation details</strong></summary>

### Prerequisites

The bootstrap script handles all of this, but if you're setting things up by hand:

- **Houdini 21.0+** (Indie or Commercial) — must be launched at least once so the preferences directory exists
- **Git** — [git-scm.com](https://git-scm.com/) or your OS package manager
- **Python 3.10+** — your OS package manager, or Houdini's bundled Python (`$HFS/python/bin/python3`)

### Manual installation (without the bootstrap script)

#### Step 1 — Clone the repository

```bash
git clone https://github.com/kleer001/houdini_remote_render.git
cd houdini_remote_render
```

#### Step 2 — Register the HDAs

You have two options. Pick one.

**Option A — Run the installer (recommended):**

```bash
python install.py
```

This auto-detects all Houdini versions on your system and creates a package file for each one.

**Option B — Create the package file by hand:**

Create `houdini_remote_render.json` in your Houdini packages directory:

| OS | Packages directory |
|---|---|
| **Linux** | `~/houdini21.0/packages/` |
| **macOS** | `~/Library/Preferences/houdini/21.0/packages/` |
| **Windows** | `%USERPROFILE%\Documents\houdini21.0\packages\` |

Contents:
```json
{
    "env": [
        {
            "HOUDINI_OTLSCAN_PATH": {
                "value": "/path/to/houdini_remote_render/hda",
                "method": "append"
            }
        }
    ],
    "path": "/path/to/houdini_remote_render"
}
```

Replace `/path/to/houdini_remote_render` with the actual path where you cloned the repo. Create the `packages/` directory if it doesn't exist.

**Alternative — houdini.env (not recommended):**

Add to `$HOUDINI_USER_PREF_DIR/houdini.env`:

```
HOUDINI_OTLSCAN_PATH = /path/to/houdini_remote_render/hda:&
```

The `:&` appends to the existing scan path. On Windows use `;` instead of `:`.

#### Step 3 — Restart Houdini

The HDAs appear in the Tab menu after restarting.

#### Managing an existing install

If you already have the repository cloned:
```bash
python install.py                   # Install for all Houdini versions
python install.py --version 21.0    # Install for a specific version
python install.py --status          # Check install status
python install.py --uninstall       # Remove
```

</details>

<details>
<summary><strong>Recompiling for a different license</strong></summary>

The shipped HDAs use the `.hdalc` (Indie) extension. If you're on a different Houdini license, recompile them with `hotl`:

```bash
cd /path/to/houdini_remote_render/hda

# Commercial / FX  (.hdalc → .hda)
for hda in karma_usd_packager remote_file_cache remote_mantra_render redshift_usd_packager; do
    hotl -l ${hda}.hdalc temp_dir && hotl -c temp_dir ${hda}.hda && rm -rf temp_dir
done

# Apprentice  (.hdalc → .hdanc)
for hda in karma_usd_packager remote_file_cache remote_mantra_render; do
    hotl -l ${hda}.hdalc temp_dir && hotl -c temp_dir ${hda}.hdanc && rm -rf temp_dir
done
```

Then update `HOUDINI_OTLSCAN_PATH` or your package file if necessary — Houdini scans by extension, so the new files will be picked up automatically from the same `hda/` directory. Restart Houdini after recompiling.

`hotl` is in `$HFS/bin/`. Common locations:

| OS | Typical path |
|---|---|
| **Linux** | `/opt/hfs21.0/bin/hotl` |
| **macOS** | `/Applications/Houdini/Current/Frameworks/Houdini.framework/Versions/Current/Resources/bin/hotl` |
| **Windows** | `C:\Program Files\Side Effects Software\Houdini 21.0\bin\hotl.exe` |

If `hotl` is not on your PATH, source the Houdini environment first: `cd $HFS && source houdini_setup_bash` (Linux/macOS) or run the Houdini Command Line Tools shortcut (Windows).

</details>

<details>
<summary><strong>Testing</strong></summary>

```bash
# CI tests (no Houdini required) — 254 tests
pytest -m "not houdini"

# Houdini integration tests (requires $HFS via hython subprocess)
export HFS=/opt/hfs21.0.596
pytest -m "houdini" -v

# All tests
export HFS=/opt/hfs21.0.596
pytest
```

Integration tests create minimal scenes via hython, exercise the full packaging pipeline, execute the generated scripts headlessly, and verify output files. See [Render Integration Tests](docs/render_integration_tests.md) for details.

</details>

<details>
<summary><strong>Documentation</strong></summary>

- [Supported Render Aspects](docs/SUPPORTED_RENDER_ASPECTS.md) — every verified rendering feature with references
- [Pipeline Modules](docs/pipeline_modules.md) — internal module architecture
- [Render Integration Tests](docs/render_integration_tests.md) — automated husk test guide

</details>

## License

[MIT](LICENSE)
