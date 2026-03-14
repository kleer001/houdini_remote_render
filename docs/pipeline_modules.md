# Pipeline Modules

## Karma USD Packager

| Module | Purpose |
|---|---|
| `validator` | Shot name, HIP file, and directory structure checks |
| `auditor` | USD stage inspection — render settings, camera, products, instances |
| `classifier` | Dependency scanning and UDIM detection |
| `converter` | Texture conversion via `imaketx` |
| `gatherer` | File copying and USD path rewriting |
| `output_injector` | RenderProduct output path authoring (format + frame tokens) |
| `packager` | Stage flatten + USDZ creation |
| `wrapper_writer` | Thin `.usda` wrapper with cache references |
| `render_script_writer` | Generate `run_render.sh` husk launcher with smart defaults |
| `manifest` | Human-readable packaging report |

## Remote File Cache

| Module | Purpose |
|---|---|
| `cache_validator` | File Cache SOP existence and parameter checks |
| `cache_auditor` | Read File Cache params into structured report |
| `cache_scene_writer` | Save portable `.hip` with rewritten cache paths |
| `cache_script_writer` | Generate `run_cache.sh` hbatch launcher |
| `cache_info_writer` | Write machine-readable `cache_info.txt` |
| `cache_manifest` | Human-readable packaging report |

## Shared

| Module | Purpose |
|---|---|
| `validator` | Shot name validation, HIP saved check (shared) |
| `platform_utils` | Path normalization, `ensure_dir`, disk space check (shared) |
