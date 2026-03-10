# Houdini Remote Render & Cache

A collection of Houdini HDAs that package scenes for remote execution — rendering, simulation caching, and more.

## Installation

**Linux / macOS:**
```bash
curl -fsSL https://raw.githubusercontent.com/kleer001/houdini_remote_render/main/scripts/bootstrap.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/kleer001/houdini_remote_render/main/scripts/bootstrap.ps1 | iex
```

The script checks for prerequisites (git, Python 3, Houdini), clones the repo, and registers the HDAs using Houdini's [package system](https://www.sidefx.com/docs/houdini/ref/plugins.html). If anything is missing it tells you exactly what to install and how. No files are copied — HDAs are loaded directly from the repository.

Restart Houdini after installing. The HDAs appear in the Tab menu:
- **Karma USD Packager** — any LOP network
- **Remote File Cache** — any SOP network

### Prerequisites

The bootstrap script handles all of this, but if you're setting things up by hand:

- **Houdini 21.0+** (Indie or Commercial) — must be launched at least once so the preferences directory exists
- **Git** — [git-scm.com](https://git-scm.com/) or your OS package manager
- **Python 3.10+** — your OS package manager, or Houdini's bundled Python (`$HFS/python/bin/python3`)

<details>
<summary>Manual installation (without the bootstrap script)</summary>

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

## Updating

HDAs load directly from the cloned repo, so updating is just a `git pull`:

```bash
cd /path/to/houdini_remote_render
git pull
```

Restart Houdini to pick up any changes.

## HDAs

<details>
<summary>Karma USD Packager (LOP)</summary>

Packages a Solaris/LOP stage into a self-contained USDZ archive for remote rendering.

- **Context:** LOPs (Solaris)
- **File:** `hda/karma_usd_packager.hdalc`
- **Node color:** Deep red (X shape)

Takes a LOP stage and produces:
- A flattened `.usdz` archive with all textures bundled
- A thin `.usda` wrapper that references the USDZ and any external caches
- A human-readable manifest documenting what was packaged
- A `render_info.txt` with frame range and USD filename for farm scripts

The HDA is a pass-through node — it doesn't modify your live stage. Drop it between your scene and your Karma ROP, set a shot name, and hit Package.

**Usage:**
1. Wire the node into your LOP network before your Karma ROP
2. Set the **Shot Name** (and pod/team/version)
3. Click **Verify** to dry-run and check for issues
4. Click **Package** to produce the USDZ, wrapper, and manifest

**Output structure** (`$HIP/{shot_name}_P{pod}T{team}_v{NNN}/`):
```
Output/              — Rendered frames land here
Textures/            — Converted textures
Cache/               — External caches (VDB, bgeo.sc, Alembic)
Scenes/              — USDZ archive + .usda wrapper
render_info.txt      — Frame range and USD filename for farm scripts
{shot}_manifest.txt  — Human-readable report
{shot}.hip.zip       — HIP backup
```

</details>

<details>
<summary>Remote File Cache (SOP)</summary>

Wraps a File Cache SOP with remote packaging. Use it as a drop-in replacement for File Cache — same parameters, same workflow — plus a "Package for Remote" button that bundles everything needed to run the cache on another machine via `hbatch`.

- **Context:** SOPs
- **File:** `hda/remote_file_cache.hdalc`
- **Node color:** Amber

Produces:
- A portable `.hip` file with cache output paths rewritten for the remote folder structure
- A `run_cache.sh` script that executes the cache via `hbatch`
- A `cache_info.txt` with frame range, node path, and format metadata
- A human-readable manifest
- A zip backup of the original `.hip`

**Usage:**
1. Drop the node into your SOP network (replaces a File Cache SOP)
2. Wire your geometry into it, configure caching as normal
3. Go to the **Remote Package** tab, set **Shot Name** (and pod/team/version)
4. Click **Verify**, then **Package for Remote**
5. Upload the output folder to your remote machine and run `Scripts/run_cache.sh`

**Output structure** (`$HIP/{shot_name}_P{pod}T{team}_v{NNN}/`):
```
Cache/               — Cache output lands here when run remotely
Scenes/              — Portable .hip file
Scripts/             — hbatch launch script (run_cache.sh)
cache_info.txt       — Machine-readable metadata
{shot}_manifest.txt  — Human-readable report
{shot}_original.hip.zip — HIP backup
```

</details>

### Mantra / Redshift ROPs (planned)

Remote packaging for Mantra and Redshift render jobs. Coming soon.

## License

[MIT](LICENSE)
