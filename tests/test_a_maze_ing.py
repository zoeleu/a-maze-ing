"""The a_maze_ing.py command and what the mazegen package exports."""
import runpy
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

import mazegen
from mazegen import Config, Maze, TaintTransformer, WilsonsGenerator
from ui import AMazeIngApp
from tests.helpers import VALID_CONFIG, WriteConfig

SCRIPT = str(Path(__file__).parent.parent / "a_maze_ing.py")


def run(monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    """Run a_maze_ing.py in this process, as if from the command line, and
    return its exit status. Under pytest there is no terminal, so it builds
    the maze without the interface."""
    monkeypatch.setattr(sys, "argv", [SCRIPT, *args])
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(SCRIPT, run_name="__main__")
    code = exited.value.code
    assert isinstance(code, int)
    return code


def script() -> dict[str, Any]:
    """The script's functions, imported without running it."""
    return runpy.run_path(SCRIPT, run_name="a_maze_ing")


def pretend_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend a person is at the terminal, so the script opens the
    interface. Call it from the test itself: pytest only puts its capturing
    sys.stdout in place once the test starts, after the fixtures."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)


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


def test_shows_progress_on_a_terminal(
        monkeypatch: pytest.MonkeyPatch, valid_config: str, in_tmp: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    """With stderr on a terminal, the build keeps rewriting a progress line
    there, and clears it once done."""
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)
    assert run(monkeypatch, valid_config) == 0
    err = capsys.readouterr().err
    assert "\r\033[Kcarving" in err
    assert "\r\033[Kwriting..." in err
    assert err.endswith("\r\033[K")


def test_no_warning_for_a_perfect_maze(
        monkeypatch: pytest.MonkeyPatch, valid_config: str, in_tmp: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    """A perfect maze builds without printing anything to stderr."""
    run(monkeypatch, valid_config)
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("args", [(), ("a.txt", "b.txt")])
def test_needs_exactly_one_config(monkeypatch: pytest.MonkeyPatch,
                                  capsys: pytest.CaptureFixture[str],
                                  args: tuple[str, ...]) -> None:
    """Without exactly one argument the command prints its usage and
    fails."""
    assert run(monkeypatch, *args) == 1
    assert "usage: python3 a_maze_ing.py <config file>" in \
        capsys.readouterr().err


def test_missing_config_is_reported(monkeypatch: pytest.MonkeyPatch,
                                    tmp_path: Path,
                                    capsys: pytest.CaptureFixture[str]
                                    ) -> None:
    """A missing config file is an error message, not a traceback."""
    assert run(monkeypatch, str(tmp_path / "missing.txt")) == 1
    err = capsys.readouterr().err
    assert "Error:" in err and "Config not found" in err
    assert "Traceback" not in err


@pytest.mark.parametrize("change, expected", [
    (("HEIGHT=8", "HEIGHT=a"), "HEIGHT: Invalid value"),
    (("EXIT=9,7", "EXIT=40,7"), "EXIT: Out of bounds"),
    (("WIDTH=10", "WIDTH=0"), "WIDTH: Invalid value"),
    (("EXIT=9,7", "EXIT=0,0"), "EXIT: Invalid value"),
    (("SEED=42", "SEED=42\nnot a pair"), "line 9: Bad syntax"),
])
def test_bad_config_names_the_problem(monkeypatch: pytest.MonkeyPatch,
                                      write_config: WriteConfig,
                                      capsys: pytest.CaptureFixture[str],
                                      change: tuple[str, str],
                                      expected: str) -> None:
    """An invalid config fails with a message that names the key or line
    at fault."""
    assert run(monkeypatch, write_config(VALID_CONFIG.replace(*change))) == 1
    assert expected in capsys.readouterr().err


def test_unwritable_output_is_reported(monkeypatch: pytest.MonkeyPatch,
                                       write_config: WriteConfig,
                                       tmp_path: Path,
                                       capsys: pytest.CaptureFixture[str]
                                       ) -> None:
    """An output file that cannot be written is an error message."""
    folder = tmp_path / "a_folder"
    folder.mkdir()
    config = write_config(VALID_CONFIG.replace(
        "OUTPUT_FILE=maze.txt", f"OUTPUT_FILE={folder}"))
    assert run(monkeypatch, config) == 1
    assert f"could not write {folder}" in capsys.readouterr().err


def test_opens_the_interface_in_a_terminal(monkeypatch: pytest.MonkeyPatch,
                                           valid_config: str) -> None:
    """With a person at the terminal, the app runs on the config."""
    opened: list[str] = []

    def fake_run(app: AMazeIngApp) -> None:
        """Record which config the app was started on."""
        opened.append(app.config_path)

    monkeypatch.setattr(AMazeIngApp, "run", fake_run)
    pretend_terminal(monkeypatch)
    assert script()["main"]([valid_config]) == 0
    assert opened == [valid_config]


@pytest.mark.parametrize("raised, code, message", [
    (KeyboardInterrupt(), 130, ""),
    (RuntimeError("boom"), 1, "Error: unexpected RuntimeError: boom"),
])
def test_interface_failures_are_reported(monkeypatch: pytest.MonkeyPatch,
                                         valid_config: str,
                                         capsys: pytest.CaptureFixture[str],
                                         raised: BaseException, code: int,
                                         message: str) -> None:
    """Ctrl+C quits quietly, and anything unexpected is an error message
    rather than a traceback."""
    def fake_run(app: AMazeIngApp) -> None:
        """Fail the way the test asks."""
        raise raised

    monkeypatch.setattr(AMazeIngApp, "run", fake_run)
    pretend_terminal(monkeypatch)
    assert script()["main"]([valid_config]) == code
    err = capsys.readouterr().err
    assert message in err
    assert "Traceback" not in err


def test_missing_interface_is_reported(monkeypatch: pytest.MonkeyPatch,
                                       valid_config: str,
                                       capsys: pytest.CaptureFixture[str]
                                       ) -> None:
    """Without Textual installed, the command says how to install it."""
    # None in sys.modules makes importing the module raise ImportError
    monkeypatch.setitem(sys.modules, "ui", None)
    assert script()["main"]([valid_config]) == 1
    assert "make install" in capsys.readouterr().err


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


@pytest.mark.parametrize("name", mazegen.__all__)
def test_package_exports(name: str) -> None:
    """Every name in mazegen.__all__ can be imported from mazegen."""
    assert hasattr(mazegen, name)
