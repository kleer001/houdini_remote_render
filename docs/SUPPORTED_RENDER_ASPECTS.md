# Supported Render Aspects

A reference for users of the Karma USD Packager. Each section describes a rendering feature, how the packager handles it for standalone `husk` rendering, and any caveats.

All aspects below have been validated end-to-end: build in Houdini, package with the HDA, render with standalone `husk`, verify output.

---

## Textures

### File Textures (.rat auto-conversion)

**Status:** Fully supported

Houdini's native `.rat` texture format is not part of the [USDZ specification](https://openusd.org/release/spec_usdz.html), which only permits PNG, JPEG, OpenEXR, and AVIF. The packager automatically detects `.rat` textures in the flattened stage and converts them to OpenEXR using `iconvert` before bundling into the USDZ archive. No user action required.

**Reference:** [USDZ File Format Specification — Permitted File Formats](https://openusd.org/release/spec_usdz.html)

### UDIM Texture Sets

**Status:** Supported (extracted as loose files)

UDIM textures use a `<UDIM>` token in the file path that expands to tile numbers (1001, 1002, ...) at render time. The USD UDIM resolver works by scanning a directory for files matching the pattern. This directory scan cannot operate inside a USDZ archive — it is a [known limitation](https://www.sidefx.com/forum/topic/86805/) of the USD asset resolution system, not a bug in any particular tool.

The packager handles this by:
1. Detecting `<UDIM>` patterns in texture paths
2. Copying all resolved tile files to the shot's `Textures/` directory as loose files
3. Overriding the texture paths in the wrapper `.usda` to point to `../Textures/`

The UDIM tiles also remain inside the USDZ (they are valid EXR files), but `husk` reads them from the loose directory via the wrapper override.

**Reference:** [SideFX Forum — USD Resolver can't resolve UDIM texture paths](https://www.sidefx.com/forum/topic/86805/)

### COP Procedural Textures (op: paths)

**Status:** Fully supported

Materials can reference Houdini COP network outputs via `op:` paths (e.g., `op:/img/my_network/OUT`). These are runtime-only Houdini references that don't exist on disk. The packager bakes COP outputs to PNG files using a temporary render node:

- **Legacy COP2 networks** (`/img`): uses `rop_comp`
- **Copernicus networks** (Houdini 20.5+): uses `rop_image`

The baked image replaces the `op:` path in the flattened stage before USDZ creation. Animated COP textures are rendered as per-frame sequences with time-sampled asset paths in the USD.

**Reference:** [hou.Cop2Node — saveImage and pixel data methods](https://www.sidefx.com/docs/houdini/hom/hou/Cop2Node.html), [Save composited data to disk](https://www.sidefx.com/docs/houdini/composite/save.html)

### HDRI Environment Maps

**Status:** Fully supported

HDRI textures on dome lights are treated like any other file texture. If the source is `.rat`, it is converted to `.exr` automatically. The HDRI is bundled inside the USDZ and loads correctly in standalone `husk`.

---

## Materials

### MaterialX Standard Surface

**Status:** Fully supported (recommended)

MaterialX materials are fully portable — they don't require Houdini on the render machine. `mtlxstandard_surface` with `mtlximage` texture nodes produces a self-contained USD material that renders identically in any Hydra-compatible renderer.

**This is the recommended material type for remote rendering.**

### UsdPreviewSurface

**Status:** Fully supported

`UsdPreviewSurface` is the USD-native material type designed for interchange. It supports diffuse color, roughness, metallic, normal maps, and opacity. Like MaterialX, it is fully portable and does not require Houdini on the render machine.

### PrincipledShader (VEX)

**Status:** Supported (requires Houdini on render machine)

Houdini's `principledshader::2.0` is a VEX-based shader. The packager handles it by:
1. Baking the VEX source code (`opdef:` URI) to a file inside the USDZ
2. Restoring the original `opdef:` URI in the wrapper `.usda`

At render time, `husk` resolves the `opdef:` path through the OTL system to compile VEX. This means **Houdini must be installed on the render machine** (Karma CPU only, not XPU).

The packager warns when VEX shaders are detected:
> *"VEX shaders found: ... These require Houdini installed on the render machine (Karma CPU only, not XPU). For fully portable scenes, use MaterialX."*

### Bump and Normal Maps

**Status:** Fully supported

Texture-driven bump mapping works through the PrincipledShader's `baseBumpAndNormal` controls or MaterialX normal map inputs. The bump/normal texture is bundled and converted like any other file texture.

---

## Geometry

### Volumes (VDB and Fog)

**Status:** Fully supported

VDB and fog volume primitives from SOP networks are imported via `sopimport` LOPs. The packager bakes the volume data to `.usdc` files (via temporary SOP Import LOPs) and bundles them in the USDZ. Volume rendering in Karma works correctly with the packaged data.

### Animated Geometry (Deformation)

**Status:** Fully supported

SOP-level deformation (e.g., animated `mountain` SOP) is captured at the current frame during packaging. For multi-frame renders, the frame range is authored in the render settings. Deformation motion blur is supported when `geosamples >= 2` in the Karma render settings.

### Subdivision Surfaces

**Status:** Fully supported

The `subdivisionScheme` attribute on USD Mesh prims (e.g., `catmullClark`) survives stage flattening and USDZ packaging. Karma respects this at render time, producing smooth subdivision surfaces from low-poly input meshes. Render-time subdivision quality is controlled via `karma:object:dicingquality` primvars.

### Point Instances (PointInstancer)

**Status:** Fully supported

USD `PointInstancer` prims with packed SOP geometry render correctly. Instance prototypes and their materials are preserved through flattening. Velocity attributes on instance points enable velocity-based motion blur.

---

## Lighting

### Multiple Light Types

**Status:** Fully supported

All USD light types survive stage flattening and render correctly in standalone `husk`:
- **DomeLight** — environment lighting with optional HDRI texture
- **RectLight** — area light with configurable width/height
- **SphereLight** — point/spot light with optional cone shaping

### Spot Light with Cone Shaping

**Status:** Fully supported

`SphereLight` with `shaping:cone:angle` and `shaping:cone:softness` attributes produces directional spot lighting. These attributes are authored by the Houdini `light::2.0` LOP and preserved through packaging.

### Color Temperature

**Status:** Fully supported

The `enableColorTemperature` and `colorTemperature` attributes on any light type are preserved. Values are specified in Kelvin (e.g., 3500K for warm tungsten, 6500K for daylight).

---

## Motion Blur

### Velocity Blur (PointInstancer)

**Status:** Fully supported

When instance points have a `v` (velocity) attribute and `instance_vblur` is set to "Velocity Blur" in Karma render settings, `husk` renders velocity-based motion blur on instanced geometry.

### Deformation Blur

**Status:** Fully supported

Animated meshes with `geosamples >= 2` in Karma render settings produce deformation motion blur. The packager preserves the `karma:object:geosamples` primvar if set via `rendergeometrysettings` LOPs.

### Camera Motion Blur

**Status:** Fully supported

Animated camera transforms (e.g., expression-driven rotation) produce camera motion blur when `xformsamples >= 2`. The camera animation is baked into the USD at the authored frame range.

---

## Render Properties

### Per-Object Visibility

**Status:** Fully supported

The `karma:object:rendervisibility` primvar controls which ray types can see an object. Setting it to an empty string makes the object completely invisible to the renderer. This is authored via `rendergeometrysettings` LOPs and survives packaging.

### Matte / Holdout Objects

**Status:** Fully supported

The `karma:object:holdoutmode` primvar (values: None, Matte, Background) is preserved through packaging. Matte objects appear as solid shapes that occlude other geometry but show the background color/alpha.

### Render Purpose

**Status:** Fully supported

The USD `purpose` attribute (`render`, `proxy`, `guide`) on `Imageable` prims is preserved. Prims with `purpose = render` are only visible during final rendering, not in viewport preview. Prims with `purpose = guide` are excluded from renders entirely.

---

## What's Not Yet Tested

The following aspects are on the roadmap but haven't been through the stress test pipeline yet:

- [ ] Alembic cache references
- [ ] Time-varying topology (point count changes per frame)
- [ ] Displacement shaders (true displacement vs bump)
- [ ] Deep AOVs and cryptomatte
- [ ] Nested instancing
- [ ] MaterialX with procedural patterns (noise, etc.)
- [ ] Light filters and blockers
- [ ] Atmosphere / fog volumes (non-geometry)

---

## How the Packager Works

For a deeper look at the packaging pipeline and module architecture, see [Pipeline Modules](pipeline_modules.md).

The key transformations the packager performs for standalone `husk` compatibility:

| Problem | Solution |
|---|---|
| `.rat` textures not valid in USDZ | Auto-convert to `.exr` via `iconvert` |
| `<UDIM>` patterns can't resolve inside USDZ | Extract tiles as loose files, override paths in wrapper |
| `op:` COP texture paths are runtime-only | Bake to PNG via `rop_comp` (COP2) or `rop_image` (Copernicus) |
| `op:` SOP geometry paths are runtime-only | Export to `.usdc` via temporary SOP Import LOP |
| `opdef:` VEX shader URIs can't be read from USDZ | Bake VFL source into USDZ, restore `opdef:` in wrapper for OTL resolution |

---

## Sources

- [USDZ File Format Specification](https://openusd.org/release/spec_usdz.html) — permitted texture formats, anchored path requirements
- [Karma User Guide — Texture Maps](https://www.sidefx.com/docs/houdini/solaris/kug/textures.html) — `.rat` auto-conversion, texture optimization
- [hou.Cop2Node](https://www.sidefx.com/docs/houdini/hom/hou/Cop2Node.html) — COP pixel data access and `saveImage()` method
- [hou.saveImageDataToFile](https://www.sidefx.com/docs/houdini/hom/hou/saveImageDataToFile.html) — low-level image file writing
- [Save Composited Data to Disk](https://www.sidefx.com/docs/houdini/composite/save.html) — COP rendering workflows
- [ROP File Output (rop_comp)](https://www.sidefx.com/docs/houdini/nodes/cop2/rop_comp.html) — COP2 render output node
- [SideFX Forum — USD Resolver can't resolve UDIM texture paths](https://www.sidefx.com/forum/topic/86805/) — UDIM-in-USDZ limitation
- [SideFX Forum — Karma .rat texture workflow](https://www.sidefx.com/forum/post/428761/) — texture format considerations
