# render_info.txt / cache_info.txt Reference

Machine-readable metadata files written to the **shot root** during packaging. One file per package — `render_info.txt` for render jobs, `cache_info.txt` for cache jobs.

Format: `key=value`, one per line, no quoting, no sections. Parseable with `grep`, `cut`, or a simple `dict(line.split("=", 1) for line in f)`.

---

## Karma (render_info.txt)

Written inline in `hda_scripts/PythonModule.py`.

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

| Key | Source | Notes |
|---|---|---|
| `usdfile` | wrapper filename | The `.usda` in `Scenes/` that references the USDZ |
| `startframe` | HDA parm | First frame |
| `framecount` | computed | `frame_end - frame_start + 1` |
| `frameinc` | hardcoded | Always `1` |
| `device` | upstream `karmarendersettings` LOP | `CPU` or `GPU` (XPU) |
| `format` | HDA parm | Output image format (`exr`, `png`, etc.) |
| `outputname` | derived | Wrapper filename without extension |
| `width` / `height` | USD `RenderSettings` prim | Falls back to `1920x1080` |
| `renderer` | derived from engine | `BRAY_HdKarma` (CPU) or `BRAY_HdKarmaXPU` |

---

## Mantra (render_info.txt)

Written by `src/mantra_info_writer.py:write_mantra_info()`.

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

| Key | Source | Notes |
|---|---|---|
| `shot_name` | HDA parm | Shot identifier |
| `folder_name` | computed | `{shot}_P{pod}T{team}_v{ver}` |
| `renderer` | hardcoded | Always `mantra` |
| `method` | hardcoded | Always `ifd` (scene description format) |
| `render_engine` | Mantra ROP parm | `micropoly`, `raytrace`, `pbr` |
| `startframe` / `endframe` / `frameinc` | Mantra ROP parms | Frame range |
| `framecount` | computed | `(end - start) / inc + 1` |
| `resolution` | Mantra ROP parms | `WIDTHxHEIGHT` |
| `pixel_samples` | Mantra ROP parms | `XxY` |
| `camera` | Mantra ROP parm | Houdini object path |
| `rop_node` | node path | Full Houdini path to the Mantra ROP |
| `output_picture` | rewritten | Relative to package root |
| `ifd_count` | computed | Number of IFD files generated |
| `ifd_pattern` | derived | printf-style IFD filename |
| `texture_count` / `textures_size_mb` | gathered | Texture stats |
| `houdini_version` | runtime | From `hou.applicationVersionString()` |
| `generated_at` | runtime | ISO 8601 timestamp |

---

## Redshift (render_info.txt)

Written by `src/redshift_info_writer.py:write_redshift_info()`.

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

| Key | Source | Notes |
|---|---|---|
| `shot_name` | HDA parm | Shot identifier |
| `folder_name` | computed | `{shot}_P{pod}T{team}_v{ver}` |
| `renderer` | hardcoded | Always `redshift` |
| `command` | hardcoded | Always `redshiftUsdCmdLine` |
| `startframe` / `endframe` / `frameinc` | HDA parms | Frame range |
| `framecount` | computed | `(end - start) / inc + 1` |
| `resolution` | USD `RenderSettings` prim | `WIDTHxHEIGHT` |
| `camera` | USD `RenderSettings` prim | USD prim path |
| `gpu_device` | HDA parm | Device ordinal or `all` |
| `aov_count` | USD stage | Number of RenderVar prims |
| `usd_file` | wrapper filename | The `.usda` in `Scenes/` |
| `texture_cache_gb` | HDA parm | Optional — omitted if not set |
| `ocio_config` | HDA parm | Optional — omitted if not set |
| `houdini_version` | runtime | From `hou.applicationVersionString()` |
| `generated_at` | runtime | ISO 8601 timestamp |

---

## File Cache (cache_info.txt)

Written by `src/cache_info_writer.py:write_cache_info()`.

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

| Key | Source | Notes |
|---|---|---|
| `shot_name` | HDA parm | Shot identifier |
| `folder_name` | computed | `{shot}_P{pod}T{team}_v{ver}` |
| `startframe` / `endframe` / `frameinc` | File Cache SOP parms | Frame range |
| `substeps` | File Cache SOP parm | Substeps per frame |
| `framecount` | computed | `(end - start) / inc + 1` |
| `cache_format` | File Cache SOP parm | `.bgeo.sc`, `.vdb`, etc. |
| `cache_node` | node path | Full Houdini path to the internal filecache node |
| `cache_output` | rewritten | Relative to package root |
| `hipfile` | derived | Portable `.hip` in `Scenes/` |
| `houdini_version` | runtime | From `hou.applicationVersionString()` |
| `generated_at` | runtime | ISO 8601 timestamp |

---

## Inconsistencies

Karma's `render_info.txt` is written inline with a different field set than Mantra/Redshift:
- No `shot_name`, `folder_name`, `endframe`, `houdini_version`, or `generated_at`
- Uses `width`/`height` instead of `resolution=WxH`
- Uses `framecount` (like Mantra/Redshift) but no `endframe`
- Uses `device` and `format` fields unique to Karma

The cache workflow uses `cache_info.txt` while all render workflows use `render_info.txt`.
