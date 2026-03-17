"""Scan IFD files for texture references and copy them for remote rendering.

IFDs with vm_binarygeometry=1 contain binary blobs, so we read with
errors='replace' to safely skip non-text sections.
"""

import os
import re
import shutil

_TEXTURE_EXTENSIONS = (
    ".exr", ".rat", ".png", ".jpg", ".jpeg",
    ".tif", ".tiff", ".hdr", ".tx",
)

# Match absolute paths (starting with /) that end with a texture extension.
# Handles paths in quotes or standalone on a line.
_ABS_PATH_RE = re.compile(r'(/[^\s"\']+\.(?:' +
                           "|".join(ext.lstrip(".") for ext in _TEXTURE_EXTENSIONS) +
                           r'))\b', re.IGNORECASE)


def scan_ifds_for_textures(ifd_paths: list[str]) -> list[str]:
    """Read IFD files and extract unique absolute texture paths that exist on disk.

    Args:
        ifd_paths: List of IFD file paths to scan.

    Returns:
        Sorted list of unique absolute texture paths that exist on disk.
    """
    found = set()
    for ifd_path in ifd_paths:
        with open(ifd_path, "r", errors="replace") as f:
            for line in f:
                for match in _ABS_PATH_RE.finditer(line):
                    candidate = match.group(1)
                    if os.path.isfile(candidate):
                        found.add(candidate)
    return sorted(found)


def gather_textures(
    texture_paths: list[str],
    textures_dir: str,
) -> dict[str, str]:
    """Copy texture files into the package's Textures/ directory.

    Args:
        texture_paths: List of absolute texture paths to copy.
        textures_dir: Destination directory for copied textures.

    Returns:
        Mapping of {original_path: copied_path} for each texture.
    """
    os.makedirs(textures_dir, exist_ok=True)
    copied = {}
    for src_path in texture_paths:
        filename = os.path.basename(src_path)
        dst_path = os.path.join(textures_dir, filename)
        # Handle name collisions by prefixing with parent dir name
        if dst_path in copied.values() and dst_path != copied.get(src_path):
            parent_name = os.path.basename(os.path.dirname(src_path))
            dst_path = os.path.join(textures_dir, f"{parent_name}_{filename}")
        if src_path not in copied:
            shutil.copy2(src_path, dst_path)
            copied[src_path] = dst_path
    return copied
