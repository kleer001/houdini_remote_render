# Package Directory Layout

Every packager creates a self-contained directory under your HIP file's location. The folder name encodes the shot, pod/team, and version: `{shot}_P{pod}T{team}_v{NNN}/`

---

## Karma / Redshift (USD Renderers)

```
{shot}_P1T1_v001/
├── render_info.txt                  ← machine-readable metadata (renderer, resolution, frames, etc.)
├── manifest.txt                     ← human-readable packaging report
├── Output/                          ← render frames land here (created by the render command)
├── Textures/                        ← all textures gathered and converted for portability
├── Cache/                           ← upstream simulation/cache output (only if caches were bundled)
├── Scenes/
│   ├── {shot}_wrapper.usda          ← thin USD file that references the USDZ + overrides cache paths
│   ├── {shot}.usdz                  ← the entire flattened scene with textures baked in
│   └── {shot}_portable.hiplc        ← portable Houdini scene (only if caches were bundled)
└── Scripts/
    ├── run_render.sh                ← launches husk (Karma) or redshiftUsdCmdLine (Redshift)
    ├── run_render.py                ← cross-platform Python launcher for the above
    ├── run_cache_001.sh             ← per-cache script (only if caches were bundled)
    ├── run_cache_001.py
    ├── run_all.sh                   ← orchestrator: runs caches in order, then render (only if caches)
    └── run_all.py
```

**Key files:**

| File | What it is | When you'd look at it |
|---|---|---|
| `render_info.txt` | Renderer, resolution, frame range, camera, samples | Checking job settings before submitting to a farm |
| `manifest.txt` | Full packaging report: what was gathered, converted, bundled | Troubleshooting missing assets or unexpected results |
| `{shot}_wrapper.usda` | The file you pass to the renderer | Debugging render failures — open in usdview to inspect |
| `{shot}.usdz` | The scene archive (everything baked in) | Transferring the scene to another machine |
| `run_render.sh` | The actual render command | Seeing exactly what will execute on the farm |
| `run_all.sh` | Full pipeline: caches then render | Running the complete job with one command |

---

## Mantra

```
{shot}_P1T1_v001/
├── render_info.txt                  ← machine-readable metadata
├── manifest.txt                     ← human-readable packaging report
├── Output/                          ← rendered frames
├── IFDs/                            ← Mantra scene description files (one per frame)
├── Textures/                        ← gathered textures
├── Scenes/
│   └── {shot}_portable.hiplc        ← portable Houdini scene
└── Scripts/
    ├── run_render.sh                ← loops through IFDs and renders each frame
    └── run_render.py                ← cross-platform Python launcher
```

Mantra exports IFD files (Mantra's scene format) instead of USD. The render script loops through them frame-by-frame. No Houdini license is needed to render IFDs — Mantra uses free render tokens.

---

## File Cache

```
{shot}_P1T1_v001/
├── cache_info.txt                   ← machine-readable metadata (node path, frame range, format)
├── manifest.txt                     ← human-readable packaging report
├── Cache/                           ← simulation/cache output
├── Scenes/
│   └── {shot}_portable.hiplc        ← portable Houdini scene with rewritten cache paths
└── Scripts/
    ├── run_cache.sh                 ← runs hython to cook the cache
    └── run_cache.py                 ← cross-platform Python launcher
```

The simplest package — just a portable Houdini scene and a script to cook the cache node.

---

## Notes

- **Every `.sh` script has a `.py` counterpart.** The Python launchers detect the OS at runtime — on Linux/macOS they call the shell script, on Windows they translate to equivalent subprocess calls.
- **All paths are relative.** Packages are fully portable — copy the entire folder to any machine and run the script.
- **`Output/` and `Cache/` directories** are created empty. They fill up when the render/cache script runs.
