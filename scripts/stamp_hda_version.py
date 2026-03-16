#!/usr/bin/env python3
"""Stamp HDA version parameters with current git commit count and hash.

Run from repo root:
    python scripts/stamp_hda_version.py

Requires: run inside Houdini Python (hython) or via MCP execute_houdini_code.
For CI/standalone use, set HFS and source houdini_setup_bash first.
"""

import os
import subprocess
import sys


def get_git_info():
    """Return (commit_count, short_hash) from git."""
    count = subprocess.check_output(
        ["git", "rev-list", "--count", "HEAD"],
        text=True,
    ).strip()
    short_hash = subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"],
        text=True,
    ).strip()
    return int(count), short_hash


def stamp_hda(hda_path, version_string):
    """Update the hda_version parm default in an HDA file."""
    import hou

    definitions = hou.hda.definitionsInFile(hda_path)
    if not definitions:
        print(f"  No definitions in {hda_path}")
        return False

    for definition in definitions:
        tmpl_group = definition.parmTemplateGroup()
        version_parm = tmpl_group.find("hda_version")
        if version_parm is None:
            print(f"  {definition.nodeTypeName()}: no hda_version parm, skipping")
            continue

        version_parm.setDefaultValue((version_string,))
        tmpl_group.replace("hda_version", version_parm)
        definition.setParmTemplateGroup(tmpl_group)
        definition.save(hda_path)
        print(f"  {definition.nodeTypeName()}: {version_string}")

    return True


def main():
    repo_root = subprocess.check_output(
        ["git", "rev-top-level", "--show-toplevel"],
        text=True,
    ).strip()
    hda_dir = os.path.join(repo_root, "hda")

    count, short_hash = get_git_info()
    version_string = f"v0.1.{count} ({short_hash})"
    print(f"Stamping HDAs with: {version_string}")

    for filename in os.listdir(hda_dir):
        if filename.endswith((".hdalc", ".hda")):
            hda_path = os.path.join(hda_dir, filename)
            print(f"\n{filename}:")
            stamp_hda(hda_path, version_string)

    print("\nDone.")


if __name__ == "__main__":
    main()
