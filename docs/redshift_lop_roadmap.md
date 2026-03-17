# Redshift LOP Packager — Implementation Roadmap

> Remote packaging for Redshift USD render jobs via `redshiftUsdCmdLine`.

## Context

The Karma USD Packager (LOP) packages a Solaris stage into a self-contained
archive with a render launch script. This roadmap covers adapting that pipeline
for Redshift, which renders USD via its own `redshiftUsdCmdLine` tool — no
Houdini or husk required on the render farm.

The Mantra Render Packager (ROP) provides a second reference for how a new
renderer is integrated: a parallel set of `mantra_*.py` modules plus
`hda_scripts_mantra/`.

---

## Verified Findings

> Confirmed via official Maxon documentation and headless Houdini 21.0.631
> testing (2026-03-16). Redshift version: 2026.3.1.

### `redshiftUsdCmdLine` CLI Flags (CONFIRMED)

Source: https://help.maxon.net/r3d/houdini/en-us/Content/html/USD+Command+Line.html

| Flag | Parameter | Default | Description |
|------|-----------|---------|-------------|
| `-f` | number | 1 | Start frame number |
| `-n` | number | 1 | Number of frames to render including start frame |
| `-i` | number | 1 | Frame increment |
| `-device` | ordinal or "all" | default GPU | GPU device selection |
| `-texturecachebudget` | number (GB) | default | Texture cache in GB |
| `-cachepath` | folder path | default | Cache folder |
| `-skippostfx` | (no param) | disabled | Skip post-processing |
| `-ocioconfig` | file path | default | OCIO config file |
| `-ociorenderspace` | string | default | OCIO render space |
| `-ociodisplay` | string | default | OCIO display |
| `-ocioview` | string | default | OCIO view |
| `-oip` | path | USD-defined | Override output image path (ALL AOVs) |
| `-ores` | WxH format | USD-defined | Override resolution |
| `-oro` | file path | none | Render options override file |
| `-V` / `-verbose` | 0-6 | default | Verbosity level |
| `-restart-delegate` | (no param) | disabled | Restart render delegate every frame |
| `-s` / `-settings` | prim path | default | Render settings prim |
| `-c` / `-camera` | prim path | default | Camera prim |
| `-purpose` | comma-sep tokens | "geometry,render" | USD render purpose |
| `-crop` | x y w h | none | Crop region |
| `-list-settings` | (no param) | disabled | List settings prims and exit |
| `-list-cameras` | (no param) | disabled | List cameras and exit |
| `-override-materials` | R G B | none | Override all materials |
| `-disable-scene-lights` | (no param) | disabled | Disable lights |
| `-shutter-open` / `-shutter-close` | number | stage-defined | Motion blur overrides |
| `-hybrid` | 0 or 1 | stage-defined | Hybrid rendering |

### Redshift Environment Variables (CONFIRMED)

| Variable | Description |
|----------|-------------|
| `REDSHIFT_COREDATAPATH` | Core install path (default `/usr/redshift` on Linux) |
| `REDSHIFT_LOCALDATAPATH` | Local data path (default `~/redshift`) |
| `REDSHIFT_LICENSEPATH` | License file search path |
| `REDSHIFT_GPUDEVICES` | Comma-separated GPU ordinals (env var alternative to `-device`) |
| `REDSHIFT_CACHEPATH` | Disk cache path override |
| `REDSHIFT_TEXTURECACHEBUDGET` | Texture cache budget override (env var alternative) |
| `REDSHIFT_ABORTONLICENSEFAIL` | Abort on license failure (important for farms) |
| `REDSHIFT_PATHOVERRIDE_FILE` | Text file for asset path remapping |
| `REDSHIFT_PATHOVERRIDE_STRING` | Direct asset path override |
| `redshift_LICENSE=port@host` | License server (**lowercase** `redshift`!) |
| `LD_LIBRARY_PATH` | Needs `$REDSHIFT_COREDATAPATH/bin` |
| `PATH` | Needs `$REDSHIFT_COREDATAPATH/bin` |
| `OCIO` | OCIO config path override |

### Houdini Node Types (CONFIRMED on hython 21.0.631)

