"""Tests for mantra_texture_gatherer module (CI-safe, no Houdini required)."""

import os
import tempfile

from src.mantra_texture_gatherer import scan_ifds_for_textures, gather_textures


class TestScanIfdsForTextures:
    def test_finds_absolute_texture_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a fake texture file
            tex_path = os.path.join(tmpdir, "wood.exr")
            with open(tex_path, "w") as f:
                f.write("fake texture data")

            # Create a fake IFD referencing that texture
            ifd_path = os.path.join(tmpdir, "test.0001.ifd")
            with open(ifd_path, "w") as f:
                f.write(f'ray_property object surface "{tex_path}" diffuse\n')

            result = scan_ifds_for_textures([ifd_path])
            assert tex_path in result

    def test_finds_multiple_extensions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = {}
            for ext in (".exr", ".rat", ".png", ".jpg", ".tif", ".hdr", ".tx"):
                p = os.path.join(tmpdir, f"tex{ext}")
                with open(p, "w") as f:
                    f.write("fake")
                paths[ext] = p

            ifd_path = os.path.join(tmpdir, "test.0001.ifd")
            lines = [f'texture "{p}"\n' for p in paths.values()]
            with open(ifd_path, "w") as f:
                f.writelines(lines)

            result = scan_ifds_for_textures([ifd_path])
            for p in paths.values():
                assert p in result

    def test_deduplicates_across_ifds(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tex_path = os.path.join(tmpdir, "shared.exr")
            with open(tex_path, "w") as f:
                f.write("fake")

            ifd1 = os.path.join(tmpdir, "test.0001.ifd")
            ifd2 = os.path.join(tmpdir, "test.0002.ifd")
            for ifd in (ifd1, ifd2):
                with open(ifd, "w") as f:
                    f.write(f'texture "{tex_path}"\n')

            result = scan_ifds_for_textures([ifd1, ifd2])
            assert result.count(tex_path) == 1

    def test_filters_nonexistent_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ifd_path = os.path.join(tmpdir, "test.0001.ifd")
            with open(ifd_path, "w") as f:
                f.write('texture "/nonexistent/path/texture.exr"\n')

            result = scan_ifds_for_textures([ifd_path])
            assert len(result) == 0

    def test_handles_binary_blobs(self):
        """IFDs with vm_binarygeometry contain binary data — scanner must not crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tex_path = os.path.join(tmpdir, "good.exr")
            with open(tex_path, "w") as f:
                f.write("fake")

            ifd_path = os.path.join(tmpdir, "test.0001.ifd")
            with open(ifd_path, "wb") as f:
                f.write(b'texture "' + tex_path.encode() + b'"\n')
                f.write(b'\x00\x01\x02\xff\xfe binary blob data\n')
                f.write(b'more text after binary\n')

            result = scan_ifds_for_textures([ifd_path])
            assert tex_path in result

    def test_returns_sorted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = []
            for name in ("z_tex.exr", "a_tex.exr", "m_tex.exr"):
                p = os.path.join(tmpdir, name)
                with open(p, "w") as f:
                    f.write("fake")
                paths.append(p)

            ifd_path = os.path.join(tmpdir, "test.0001.ifd")
            with open(ifd_path, "w") as f:
                for p in paths:
                    f.write(f'texture "{p}"\n')

            result = scan_ifds_for_textures([ifd_path])
            assert result == sorted(result)

    def test_empty_ifd_list(self):
        result = scan_ifds_for_textures([])
        assert result == []

    def test_ignores_non_texture_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a .obj file (not a texture)
            obj_path = os.path.join(tmpdir, "mesh.obj")
            with open(obj_path, "w") as f:
                f.write("v 0 0 0")

            ifd_path = os.path.join(tmpdir, "test.0001.ifd")
            with open(ifd_path, "w") as f:
                f.write(f'geometry "{obj_path}"\n')

            result = scan_ifds_for_textures([ifd_path])
            assert len(result) == 0


class TestGatherTextures:
    def test_copies_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "source")
            dst_dir = os.path.join(tmpdir, "Textures")
            os.makedirs(src_dir)

            tex_path = os.path.join(src_dir, "wood.exr")
            with open(tex_path, "w") as f:
                f.write("fake texture")

            result = gather_textures([tex_path], dst_dir)
            assert tex_path in result
            assert os.path.isfile(result[tex_path])
            assert os.path.basename(result[tex_path]) == "wood.exr"

    def test_returns_mapping(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "source")
            dst_dir = os.path.join(tmpdir, "Textures")
            os.makedirs(src_dir)

            paths = []
            for name in ("a.exr", "b.png"):
                p = os.path.join(src_dir, name)
                with open(p, "w") as f:
                    f.write("fake")
                paths.append(p)

            result = gather_textures(paths, dst_dir)
            assert len(result) == 2
            for src, dst in result.items():
                assert os.path.isfile(dst)

    def test_creates_destination_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_path = os.path.join(tmpdir, "tex.exr")
            with open(src_path, "w") as f:
                f.write("fake")

            dst_dir = os.path.join(tmpdir, "new", "Textures")
            gather_textures([src_path], dst_dir)
            assert os.path.isdir(dst_dir)

    def test_empty_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dst_dir = os.path.join(tmpdir, "Textures")
            result = gather_textures([], dst_dir)
            assert result == {}
