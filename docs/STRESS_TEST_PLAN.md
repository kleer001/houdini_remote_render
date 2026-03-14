# Stress Test Plan — Karma USD Packager

Test each category by building it in `tester.hiplc`, packaging with the HDA, and rendering with standalone husk. Each test should verify: no husk errors, correct visual output, all assets bundled.

## Test Scene: `/stage` in tester.hiplc

The scene already has a working base (v003 rendered successfully):
- Dome light, camera, Karma RenderSettings with Beauty AOV
- 3 instance flavours (PointInstancer, native USD instances, expanded geo)

## Tests to Add

### 1. Textures
- [ ] File-based texture on a material (PNG/EXR image map on diffuse)
- [ ] UDIM texture set (multi-tile texture)
- [ ] COP-driven texture (op: reference — already tested in mMultiFX, but verify in isolation)
- [ ] HDRI on dome light (environment map)

### 2. Volumes
- [ ] VDB volume (pyro/smoke cache referenced via file path)
- [ ] Fog volume (simple procedural volume from SOP)

### 3. Animated Geometry
- [ ] SOP-level deformation over frame range (e.g. mountain SOP with animated offset)
- [ ] Alembic cache reference (if available)
- [ ] Time-varying point count (topology change per frame)

### 4. Lights
- [ ] Area light (rect/disk)
- [ ] Spot light with barn doors
- [ ] Multiple lights (verify all survive flatten)
- [ ] Light with color temperature

### 5. Materials with Texture Maps
- [ ] MaterialX standard surface with file texture inputs
- [ ] UsdPreviewSurface with texture maps
- [ ] PrincipledShader with texture maps (VEX path — verify opdef: restoration)
- [ ] Material with normal map

### 6. Motion Blur
- [ ] Velocity-based motion blur on PointInstancer
- [ ] Deformation blur on animated mesh
- [ ] Camera motion blur (animated camera transform)

### 7. Subdivision Surfaces
- [ ] Mesh with subdivision scheme set (catmullClark)
- [ ] Render-time subdivision level via karma:object properties

### 8. Render Properties
- [ ] Per-object visibility (hidden prim that should NOT render)
- [ ] Per-object render purpose (render vs proxy vs guide)
- [ ] Matte/holdout objects

## How to Run

```bash
# Package from HDA (in Houdini)
# Set version, click Package

# Render with husk
cd /path/to/SHOT_P1T1_vNNN/Scenes
husk --renderer BRAY_HdKarma --frame 1 --frame-count 1 SHOT.usda

# Convert EXR to PNG for viewing
hoiiotool ../Output/SHOT.0001.exr -o /tmp/test_preview.png
```

## Pass Criteria
- husk exit code 0
- No "Unhandled node type" errors
- No "Unsupported AOV settings" errors
- No "No render camera defined" errors
- Output image contains expected geometry/shading (not black, not grey fallback)
- File size reasonable (not suspiciously small)