| Context | Node Type | Description |
|---------|-----------|-------------|
| LOP | `redshift::1.0` | Redshift render settings LOP |
| LOP | `redshift::1.1` | Redshift render settings LOP (v1.1) |
| LOP | `redshift_rendervars::1.0` | Redshift render variables LOP |
| ROP | `Redshift_IPR` | Redshift IPR ROP |
| SOP | `redshift_instancefileSOP` | Redshift instance file |
| SOP | `redshift_proxySOP` | Redshift proxy |
| VOP | `redshift_material` | Redshift material |
| VOP | `redshift_usd_material` | Redshift USD material |
| VOP | `redshift_light_shader` | Redshift light shader |
| VOP | `redshift_usd_light_shader` | Redshift USD light shader |
| Hydra | `HdRedshiftRendererPlugin` | Hydra delegate name |

### Version Info (CONFIRMED)

- Local Redshift install: **2026.3.1**
- `redshiftUsdCmdLine` was added in **Redshift 2025.2.0** (Dec 2024)
- USDZ asset rendering was added in **Redshift 2025.5.0** (June 2025)
- Windows UNC path bug fixed in **2025.5.0**

---

## Decision: `redshiftUsdCmdLine` vs husk + Hydra delegate

| | redshiftUsdCmdLine | husk --renderer HdRedshiftRendererPlugin |
|---|---|---|
| Houdini on farm | Not required | Required |
| Hydra 2.0 (H21) | Not affected (bypasses Hydra entirely) | Compatibility issues (Hydra delegate) |
| Frame flags | `-f START -n COUNT -i INC` | `-f START -n COUNT -i INC` |
| Env setup | `REDSHIFT_COREDATAPATH` only | `HFS` + `PXR_PLUGINPATH_NAME` + Redshift paths |
| Standalone | Yes | No |

**Decision: CONFIRMED.** `redshiftUsdCmdLine` is confirmed working and is the
correct primary path. It is self-contained, bypasses Hydra entirely (avoiding
the Hydra 2.0 compatibility issues that affect the Solaris viewport), and
doesn't require a Houdini license on the render node. Available since Redshift
2025.2.0 (Dec 2024); our local install is 2026.3.1. Optionally support husk as
a secondary path later.

---

## Phase 0 — Shared Infrastructure Prep

Before writing Redshift-specific code, small changes to shared modules make
them renderer-agnostic.

### 0.1 `platform_utils.py` — Add Redshift binary resolver

Add `detect_redshift()` and `get_redshift_binary(name)` alongside the existing
`detect_hfs()` / `_get_hfs_binary()`. Resolves paths via
`$REDSHIFT_COREDATAPATH/bin/`.

```
detect_redshift() -> str | None     # returns $REDSHIFT_COREDATAPATH or None
get_redshift_binary(name) -> str    # e.g. "redshiftUsdCmdLine", "redshiftTextureProcessor"
redshift_env_block() -> str         # bash snippet: export REDSHIFT_COREDATAPATH, PATH,
                                    # LD_LIBRARY_PATH, redshift_LICENSE, REDSHIFT_ABORTONLICENSEFAIL
```

### 0.2 `output_injector.py` — `<F4>` token confirmed compatible

**CONFIRMED:** `redshiftUsdCmdLine` uses the same USD-standard `<F4>`
angle-bracket frame token in `productName` attributes. This is NOT
Houdini's `$F4` (which is an expression variable). The existing
`output_injector.py` already writes `<F4>` as a literal string via `Sdf`
layer specs — this works as-is for Redshift.

Redshift 2025.2+ also supports `%d`-style printf format tokens, but `<F4>`
is the standard and works across both husk and `redshiftUsdCmdLine`.

**No changes needed** to `output_injector.py` for Redshift support.

### 0.3 `auditor.py` — Parameterize warning messages

Replace hardcoded "Karma" / "husk" / "Karma RenderSettings LOP" strings with
a `renderer_label` parameter so the same audit logic can emit
renderer-appropriate warnings. The core USD traversal is already generic.

---

## Phase 1 — Core Redshift Modules (`src/`)

Follow the Mantra pattern: a parallel set of `redshift_*.py` modules.

### 1.1 `redshift_validator.py`

Validates that the connected node is a Redshift-compatible LOP setup.

- Check for Redshift LOP nodes upstream (`redshift::1.0`, `redshift::1.1`)
  and/or `redshift:` namespaced attributes on RenderSettings prims in the stage
- Validate GPU availability warning (advisory, not blocking)
- Reuse `validate_shot_name()` and `validate_hip_saved()` from `validator.py`
- Reuse `validate_frame_range()` from `cache_validator.py`

