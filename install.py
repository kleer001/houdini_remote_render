#!/usr/bin/env python3
"""Install/uninstall Houdini Remote Render & Cache HDAs.

Uses Houdini's package system to register the HDA directory without copying files.
This keeps the HDAs in the repository so that _ensure_src_path() can find the
src/ modules relative to the HDA library file.

Usage:
    python install.py              # Auto-detect Houdini versions, install for all
    python install.py --version 21.0   # Install for a specific version
    python install.py --uninstall  # Remove the package file
    python install.py --status     # Show current install status
"""

import argparse
import json
import platform
import sys
from pathlib import Path

PACKAGE_NAME = "houdini_remote_render"
PACKAGE_FILENAME = f"{PACKAGE_NAME}.json"


def get_repo_root() -> Path:
    """Return the repository root (directory containing this script)."""
    return Path(__file__).resolve().parent


def get_houdini_pref_dirs() -> list[Path]:
    """Find all Houdini user preference directories on this system.

    Returns a list of paths like ~/houdini21.0/, sorted by version descending.
    """
    system = platform.system()

    if system == "Linux":
        base = Path.home()
        pattern = "houdini*"
    elif system == "Darwin":
        base = Path.home() / "Library" / "Preferences" / "houdini"
        pattern = "*"
    elif system == "Windows":
        base = Path.home() / "Documents"
        pattern = "houdini*"
    else:
        print(f"Unsupported platform: {system}")
        return []

    if not base.exists():
        return []

    dirs = []
    for d in sorted(base.glob(pattern), reverse=True):
        if not d.is_dir():
            continue
        # Filter to directories that look like Houdini prefs
        name = d.name
        if system == "Darwin":
            # On macOS, version dirs are directly under houdini/
            # e.g. ~/Library/Preferences/houdini/21.0/
            try:
                float(name)
                dirs.append(d)
            except ValueError:
                continue
        else:
            # On Linux/Windows, dirs are houdini21.0, houdini20.5, etc.
            if name.startswith("houdini"):
                version_part = name[len("houdini"):]
                try:
                    float(version_part)
                    dirs.append(d)
                except ValueError:
                    continue

    return dirs


def get_pref_dir_for_version(version: str) -> Path | None:
    """Find the Houdini pref dir for a specific version string (e.g. '21.0').

    Matches against the version portion of the directory name, not the full name.
    '21.0' matches 'houdini21.0' but '2' does not match 'houdini21.0'.
    """
    # Normalize: strip leading 'houdini' if user passed it
    version = version.lower().removeprefix("houdini")

    for d in get_houdini_pref_dirs():
        # Extract the version portion from the dir name
        name = d.name.lower()
        if name.startswith("houdini"):
            dir_version = name[len("houdini"):]
        else:
            dir_version = name  # macOS: just the version number

        if dir_version == version:
            return d

    return None


def build_package_json(repo_root: Path) -> dict:
    """Build the Houdini package JSON content."""
    hda_dir = (repo_root / "src" / "hda").as_posix()
    return {
        "env": [
            {
                "HOUDINI_OTLSCAN_PATH": {
                    "value": hda_dir,
                    "method": "append",
                }
            }
        ],
        "path": repo_root.as_posix(),
    }


def install(pref_dir: Path, repo_root: Path) -> tuple[bool, str]:
    """Install the package file into a Houdini pref directory.

    Returns (success, message) tuple.
    """
    package_file = pref_dir / "packages" / PACKAGE_FILENAME
    try:
        packages_dir = pref_dir / "packages"
        packages_dir.mkdir(parents=True, exist_ok=True)

        package_data = build_package_json(repo_root)

        with open(package_file, "w", newline="\n") as f:
            json.dump(package_data, f, indent=4)
            f.write("\n")

        return True, str(package_file)
    except OSError as e:
        return False, f"Failed to write {package_file}: {e}"


def uninstall(pref_dir: Path) -> tuple[bool, str]:
    """Remove the package file from a Houdini pref directory.

    Returns (success, message) tuple. Success is False if the file was not
    found or could not be removed.
    """
    package_file = pref_dir / "packages" / PACKAGE_FILENAME
    if not package_file.exists():
        return False, "Not installed"
    try:
        package_file.unlink()
        return True, str(package_file)
    except OSError as e:
        return False, f"Failed to remove {package_file}: {e}"


def check_status(pref_dir: Path) -> dict:
    """Check install status for a Houdini pref directory.

    Returns a dict with 'installed', 'package_file', and 'hda_dir' keys.
    """
    package_file = pref_dir / "packages" / PACKAGE_FILENAME
    result = {
        "installed": False,
        "package_file": str(package_file),
        "hda_dir": None,
    }

    if package_file.exists():
        result["installed"] = True
        try:
            with open(package_file) as f:
                data = json.load(f)
            for env in data.get("env", []):
                otl_path = env.get("HOUDINI_OTLSCAN_PATH", {})
                if isinstance(otl_path, dict):
                    result["hda_dir"] = otl_path.get("value")
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    return result


