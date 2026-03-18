"""Tests for cache_script_writer module."""

import os
import stat
import tempfile

from src.cache_script_writer import write_cache_script


class TestWriteCacheScript:
    def test_writes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_cache.sh")
            write_cache_script(
                output_path=path,
                shot_name="test_shot",
                hip_filename="test_shot.hip",
                cache_node_path="/obj/geo1/filecache1",
                frame_start=1001,
                frame_end=1200,
            )
            assert os.path.isfile(path)

    def test_is_executable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_cache.sh")
            write_cache_script(
                output_path=path,
                shot_name="test_shot",
                hip_filename="test_shot.hip",
                cache_node_path="/obj/geo1/filecache1",
                frame_start=1001,
                frame_end=1200,
            )
            st = os.stat(path)
            assert st.st_mode & stat.S_IEXEC

    def test_contains_hython_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_cache.sh")
            write_cache_script(
                output_path=path,
                shot_name="explosion",
                hip_filename="explosion.hip",
                cache_node_path="/obj/geo1/filecache1",
                frame_start=1001,
                frame_end=1200,
            )

            with open(path) as f:
                content = f.read()

            assert "#!/bin/bash" in content
            assert "hython" in content
            assert "Scenes/explosion.hip" in content
            assert "/obj/geo1/filecache1" in content
            assert "pressButton" in content

    def test_contains_shot_info(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_cache.sh")
            write_cache_script(
                output_path=path,
                shot_name="my_sim",
                hip_filename="my_sim.hip",
                cache_node_path="/obj/geo1/fc1",
                frame_start=1,
                frame_end=240,
            )

            with open(path) as f:
                content = f.read()

            assert "my_sim" in content
            assert "1-240" in content

    def test_newline_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_cache.sh")
            write_cache_script(
                output_path=path,
                shot_name="test",
                hip_filename="test.hip",
                cache_node_path="/obj/geo1/fc1",
                frame_start=1,
                frame_end=10,
            )

            with open(path, "rb") as f:
                raw = f.read()
            assert b"\r\n" not in raw

    def test_deletes_keyframes_before_set(self):
        """Frame range parms with expressions need deleteAllKeyframes
        before set() — otherwise set() is silently ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_cache.sh")
            write_cache_script(
                output_path=path,
                shot_name="test",
                hip_filename="test.hip",
                cache_node_path="/obj/geo1/fc1",
                frame_start=1,
                frame_end=10,
            )

            with open(path) as f:
                content = f.read()

            assert "deleteAllKeyframes" in content


class TestDryRunAndLogging:
    def _generate(self):
        import tempfile
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "Scripts", "run_cache.sh")
        write_cache_script(
            output_path=path,
            shot_name="test",
            hip_filename="test.hip",
            cache_node_path="/obj/geo1/fc1",
            frame_start=1,
            frame_end=10,
        )
        with open(path) as f:
            return f.read()

    def test_dry_run_guard(self):
        content = self._generate()
        assert 'DRY_RUN=false' in content
        assert '--dry-run) DRY_RUN=true' in content
        assert '[ "$DRY_RUN" = true ]' in content
        assert "DRY RUN" in content

    def test_dry_run_exits_before_hython(self):
        content = self._generate()
        dry_pos = content.index("DRY RUN")
        exit_pos = content.index("exit 0", dry_pos)
        # Find the actual hython command (multiline), not the echo summary
        hython_pos = content.index("hython -c '\n")
        assert exit_pos < hython_pos

    def test_logging_setup(self):
        content = self._generate()
        assert 'LOGFILE="../cache_log.txt"' in content
        assert "tee -a" in content

    def test_elapsed_time(self):
        content = self._generate()
        assert "${SECONDS}s" in content

    def test_timestamps(self):
        content = self._generate()
        assert "date -Iseconds" in content
        assert "hostname" in content


class TestPythonLauncherCopied:
    def test_run_cache_py_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "Scripts", "run_cache.sh")
            write_cache_script(
                output_path=path,
                shot_name="test",
                hip_filename="test.hip",
                cache_node_path="/obj/geo1/fc1",
                frame_start=1,
                frame_end=10,
            )
            py = os.path.join(tmpdir, "Scripts", "run_cache.py")
            assert os.path.isfile(py)