### 1.2 `redshift_auditor.py`

Reads the USD stage and reports Redshift-specific render configuration.

```python
@dataclass
class RedshiftAuditReport:
    has_render_settings: bool
    has_camera: bool
    has_render_products: bool
    has_redshift_settings: bool   # NEW: redshift: attrs on RenderSettings
    has_lights: bool
    light_count: int
    resolution: tuple[int, int]
    aov_names: list[str]
    gpu_device: str | None        # NEW: requested GPU device
    warnings: list[str]
```

Leverages the generic traversal from `auditor.py` but adds Redshift-specific
attribute detection (the `redshift:` namespace on prims).

### 1.3 `redshift_script_writer.py`

Generates `run_render.sh` that calls `redshiftUsdCmdLine` instead of `husk`.

```python
def write_redshift_script(
    output_path: str,
    shot_name: str,
    wrapper_filename: str,           # or the USDZ directly
    frame_start: int,
    frame_end: int,
    gpu_device: str = "all",         # NEW: -device flag
    texture_cache_gb: int | None = None,
    cache_path: str | None = None,
    ocio_config: str | None = None,
    skip_postfx: bool = False,
    extra_flags: list[str] | None = None,
    redshift_path: str | None = None,
) -> None:
```

**Key differences from `render_script_writer.py` (CONFIRMED flags):**

| Karma (husk) | Redshift (redshiftUsdCmdLine) |
|---|---|
| `hfs_source_block()` sources HFS | `redshift_env_block()` exports `REDSHIFT_COREDATAPATH`, `LD_LIBRARY_PATH`, adds `bin/` to PATH |
| `--renderer BRAY_HdKarma` | Not needed (native renderer) |
| `--engine xpu/cpu` | Not applicable (always GPU) |
| `--restart-delegate N` | `-restart-delegate` (no param, per-frame delegate restart) |
| `--exrmode`, `--autotile` | Not applicable |
| `--make-output-path` | Needs manual `mkdir -p` in script |
| `--headlight none` | `-disable-scene-lights` (disables all lights) |
| — | `-device all` or `-device N` (GPU selection) |
| — | `-texturecachebudget N` (GB) |
| — | `-cachepath PATH` |
| — | `-skippostfx` |
| — | `-ocioconfig PATH` / `-ociorenderspace` / `-ociodisplay` / `-ocioview` |
| — | `-oip PATH` (override output image path, ALL AOVs) |
| — | `-ores WxH` (override resolution) |
| — | `-oro FILE` (render options override file) |
| — | `-V 0-6` / `-verbose 0-6` (verbosity level) |
| — | `-s PRIM` / `-settings PRIM` (render settings prim override) |
| — | `-c PRIM` / `-camera PRIM` (camera prim override) |
| — | `-purpose TOKENS` (USD render purpose, default "geometry,render") |
| — | `-crop x y w h` (crop region) |
| — | `-list-settings` / `-list-cameras` (introspection, exit after listing) |
| — | `-override-materials R G B` (clay render) |
| — | `-shutter-open` / `-shutter-close` (motion blur overrides) |
| — | `-hybrid 0\|1` (hybrid rendering toggle) |

Frame flags are identical: `-f START -n COUNT -i INC`.

The script still `cd Scenes` before rendering (same CWD requirement for
relative productName paths).

### 1.4 `redshift_converter.py` (optional)

Pre-converts textures to `.rstexbin` using `redshiftTextureProcessor`.

```python
def convert_to_rstexbin(texture_path: str, processor_path: str) -> str:
    """Convert a texture to .rstexbin format.

    The .rstexbin file is written side-by-side with the source texture
    (same directory, same base name). This is a Redshift requirement.
    """
```

**Placement rule:** `.rstexbin` files go side-by-side with the source texture
(same dir, same base name). This differs from `imaketx` where you can specify
an output directory. The gatherer copies textures first, then the converter
runs in the staging directory.

**Open question:** Is pre-conversion worth the complexity? Redshift
auto-converts at render time. For a v1, skipping pre-conversion and adding it
as a v2 optimization may be pragmatic.

### 1.5 `redshift_info_writer.py`

Writes machine-readable `render_info.txt`. Follows `mantra_info_writer.py`
pattern.

```
renderer=redshift
command=redshiftUsdCmdLine
gpu_device=all
frame_start=1001
frame_end=1100
resolution=1920x1080
texture_cache_gb=8
```

