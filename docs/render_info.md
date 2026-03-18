# Metadata Files

Machine-readable metadata written to the **shot root** during packaging. One file per package — `render_info.txt` for render jobs, `cache_info.txt` for cache jobs.

Format: `key=value`, one per line. Parseable with `grep`, `cut`, or any scripting language.

The Python launchers (`run_render.py`, `run_cache.py`) read these files to determine which renderer to use and how to configure it. They are also useful for farm submission tools or manual pre-flight checks.

---

## Karma — `render_info.txt`

```
usdfile=shot_wrapper.usda
startframe=1001
framecount=48
frameinc=1
device=CPU
format=exr
outputname=shot_wrapper
width=1920
height=1080
renderer=BRAY_HdKarma
```

| Key | What it means |
|---|---|
| **`usdfile`** | The `.usda` scene file in `Scenes/` — this is what husk renders |
| **`startframe`** | First frame to render |
| **`framecount`** | Total number of frames (not the end frame) |
| **`frameinc`** | Frame step — always `1` |
| **`device`** | `CPU` or `GPU` (XPU) |
| **`format`** | Output image format (`exr`, `png`, etc.) |
| **`outputname`** | Base name for output files |
| **`width`** / **`height`** | Render resolution in pixels |
| **`renderer`** | Hydra delegate — `BRAY_HdKarma` (CPU) or `BRAY_HdKarmaXPU` (GPU+CPU) |

---

## Mantra — `render_info.txt`

```
shot_name=shot
folder_name=shot_P1T1_v001
renderer=mantra
method=ifd
render_engine=micropoly
startframe=1001
endframe=1048
frameinc=1
framecount=48
resolution=1920x1080
pixel_samples=6x6
camera=/obj/cam1
rop_node=/out/mantra1
output_picture=Output/shot.0001.exr
ifd_count=48
ifd_pattern=shot.%04d.ifd
texture_count=12
textures_size_mb=234.50
houdini_version=21.0.631
generated_at=2026-03-15T14:30:00
```

| Key | What it means |
|---|---|
| **`shot_name`** | Shot identifier |
| **`folder_name`** | Package folder name (`{shot}_P{pod}T{team}_v{ver}`) |
| **`renderer`** | Always `mantra` |
| **`method`** | Always `ifd` — Mantra's scene description format |
| **`render_engine`** | Mantra engine: `micropoly`, `raytrace`, or `pbr` |
| **`startframe`** / **`endframe`** / **`frameinc`** | Frame range |
| **`framecount`** | Total number of frames |
| **`resolution`** | `WIDTHxHEIGHT` in pixels |
| **`pixel_samples`** | Sampling quality (`XxY`) |
| **`camera`** | Houdini camera path |
| **`rop_node`** | Houdini path to the Mantra ROP |
| **`output_picture`** | Output path relative to package root |
| **`ifd_count`** | Number of IFD scene files generated |
| **`ifd_pattern`** | printf-style filename pattern for IFD files |
| **`texture_count`** / **`textures_size_mb`** | How many textures were gathered, and their total size |
| **`houdini_version`** | Houdini version used to package |
| **`generated_at`** | ISO 8601 timestamp |

---

## Redshift — `render_info.txt`

```
shot_name=shot
folder_name=shot_P1T1_v001
renderer=redshift
command=redshiftUsdCmdLine
startframe=1001
endframe=1048
frameinc=1
framecount=48
resolution=1920x1080
camera=/Render/Camera
gpu_device=all
aov_count=3
usd_file=shot_wrapper.usda
texture_cache_gb=8
ocio_config=/path/to/config.ocio
houdini_version=21.0.631
generated_at=2026-03-16T10:00:00
```

| Key | What it means |
|---|---|
| **`shot_name`** | Shot identifier |
| **`folder_name`** | Package folder name |
| **`renderer`** | Always `redshift` |
| **`command`** | Always `redshiftUsdCmdLine` |
| **`startframe`** / **`endframe`** / **`frameinc`** | Frame range |
| **`framecount`** | Total number of frames |
| **`resolution`** | `WIDTHxHEIGHT` in pixels |
| **`camera`** | USD prim path to the camera |
| **`gpu_device`** | Which GPU(s) to use — `all` or a device number (`0`, `1`, etc.) |
| **`aov_count`** | Number of render output layers (AOVs) |
| **`usd_file`** | The `.usda` scene file in `Scenes/` |
| **`texture_cache_gb`** | GPU texture cache budget in GB (omitted if not set) |
| **`ocio_config`** | Path to OCIO color config (omitted if not set) |
| **`houdini_version`** | Houdini version used to package |
| **`generated_at`** | ISO 8601 timestamp |

---

## File Cache — `cache_info.txt`

```
shot_name=shot
folder_name=shot_P1T1_v001
startframe=1001
endframe=1048
frameinc=1
substeps=1
framecount=48
cache_format=.bgeo.sc
cache_node=/obj/geo1/remote_file_cache1/filecache1
cache_output=Cache/shot.0001.bgeo.sc
hipfile=Scenes/shot_portable.hiplc
houdini_version=21.0.631
generated_at=2026-03-15T12:00:00
```

| Key | What it means |
|---|---|
| **`shot_name`** | Shot identifier |
| **`folder_name`** | Package folder name |
| **`startframe`** / **`endframe`** / **`frameinc`** | Frame range |
| **`substeps`** | Substeps per frame (for simulations that need sub-frame resolution) |
| **`framecount`** | Total number of frames |
| **`cache_format`** | File format — `.bgeo.sc` (compressed geometry), `.vdb` (volumes), etc. |
| **`cache_node`** | Full Houdini node path to the cache node inside the portable `.hip` |
| **`cache_output`** | Output path relative to package root |
| **`hipfile`** | Portable `.hip` scene in `Scenes/` |
| **`houdini_version`** | Houdini version used to package |
| **`generated_at`** | ISO 8601 timestamp |

---

## Field Differences Between Renderers

Karma's info file uses a simpler field set — it predates the Mantra and Redshift packagers and doesn't include `shot_name`, `folder_name`, `endframe`, `houdini_version`, or `generated_at`. It also uses separate `width`/`height` fields instead of `resolution=WxH`.

| Field | Karma | Mantra | Redshift | Cache |
|---|---|---|---|---|
| `shot_name` | — | yes | yes | yes |
| `folder_name` | — | yes | yes | yes |
| `startframe` | yes | yes | yes | yes |
| `endframe` | — | yes | yes | yes |
| `framecount` | yes | yes | yes | yes |
| `resolution` / `width`+`height` | `width`+`height` | `resolution` | `resolution` | — |
| `houdini_version` | — | yes | yes | yes |
| `generated_at` | — | yes | yes | yes |
