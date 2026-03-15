# Publicity Plan

## Positioning

**One-liner:** Self-contained USD scene packaging for Houdini — bundle, ship, render anywhere without shared filesystems or farm managers.

**The gap we fill:** Existing tools either collect .hip files without understanding USD (HipCollector), or submit husk jobs assuming shared filesystems (HuskSubmitter, Deadline plugins). Nothing packages a Houdini USD scene into a portable USDZ archive with a ready-to-run render script. We do.

**Target audience:**
- Freelancers sending renders to cloud machines or remote workstations
- Small studios without Deadline/Tractor/shared NFS
- Students and educators running renders on school lab machines
- Teams using Google Drive / Dropbox / sneakernet to move scenes between machines
- Anyone who's ever emailed a .hip file and had it fail because of missing textures

---

## Launch Channels

### 1. SideFX Forum (highest value)

**Where:** [SideFX Forum — Solaris / Karma](https://www.sidefx.com/forum/71/)

**Post title:** "Karma USD Packager — package scenes for standalone husk rendering (open source HDA)"

**Structure:**
- Problem statement: "I needed to render Karma scenes on machines without access to my project filesystem"
- What it does: 3-bullet summary (packages USDZ, generates run_render.sh, handles textures/COP baking/VEX shaders)
- Demo: before/after — show the output directory structure
- Link to GitHub
- Mention it's Indie-licensed (.hdalc) and works with H21.0+
- Ask for feedback on what render aspects people need

**Also post in:** [SideFX Forum — HDAs & Scripts](https://www.sidefx.com/forum/46/)

### 2. Reddit

**Subreddits:**
- **r/Houdini** (~45k members) — primary audience
- **r/vfx** (~180k members) — broader reach
- **r/computergraphics** — academic/technical crowd

**Post format:** Short intro + GIF or screenshot of the HDA in action + link. Reddit rewards visual content. A 30-second screen recording of: drop HDA → click Verify → click Package → run script → show rendered EXR would be ideal.

### 3. GitHub

**README polish:**
- Add badges (license, Python version, Houdini version)
- Add a hero screenshot or diagram of the packaging pipeline
- Add a "Quick Start" section with 5 steps
- Add a "Why?" section contrasting with existing tools
- Tag the repo with topics: `houdini`, `usd`, `karma`, `husk`, `rendering`, `vfx`, `solaris`, `usdz`

**Release:**
- Create a GitHub Release (v1.0.0) with a changelog summarizing all verified render aspects
- Attach the .hdalc files as release assets for easy download

### 4. Discord

- **Houdini Artists Discord** — #tools-and-scripts channel
- **Think Procedural Discord** — Houdini-focused community
- **VFX Discord servers** — look for #houdini or #pipeline channels

### 5. LinkedIn

**Post format:** "I built an open-source tool that solves a problem I kept hitting..." story format. Tag #Houdini #VFX #USD #OpenSource. Mention the stress test results (verified 20+ render aspects). LinkedIn rewards longer-form "I built this" posts.

### 6. Odforce (legacy but still active)

[odforce.net](https://odforce.net) — the original Houdini community forum. Post in the Tools section.

### 7. YouTube / Vimeo (optional but high impact)

A 3-5 minute walkthrough video:
1. The problem (missing textures, broken paths on remote machines)
2. Drop the HDA, click Verify, click Package
3. Show the output directory structure
4. Copy to another machine, run `./Scripts/run_render.sh`
5. Show the rendered EXR

This can be referenced from all other channels.

---

## Content Assets to Prepare

### Must-have before launch

- [ ] **README overhaul** — hero image, quick start, "why this exists" section
- [ ] **Screenshot** — the HDA node in a LOP network with the verify log visible
- [ ] **Output directory tree** — terminal screenshot showing the clean folder structure
- [ ] **Before/after comparison** — "here's what breaks without packaging" vs "here's the packaged output"

### Nice-to-have

- [ ] **Screen recording** (GIF or short video) — full workflow in 30 seconds
- [ ] **Architecture diagram** — the 11-module pipeline as a flow chart
- [ ] **Comparison table** — this tool vs HipCollector vs HuskSubmitter vs Deadline

---

## Messaging

### Key points to hit

1. **No shared filesystem required.** Package on your workstation, render on any machine with Houdini.
2. **One click, everything bundled.** Textures converted, COP networks baked, VEX shaders embedded, UDIM tiles extracted.
3. **Ready-to-run render script.** `run_render.sh` sources Houdini, calls husk with smart defaults. No manual CLI flag wrangling.
4. **Verified end-to-end.** 20+ render aspects stress-tested with actual husk renders. Automated integration tests that invoke husk.
5. **Open source, Indie-friendly.** .hdalc format, works with Houdini Indie license.

### What NOT to claim

- Don't position as a "render farm manager" — it's a packager, not a scheduler
- Don't claim Redshift/Mantra support yet — those are planned but not built
- Don't oversell XPU — it works but requires MaterialX-only scenes

---

## Launch Sequence

1. **Week 0:** Polish README, prepare screenshots, create GitHub Release v1.0.0
2. **Week 1:** Post on SideFX Forum (Solaris + HDAs sections)
3. **Week 1:** Post on r/Houdini with screenshot/GIF
4. **Week 2:** Post on Discord servers, LinkedIn
5. **Week 2:** Cross-post to r/vfx if r/Houdini got traction
6. **Week 3+:** Respond to feedback, fix reported issues, post follow-up with improvements
7. **Ongoing:** Monitor GitHub issues, iterate based on real user feedback

---

## Success Metrics

- GitHub stars (proxy for visibility)
- SideFX Forum thread views and replies
- GitHub Issues filed (means people are actually using it)
- Forks (means people want to extend it)
- Any mentions in Houdini community roundups or newsletters