### 1.6 `redshift_manifest.py`

Human-readable packaging report. Follows `mantra_manifest.py` pattern but
includes Redshift-specific sections (GPU device, texture cache, OCIO config).

---

## Phase 2 — HDA Scripts (`hda_scripts_redshift/`)

### 2.1 `PythonModule.py`

Two callbacks: `on_verify_clicked()` and `on_package_clicked()`.

**Key changes from the Karma PythonModule:**

- **Node detection:** Instead of walking upstream for `karmarendersettings`,
  look for Redshift LOP nodes (`redshift::1.0`, `redshift::1.1`) upstream or
  check for `redshift:` namespaced attributes on RenderSettings prims in the
  USD stage. Also detect `redshift_rendervars::1.0` for AOV configuration.
  This is more robust since Redshift settings can come from multiple LOP nodes.

- **No engine selection:** Remove CPU/XPU logic entirely. Redshift is always
  GPU. Replace with GPU device selection (ordinal or "all").

- **AOV handling:** Instead of reading
  `driver:parameters:aov:husk:name`, read standard `RenderVar` prims.
  Redshift uses the standard USD `RenderVar` schema.

- **Output format:** Keep auto-EXR-for-multi-AOV logic (Redshift also can't
  write multiple AOVs to PNG).

- **Texture baking:** The existing `_bake_opdef()` / `_bake_op()` /
  `_bake_houdini_paths()` infrastructure for VOP/SOP/COP baking is
  Houdini-generic and can be reused as-is for Redshift materials that
  reference COP textures or procedural VOPs.

**Pipeline sequence** (same as Karma, different render script step):

1. validate → 2. resolve cache dependencies → 3. audit → 4. create dirs →
5. package upstream caches → 6. inject output paths → 7. flatten & USDZ →
8. write wrapper → 9. **write Redshift render script** → 10. write
orchestration script → 11. write manifest

### 2.2 `OnCreated.py`

- Node color: Redshift brand red — `hou.Color((0.8, 0.15, 0.15))`
- Network box label: "Remote Redshift Render"
- Auto-wire into LOP network (same as Karma)
- X-shape flag (same as Karma)

### 2.3 `btn_verify.py` / `btn_package.py`

One-liners identical to the other HDAs:
```python
hou.phm().on_verify_clicked(kwargs)
```

---

## Phase 3 — HDA Definition

### 3.1 Create `hda/redshift_usd_packager.hdalc`

LOP HDA (same category as Karma packager). Parameters:

**Packaging tab (identical to Karma):**
- `shot_name` — string, shot identifier
- `pod` / `team` — int, folder naming
- `version` — int, auto-incrementing
- `log_output` — multiline string, log display

**Redshift tab (replaces Karma engine/settings):**
- `gpu_device` — string menu: "all", "0", "1", "2", "3"
- `texture_cache_gb` — int, default 8
- `cache_path` — string (file path), optional
- `skip_postfx` — toggle, default off
- `ocio_config` — string (file path), optional

**Buttons:**
- Verify
- Package for Remote

**Footer:**
- `hda_version` — disabled string, version stamp

### 3.2 Pass-through behavior

Same as Karma packager: the node is a pass-through that doesn't modify the
live stage. All packaging writes to disk only.

---

## Phase 4 — Tests

Follow the existing test patterns. All tests marked `not houdini` must pass
in CI.

### New test files:

| File | Tests |
|---|---|
| `test_redshift_validator.py` | Redshift node/stage validation |
| `test_redshift_auditor.py` | Redshift audit report generation |
| `test_redshift_script_writer.py` | Render script content verification |
| `test_redshift_info_writer.py` | Info file format |
| `test_redshift_manifest.py` | Manifest content |
| `test_redshift_converter.py` | Texture conversion (if implemented) |

### Modified test files:

| File | Change |
|---|---|
| `test_auditor.py` | Verify parameterized warnings |
| `test_render_script_writer.py` | No changes (Karma-specific) |

---

## Phase 5 — Integration & Orchestration

### 5.1 Orchestration writer compatibility

`orchestration_writer.py` generates `run_all.sh` that sequences cache scripts
then the render script. This is already renderer-agnostic — it just calls
whatever `run_render.sh` exists. No changes needed.

### 5.2 Dependency resolver compatibility

`dependency_resolver.py` discovers upstream Remote File Cache nodes. This is
entirely SOP/LOP graph traversal — renderer-agnostic. No changes needed.