def format_pref_dir_label(pref_dir: Path) -> str:
    """Return a human-readable label for a Houdini pref directory."""
    system = platform.system()
    if system == "Darwin":
        return f"Houdini {pref_dir.name}"
    else:
        return pref_dir.name


def main():
    if sys.version_info < (3, 10):
        print(f"Error: Python 3.10+ required, found {sys.version}")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Install Houdini Remote Render & Cache HDAs",
    )
    parser.add_argument(
        "--version",
        help="Houdini version to target (e.g. '21.0'). Default: all found versions.",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove the package file instead of installing.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current install status without making changes.",
    )
    args = parser.parse_args()

    repo_root = get_repo_root()
    hda_dir = repo_root / "src" / "hda"

    # Verify repo structure
    if not hda_dir.is_dir():
        print(f"Error: src/hda/ directory not found at {hda_dir}")
        sys.exit(1)

    hdas = sorted(hda_dir.glob("*.hdalc"), key=lambda p: p.name)
    if not hdas:
        print(f"Error: no .hdalc files found in {hda_dir}")
        sys.exit(1)

    # Find target pref dirs
    if args.version:
        pref_dir = get_pref_dir_for_version(args.version)
        if pref_dir is None:
            print(f"Error: no Houdini {args.version} preferences directory found.")
            print("Searched locations:")
            system = platform.system()
            if system == "Linux":
                print(f"  ~/houdini{args.version}/")
            elif system == "Darwin":
                print(f"  ~/Library/Preferences/houdini/{args.version}/")
            elif system == "Windows":
                print(f"  ~/Documents/houdini{args.version}/")
            sys.exit(1)
        pref_dirs = [pref_dir]
    else:
        pref_dirs = get_houdini_pref_dirs()
        if not pref_dirs:
            print("Error: no Houdini preference directories found.")
            print("Is Houdini installed? Expected locations:")
            system = platform.system()
            if system == "Linux":
                print("  ~/houdini*/")
            elif system == "Darwin":
                print("  ~/Library/Preferences/houdini/*/")
            elif system == "Windows":
                print("  ~/Documents/houdini*/")
            sys.exit(1)

    # Status
    if args.status:
        print(f"Repository: {repo_root}")
        print(f"HDA directory: {hda_dir}")
        print(f"HDAs: {', '.join(h.name for h in hdas)}")
        print()
        for pref_dir in pref_dirs:
            label = format_pref_dir_label(pref_dir)
            status = check_status(pref_dir)
            if status["installed"]:
                print(f"  {label}: INSTALLED")
                print(f"    Package: {status['package_file']}")
                print(f"    HDA dir: {status['hda_dir']}")
            else:
                print(f"  {label}: not installed")
        return

    # Uninstall
    if args.uninstall:
        ok_count = 0
        fail_count = 0
        for pref_dir in pref_dirs:
            label = format_pref_dir_label(pref_dir)
            success, msg = uninstall(pref_dir)
            if success:
                print(f"  [OK] Removed: {label}")
                ok_count += 1
            else:
                print(f"  [--] {label}: {msg}")
                if "Failed" in msg:
                    fail_count += 1
        print()
        if fail_count:
            print(f"Done with {fail_count} error(s). Check permissions.")
            sys.exit(1)
        elif ok_count:
            print("Done. Restart Houdini for changes to take effect.")
        else:
            print("Nothing to uninstall.")
        return

    # Install
    print(f"Repository: {repo_root}")
    print(f"HDAs: {', '.join(h.name for h in hdas)}")
    print()

    ok_count = 0
    fail_count = 0
    for pref_dir in pref_dirs:
        label = format_pref_dir_label(pref_dir)
        success, msg = install(pref_dir, repo_root)
        if success:
            print(f"  [OK] Installed: {label}")
            ok_count += 1
        else:
            print(f"  [FAIL] {label}: {msg}")
            fail_count += 1

    print()
    if fail_count:
        print(f"Done with {fail_count} error(s) out of {ok_count + fail_count} version(s).")
        sys.exit(1)
    else:
        print(f"Done. Installed for {ok_count} Houdini version(s).")
        print("Restart Houdini for changes to take effect.")
        print()
        print("HDAs will appear as:")
        print("  - Karma USD Packager  (LOP networks)")
        print("  - Remote File Cache   (SOP networks)")


if __name__ == "__main__":
    main()
