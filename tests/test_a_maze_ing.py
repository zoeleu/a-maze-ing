"""The a_maze_ing.py command and what the lib package exports."""
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

import lib
from lib import Config, Maze, TaintTransformer, WilsonsGenerator
from tests.helpers import VALID_CONFIG, WriteConfig

SCRIPT = str(Path(__file__).parent.parent / "a_maze_ing.py")


def run(monkeypatch: pytest.MonkeyPatch, *args: str) -> None:
    """Run a_maze_ing.py in this process, as if from the command line."""
    monkeypatch.setattr(sys, "argv", [SCRIPT, *args])
    runpy.run_path(SCRIPT, run_name="__main__")


def expected_output(path: str) -> str:
    """What the library alone builds for the config at *path*."""
    maze = Maze(Config(path))
    WilsonsGenerator().generate(maze)
    if not maze.config.perfect:
        TaintTransformer().transform(maze)
    return maze.get_output()


@pytest.mark.parametrize("perfect", ["True", "False"])
def test_writes_the_output_file(monkeypatch: pytest.MonkeyPatch,
                                write_config: WriteConfig, tmp_path: Path,
                                perfect: str) -> None:
    """The output file holds exactly what the library builds for the config,
    perfect or not."""
    text = VALID_CONFIG.replace("PERFECT=True", f"PERFECT={perfect}")
    text = text.replace("OUTPUT_FILE=maze.txt",
                        f"OUTPUT_FILE={tmp_path / 'out.txt'}")
    config = write_config(text)
    run(monkeypatch, config)
    assert (tmp_path / "out.txt").read_text() == expected_output(config)


def test_output_file_is_relative_to_the_working_directory(
        monkeypatch: pytest.MonkeyPatch, valid_config: str,
        in_tmp: Path) -> None:
    """A relative OUTPUT_FILE is written where the command is run from."""
    run(monkeypatch, valid_config)
    assert (in_tmp / "maze.txt").is_file()


def test_same_seed_same_file(monkeypatch: pytest.MonkeyPatch,
                             valid_config: str, in_tmp: Path) -> None:
    """Running twice with the same seed writes the same file."""
    run(monkeypatch, valid_config)
    first = (in_tmp / "maze.txt").read_text()
    run(monkeypatch, valid_config)
    assert (in_tmp / "maze.txt").read_text() == first


def test_warns_when_dead_ends_are_left(
        monkeypatch: pytest.MonkeyPatch, write_config: WriteConfig,
        in_tmp: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A braided maze that keeps dead ends is reported on stderr."""
    monkeypatch.setattr(TaintTransformer, "_transform",
                        lambda self, maze, seed: False)
    run(monkeypatch, write_config(
        VALID_CONFIG.replace("PERFECT=True", "PERFECT=False")))
    assert "could not remove all dead ends" in capsys.readouterr().err


def test_no_warning_for_a_perfect_maze(
        monkeypatch: pytest.MonkeyPatch, valid_config: str, in_tmp: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    """A perfect maze builds without printing anything to stderr."""
    run(monkeypatch, valid_config)
    assert capsys.readouterr().err == ""


def test_needs_a_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without a config argument the command fails."""
    with pytest.raises(IndexError):
        run(monkeypatch)


def test_bad_config_raises(monkeypatch: pytest.MonkeyPatch,
                           tmp_path: Path) -> None:
    """A missing config file stops the command with FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        run(monkeypatch, str(tmp_path / "missing.txt"))


def test_importing_does_not_run(monkeypatch: pytest.MonkeyPatch,
                                in_tmp: Path) -> None:
    """Importing the script, rather than running it, builds nothing."""
    monkeypatch.setattr(sys, "argv", [SCRIPT])
    runpy.run_path(SCRIPT, run_name="a_maze_ing")
    assert not (in_tmp / "maze.txt").exists()


def test_end_to_end(write_config: WriteConfig, tmp_path: Path) -> None:
    """Run as a real process, the command writes a well-formed output file: a
    10x8 hex grid, the entry, the exit and a path of N, E, S and W."""
    config = write_config(VALID_CONFIG)
    result = subprocess.run([sys.executable, SCRIPT, config], cwd=tmp_path,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    grid, footer = (tmp_path / "maze.txt").read_text().split("\n\n")
    rows = grid.splitlines()
    assert len(rows) == 8
    assert all(len(row) == 10 for row in rows)
    entry, exit, path = footer.splitlines()
    assert (entry, exit) == ("0,0", "9,7")
    assert set(path) <= set("NESW")


@pytest.mark.parametrize("name", lib.__all__)
def test_package_exports(name: str) -> None:
    """Every name in lib.__all__ can be imported from lib."""
    assert hasattr(lib, name)