### 5.3 Wrapper writer

`wrapper_writer.py` creates a thin `.usda` that sublayers the USDZ. This is
pure USD — no changes needed.

---

## Gotchas & Risk Register

### Resolved (confirmed safe):

- **`<F4>` frame token** — CONFIRMED WORKING. `redshiftUsdCmdLine` uses the
  same USD-standard `<F4>` angle-bracket token in `productName`. The existing
  `output_injector.py` writes this correctly. No changes needed.

- **CWD-relative `productName` paths** — CONFIRMED. Like husk,
  `redshiftUsdCmdLine` resolves relative `productName` against CWD. The
  existing `cd Scenes/` pattern in render scripts is correct.

- **USDZ input** — CONFIRMED. `redshiftUsdCmdLine` accepts `.usdz` files
  directly as of Redshift 2025.5.0 (June 2025). The wrapper `.usda`
  sublayering approach also works via standard ArResolver. Our local install
  (2026.3.1) is well past this requirement.

- **`-oip` flag** — CONFIRMED. `-oip PATH` overrides the output image path
  for **ALL AOVs** (not just the beauty pass). This overrides the USD-defined
  `productName`. Useful as a fallback but not needed if `productName` works
  correctly. Also available: `-ores WxH` for resolution override.

### Active risks:

1. **Hydra 2.0 on Houdini 21** — **CONFIRMED SAFE for our use case.**
   Houdini 21 introduced Hydra 2.0 as default. Redshift's Hydra delegate
   (`HdRedshiftRendererPlugin`) has compatibility issues with it, but this
   affects the **Solaris viewport only**. `redshiftUsdCmdLine` bypasses Hydra
   entirely and is unaffected. The packager doesn't use the viewport for
   rendering, so this is **not a blocker**.

2. **`.rstexbin` side-by-side placement** — `redshiftTextureProcessor` writes
   `.rstexbin` next to the source file (same dir, same base name). If the
   source directory is read-only (e.g., shared texture library), conversion
   fails. Also: name collisions if `brick.jpg` and `brick.exr` coexist
   (both produce `brick.rstexbin` — second overwrites first).
   **Mitigation:** Run the converter after `gatherer.py` stages textures into
   the writable package directory. Warn on base-name collisions.

3. **USDZ + Redshift textures** — Textures inside a USDZ archive can't have
   `.rstexbin` siblings. Redshift auto-converts at render time (~30s first-
   frame overhead for scene translation + texture conversion).
   **Mitigation:** Accept the auto-conversion overhead for USDZ workflows, or
   use the wrapper + loose textures approach.

4. **GPU requirement** — Unlike Karma CPU, Redshift always needs a GPU.
   The render script can't fall back to CPU if no GPU is found.
   **Mitigation:** Add a GPU availability check in the verify step (advisory
   warning). The render script should fail fast with a clear error if no GPU
   is detected.

5. **Redshift licensing** — **CONFIRMED:** Requires `redshift_LICENSE=port@host`
   env var (lowercase `redshift` confirmed from Maxon docs). The
   `REDSHIFT_ABORTONLICENSEFAIL` env var can force an explicit abort on
   license failure instead of cryptic errors. Missing or misconfigured
   license = render fails silently unless `REDSHIFT_ABORTONLICENSEFAIL` is set.
   **Mitigation:** The render script should export
   `REDSHIFT_ABORTONLICENSEFAIL=1`, echo the license server address, and
   verify connectivity before starting the render.

6. **UsdPreviewSurface materials not supported** — USDZ files from external
   sources (Sketchfab, Apple AR) use `UsdPreviewSurface` shaders. Redshift
   cannot render these natively — it needs Redshift-specific materials.
   **Mitigation:** The verify step should warn if `UsdPreviewSurface` shaders
   are detected. For LOP workflows this is rare (users build Redshift
   materials in Solaris), but worth flagging.

7. **`RSProceduralUSD.so` manual install** — **CONFIRMED:** This issue is
   specific to the Redshift **Hydra delegate** (`HdRedshiftRendererPlugin`),
   NOT `redshiftUsdCmdLine`. The USD Procedural plugin must be manually
   copied into Redshift's `Procedurals/` directory and matched to the correct
   USD version when using the Hydra delegate via husk. Since we use
   `redshiftUsdCmdLine` (which has its own built-in USD support), this is
   **not a concern for our pipeline**.
   **Mitigation:** Only relevant if we add husk as a secondary render path.
   Document in HDA help for users who render via husk.

8. **Animated attribute limitations** — When using single-process batch
   rendering (all frames in one invocation), only object transforms and camera
   moves update correctly. Animated point attributes, UV transforms, etc. may
   render only the first frame's values.
   **Mitigation:** Document this limitation. For scenes with animated
   attributes, users should render with per-frame invocations (slower but
   correct). Add a parm to control single-process vs per-frame rendering.

### Lower-risk items:

9. **`redshiftUsdCmdLine` path variability** — Install path differs by OS and
   custom installs. Linux default: `/usr/redshift`. No guarantee
   `$REDSHIFT_COREDATAPATH` is set.
   **Mitigation:** `detect_redshift()` checks the env var, falls back to
   common paths (`/usr/redshift`, `/opt/redshift`).

10. **OCIO config** — Redshift on the command line needs explicit OCIO config
    if the scene uses OCIO color management. Houdini sets this automatically;
    `redshiftUsdCmdLine` does not.
    **Mitigation:** Add `ocio_config` parameter to the HDA; include
    `-ocioconfig` flag in the render script.

11. **RS Proxy files (`.rs`) in USDZ** — `.rs` proxy files are Redshift's
    native binary format, NOT USD. They cannot be embedded in USDZ and won't
    be bundled by `UsdUtils.CreateNewUsdzPackage`.
    **Mitigation:** Extend `classifier.py` to detect `.rs` proxy references
    and warn. Rare in LOP workflows (USD Procedurals are used instead).

12. **No `--make-output-path` equivalent** — husk auto-creates output
    directories; `redshiftUsdCmdLine` does not.
    **Mitigation:** Add `mkdir -p ../Output` in the render script before
    calling the renderer.

13. **`redshiftTextureProcessor` flags** — Syntax:
    `redshiftTextureProcessor <inputfile> [-l|-s|-cs "COLORSPACE"]`.
    `-l` = force linear (normals, displacement), `-s` = force sRGB (diffuse).
    Supports wildcards (`*.jpg`). No output directory flag — always writes
    side-by-side.
    **Mitigation:** Document flag usage. Auto-detect color space from texture
    type if feasible, else default to auto-detection (float=linear, int=sRGB).

---

## Implementation Order

```
Phase 0  (prep)       ~1 day    platform_utils, output_injector, auditor
Phase 1  (modules)    ~3 days   validator, auditor, script_writer, info, manifest
Phase 2  (HDA code)   ~2 days   PythonModule, OnCreated, buttons
Phase 3  (HDA def)    ~1 day    .hdalc file, parameters, wiring
Phase 4  (tests)      ~2 days   unit tests for all new modules
Phase 5  (integrate)  ~1 day    verify orchestration, dependency resolver, e2e
```

Total: ~10 working days for a complete, tested Redshift LOP packager.

---

## Files Created (New)

```
src/redshift_validator.py
src/redshift_auditor.py
src/redshift_script_writer.py
src/redshift_info_writer.py
src/redshift_manifest.py
src/redshift_converter.py          # optional, v2
hda_scripts_redshift/PythonModule.py
hda_scripts_redshift/OnCreated.py
hda_scripts_redshift/btn_verify.py
hda_scripts_redshift/btn_package.py
hda/redshift_usd_packager.hdalc
tests/test_redshift_validator.py
tests/test_redshift_auditor.py
tests/test_redshift_script_writer.py
tests/test_redshift_info_writer.py
tests/test_redshift_manifest.py
```

## Files Modified (Existing)

```
src/platform_utils.py              # add detect_redshift(), redshift_env_block()
src/auditor.py                     # parameterize warning messages
```

## Files Unchanged

```
src/output_injector.py             # <F4> token works with redshiftUsdCmdLine
src/packager.py                    # pure USD, renderer-agnostic
src/wrapper_writer.py              # pure USD
src/classifier.py                  # pure USD
src/gatherer.py                    # pure USD
src/validator.py                   # shared validations
src/dependency_resolver.py         # SOP/LOP graph traversal
src/orchestration_writer.py        # run_all.sh sequencing
src/manifest.py                    # base manifest (Karma)
src/cache_*.py                     # Remote File Cache (unrelated)
src/mantra_*.py                    # Mantra packager (unrelated)
```
