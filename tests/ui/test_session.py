"""The UI's bridge to the library: config loading, sessions and replays."""
import re
from pathlib import Path

import pytest

from mazegen import (Config, Direction, GeneratorError, Maze,
                     MazeHistoryCallbackCell, TaintTransformer,
                     WilsonsGenerator)
from ui import session as session_module
from ui.session import (ALGORITHMS, CLOSED, CellEvent, ConfigProblem,
                        Event, MazeRun, Replay, Session, WallChange,
                        dead_ends, load_config)
from tests.helpers import VALID_CONFIG, MakeConfig, MakeMaze, WriteConfig

Kind = MazeHistoryCallbackCell
N, E, S, W = Direction.NORTH, Direction.EAST, Direction.SOUTH, Direction.WEST


def config_with(**values: str) -> str:
    """VALID_CONFIG with the given keys replaced."""
    text = VALID_CONFIG
    for key, value in values.items():
        text = re.sub(rf"^{key}=.*$", f"{key}={value}", text, flags=re.M)
    return text


def problem_for(write_config: WriteConfig, text: str) -> ConfigProblem:
    """The ConfigProblem raised when loading a config of *text*."""
    with pytest.raises(ConfigProblem) as info:
        load_config(write_config(text))
    return info.value


class TestLoadConfig:
    """load_config, which turns every config error into a ConfigProblem."""

    def test_valid(self, valid_config: str) -> None:
        """A valid config is returned as a Config."""
        config = load_config(valid_config)
        assert isinstance(config, Config)
        assert config.width == 10

    def test_not_found(self, tmp_path: Path) -> None:
        """A missing file says where it was looked for."""
        path = str(tmp_path / "missing.txt")
        with pytest.raises(ConfigProblem) as info:
            load_config(path)
        assert info.value.title == "Config not found"
        assert info.value.detail == f"There is no file at {path}."
        assert info.value.path == path

    def test_missing_keys(self, write_config: WriteConfig) -> None:
        """Missing keys are listed, sorted."""
        problem = problem_for(write_config, "PERFECT=True\nWIDTH=3\n")
        assert problem.title == "Missing keys"
        assert problem.detail == ("Add ENTRY, EXIT, HEIGHT, OUTPUT_FILE "
                                  "to the config.")
        assert problem.key is None

    def test_other_index_error(self, valid_config: str,
                               monkeypatch: pytest.MonkeyPatch) -> None:
        """Any other IndexError is passed on as an invalid config."""
        def broken(path: str) -> None:
            """Stand-in for Config: raises an unexpected IndexError."""
            raise IndexError("list index out of range")
        monkeypatch.setattr(session_module, "Config", broken)
        with pytest.raises(ConfigProblem) as info:
            load_config(valid_config)
        assert info.value.title == "Invalid config"
        assert info.value.detail == "list index out of range"

    def test_binary_file(self, tmp_path: Path) -> None:
        """A file that is not text is reported as unreadable."""
        path = tmp_path / "binary"
        path.write_bytes(b"\xff\xfe\x00")
        with pytest.raises(ConfigProblem) as info:
            load_config(str(path))
        assert info.value.title == "Unreadable config"
        assert info.value.detail == "The file is not plain text."

    def test_bad_syntax(self, write_config: WriteConfig) -> None:
        """A line without = is reported with its 0-based line number."""
        problem = problem_for(write_config,
                              VALID_CONFIG.replace("HEIGHT=8", "HEIGHT 8"))
        assert problem.title == "Bad syntax"
        assert problem.detail == "Every line must be KEY=VALUE."
        assert problem.line == 2  # 0-based: the third line

    @pytest.mark.parametrize(("key", "value", "detail"), [
        ("WIDTH", "ten", "WIDTH must be a whole number of cells"),
        ("HEIGHT", "", "HEIGHT must be a whole number of cells"),
        ("ENTRY", "0;0", "ENTRY must be a cell written x,y"),
        ("EXIT", "x", "EXIT must be a cell written x,y"),
        ("OUTPUT_FILE", "", "OUTPUT_FILE must be a file name"),
        ("PERFECT", "maybe", "PERFECT must be True or False"),
    ])
    def test_unparsable_value(self, write_config: WriteConfig, key: str,
                              value: str, detail: str) -> None:
        """A value that does not parse says what the key expects."""
        problem = problem_for(write_config, config_with(**{key: value}))
        assert problem.title == "Invalid value"
        assert problem.detail == detail
        assert problem.key == key
        assert problem.part is None

    @pytest.mark.parametrize(("key", "value", "part"), [
        ("ENTRY", "10,0", 0),
        ("ENTRY", "0,8", 1),
        ("EXIT", "50,50", 0),
    ])
    def test_out_of_bounds(self, write_config: WriteConfig, key: str,
                           value: str, part: int) -> None:
        """A cell outside the maze names its key and the wrong coordinate."""
        problem = problem_for(write_config, config_with(**{key: value}))
        assert problem.title == "Out of bounds"
        assert problem.key == key
        assert problem.part == part
        assert problem.detail.startswith("xy"[part] + " must be between")

    @pytest.mark.parametrize(("values", "key", "detail"), [
        ({"WIDTH": "0"}, "WIDTH", "must be at least 1"),
        ({"EXIT": "0,0"}, "EXIT", "must be a different cell from ENTRY"),
        ({"ENTRY": "1,1"}, "ENTRY", "falls on the 42 pattern"),
    ])
    def test_invalid_value(self, write_config: WriteConfig,
                           values: dict[str, str], key: str,
                           detail: str) -> None:
        """Other bad values name their key and the reason."""
        problem = problem_for(write_config, config_with(**values))
        assert problem.title == "Invalid value"
        assert problem.key == key
        assert problem.detail == detail

    def test_unknown_key_gets_a_generic_hint(
            self, valid_config: str,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """A key without its own hint is told to be valid."""
        def broken(path: str) -> None:
            """Stand-in for Config: rejects SEED."""
            raise ValueError("Invalid value `x` at key `SEED`: in config "
                             "file")
        monkeypatch.setattr(session_module, "Config", broken)
        with pytest.raises(ConfigProblem) as info:
            load_config(valid_config)
        assert info.value.detail == "SEED must be valid"

    def test_unrecognised_value_error(
            self, valid_config: str,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """A ValueError in an unknown format is passed on as it is."""
        def broken(path: str) -> None:
            """Stand-in for Config: raises an unexpected ValueError."""
            raise ValueError("something else")
        monkeypatch.setattr(session_module, "Config", broken)
        with pytest.raises(ConfigProblem) as info:
            load_config(valid_config)
        assert info.value.title == "Invalid value"
        assert info.value.detail == "something else"
        assert info.value.key is None

    @pytest.mark.parametrize(("error", "detail"), [
        (PermissionError(13, "Permission denied"), "Permission denied"),
        (OSError("disk on fire"), "disk on fire"),
    ])
    def test_os_error(self, valid_config: str,
                      monkeypatch: pytest.MonkeyPatch, error: OSError,
                      detail: str) -> None:
        """An error reading the file is reported with its reason."""
        def broken(path: str) -> None:
            """Stand-in for Config: raises *error*."""
            raise error
        monkeypatch.setattr(session_module, "Config", broken)
        with pytest.raises(ConfigProblem) as info:
            load_config(valid_config)
        assert info.value.title == "Unreadable config"
        assert info.value.detail == detail

    def test_problems_hide_the_original_traceback(
            self, tmp_path: Path) -> None:
        """The original exception is not chained, so tracebacks stay short."""
        with pytest.raises(ConfigProblem) as info:
            load_config(str(tmp_path / "missing"))
        assert info.value.__suppress_context__


class TestConfigProblem:
    """ConfigProblem, and how it finds the spot to point at."""

    def test_message(self) -> None:
        """The message is the title and the detail."""
        problem = ConfigProblem("Title", "detail", "path")
        assert str(problem) == "Title: detail"
        assert isinstance(problem, Exception)

    def test_defaults(self) -> None:
        """Key, part and line are unknown unless given."""
        problem = ConfigProblem("Title", "detail", "path")
        assert (problem.key, problem.part, problem.line) == (None, None,
                                                             None)

    def test_source(self, write_config: WriteConfig) -> None:
        """source() reads the config's lines."""
        problem = ConfigProblem("T", "d", write_config("A=1\nB=2\n"))
        assert problem.source() == ["A=1", "B=2"]

    def test_source_of_a_missing_file(self, tmp_path: Path) -> None:
        """A missing file has no lines."""
        assert ConfigProblem("T", "d", str(tmp_path / "x")).source() == []

    def test_source_of_a_binary_file(self, tmp_path: Path) -> None:
        """A file that is not text has no lines."""
        path = tmp_path / "binary"
        path.write_bytes(b"\xff\xfe")
        assert ConfigProblem("T", "d", str(path)).source() == []

    LINES = ["# comment", "WIDTH = 10  ", "ENTRY=12,3", "#ENTRY=1,1",
             "OOPS", "EXIT=", "ENTRY=  4,567"]

    @pytest.mark.parametrize(("key", "part", "line", "spot"), [
        (None, None, 1, (1, 8, 10)),      # value, without the spaces
        (None, None, 4, (4, 0, 4)),       # no `=`: the whole line
        (None, None, 5, (5, 5, 6)),       # empty value: one character
        ("WIDTH", None, None, (1, 8, 10)),
        ("ENTRY", None, None, (6, 8, 13)),  # the last one counts
        ("ENTRY", 0, None, (6, 8, 9)),
        ("ENTRY", 1, None, (6, 10, 13)),
        ("ENTRY", 2, None, (6, 8, 13)),   # no such part: the whole value
        ("HEIGHT", None, None, None),     # not in the file
        (None, None, None, None),         # nothing to point at
        (None, None, 99, None),           # past the end
        (None, None, -1, None),
    ])
    def test_locate(self, key: str | None, part: int | None,
                    line: int | None,
                    spot: tuple[int, int, int] | None) -> None:
        """locate() finds the line and the characters to point at, or None."""
        problem = ConfigProblem("T", "d", "path", key=key, part=part,
                                line=line)
        assert problem.locate(self.LINES) == spot

    def test_located_text(self, write_config: WriteConfig) -> None:
        """The spot found for an out-of-bounds cell is the wrong coordinate."""
        problem = problem_for(write_config, config_with(ENTRY="0,99"))
        lines = problem.source()
        spot = problem.locate(lines)
        assert spot is not None
        index, start, end = spot
        assert lines[index][start:end] == "99"


@pytest.fixture
def session(valid_config: str, in_tmp: Path) -> Session:
    """A session for the valid config, in the test's temporary directory."""
    return Session(valid_config)


class TestSession:
    """Session, which builds the mazes the screens show."""

    def test_loads_the_config(self, session: Session,
                              valid_config: str) -> None:
        """A session starts from the config, with default choices."""
        assert session.config_path == valid_config
        assert session.config.width == 10
        assert session.seed == "42"
        assert (session.algorithm, session.wall_colour,
                session.logo_colour) == (0, 0, 0)
        assert session.expanded is False

    @pytest.mark.parametrize("line", ["SEED=", None])
    def test_picks_a_seed_when_there_is_none(
            self, write_config: WriteConfig, in_tmp: Path,
            line: str | None) -> None:
        """Without a seed in the config, a random 6-digit hex one is used."""
        text = VALID_CONFIG.replace("SEED=42\n", "" if line is None
                                    else line + "\n")
        session = Session(write_config(text))
        assert re.fullmatch(r"[0-9a-f]{6}", session.seed)

    def test_bad_config(self, write_config: WriteConfig) -> None:
        """A broken config raises ConfigProblem."""
        with pytest.raises(ConfigProblem):
            Session(write_config("nonsense"))

    def test_first_run(self, session: Session, in_tmp: Path) -> None:
        """The first maze is built, solved, counted and written out."""
        run = session.current
        assert isinstance(run, MazeRun)
        assert run.algorithm == ALGORITHMS[0][0]
        assert run.path[0] == (0, 0)
        assert run.path[-1] == (7, 9)
        assert len(run.path) - 1 == len(run.maze.solve())
        assert run.dead_ends == dead_ends(run.maze)
        assert run.braided is True
        assert run.elapsed >= 0
        assert run.write_error is None
        assert (in_tmp / "maze.txt").read_text() == run.maze.get_output()

    def test_path_is_a_chain_of_open_cells(self, session: Session) -> None:
        """Each step of the path goes through an open passage."""
        run = session.current
        for cell, other in zip(run.path, run.path[1:]):
            assert run.maze.is_open(cell, Direction.between(cell, other))

    def test_matches_the_library(self, session: Session,
                                 make_maze: MakeMaze) -> None:
        """The session builds the same maze as the library alone."""
        maze = make_maze(width=10, height=8, seed="42")
        WilsonsGenerator().generate(maze)
        assert session.current.maze.grid == maze.grid

    def test_perfect_history_is_all_carving(self, session: Session) -> None:
        """A perfect maze's history all comes from the generator."""
        run = session.current
        assert run.carved == len(run.history)
        assert run.history is run.maze.history  # type: ignore[attr-defined]

    def test_braided_history(self, write_config: WriteConfig,
                             in_tmp: Path) -> None:
        """A braided maze's history goes on after the carving, and only the two
        pockets of the 2 are left as dead ends."""
        session = Session(write_config(config_with(PERFECT="False")))
        run = session.current
        assert 0 < run.carved < len(run.history)
        assert run.dead_ends == 2  # the pockets inside the 2

    def test_does_not_change_the_config_seed(
            self, write_config: WriteConfig, in_tmp: Path) -> None:
        """The picked seed goes into the maze's config, not the session's."""
        session = Session(write_config(VALID_CONFIG.replace("SEED=42\n",
                                                            "")))
        assert session.config.seed is None
        assert session.current.maze.config.seed == session.seed

    def test_regenerate(self, session: Session) -> None:
        """regenerate() builds a new maze from a new seed."""
        first = session.current
        run = session.regenerate()
        assert run is session.current
        assert run is not first
        assert session.seed != "42"
        assert run.maze.config.seed == session.seed

    def test_toggle_perfect(self, session: Session) -> None:
        """toggle_perfect() switches mode, keeps the seed, and switching back
        gives the first maze again."""
        perfect = session.current
        braided = session.toggle_perfect()
        assert session.config.perfect is False
        assert braided.maze.config.perfect is False
        assert session.seed == "42"
        assert braided.dead_ends < perfect.dead_ends
        again = session.toggle_perfect()
        assert session.config.perfect is True
        assert again.maze.grid == perfect.maze.grid

    def test_next_algorithm_with_one_algorithm(self,
                                               session: Session) -> None:
        """With one algorithm, next_algorithm() rebuilds with the same one."""
        run = session.next_algorithm()
        assert session.algorithm == 0
        assert run is session.current
        assert session.seed == "42"

    def test_next_algorithm_cycles(self, session: Session,
                                   monkeypatch: pytest.MonkeyPatch) -> None:
        """next_algorithm() goes through each algorithm, then back."""
        monkeypatch.setattr(session_module, "ALGORITHMS", [
            ("first", WilsonsGenerator), ("second", WilsonsGenerator)])
        assert session.next_algorithm().algorithm == "second"
        assert session.next_algorithm().algorithm == "first"

    def test_impossible_maze(self, session: Session,
                             monkeypatch: pytest.MonkeyPatch) -> None:
        """A GeneratorError becomes an Impossible maze problem."""
        def fail(self: WilsonsGenerator, maze: Maze,
                 seed: str | None) -> None:
            """Stand-in for Wilson's algorithm: always fails."""
            raise GeneratorError("no room")
        monkeypatch.setattr(WilsonsGenerator, "_generate", fail)
        with pytest.raises(ConfigProblem) as info:
            session.regenerate()
        assert info.value.title == "Impossible maze"
        assert info.value.detail == "no room"

    def test_no_way_out(self, write_config: WriteConfig, in_tmp: Path,
                        monkeypatch: pytest.MonkeyPatch) -> None:
        """An exit that cannot be reached becomes a No way out problem."""
        def wall_in_the_exit(self: TaintTransformer, maze: Maze,
                             seed: str | None) -> bool:
            """Stand-in for the braiding: walls the exit in."""
            maze[(7, 9)] = CLOSED
            return True
        monkeypatch.setattr(TaintTransformer, "_transform",
                            wall_in_the_exit)
        with pytest.raises(ConfigProblem) as info:
            Session(write_config(config_with(PERFECT="False")))
        assert info.value.title == "No way out"
        assert info.value.key == "EXIT"

    def test_write_error(self, write_config: WriteConfig,
                         in_tmp: Path) -> None:
        """A failed write is kept on the run with the reason."""
        (in_tmp / "taken").mkdir()
        session = Session(write_config(config_with(OUTPUT_FILE="taken")))
        assert session.current.write_error == "Is a directory"

    def test_write_error_without_strerror(
            self, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
        """An error without strerror is kept as its message."""
        def broken(*args: object, **kwargs: object) -> None:
            """Stand-in for open(): always fails."""
            raise ValueError("bad name")
        # only the session module's open(): replacing the builtin also
        # breaks PyPy's os.urandom, which the new seed needs
        monkeypatch.setattr(session_module, "open", broken, raising=False)
        assert session.regenerate().write_error == "bad name"


class TestRecordingMaze:
    """The maze that records its changes so they can be replayed."""

    def test_records_wall_changes(self, make_config: MakeConfig) -> None:
        """Every wall change is recorded, for both cells of a passage."""
        maze = session_module._RecordingMaze(make_config(width=3, height=1))
        assert maze.history == []
        maze.open_path((0, 0), E)
        assert maze.history == [WallChange((0, 0), N | S | W),
                                WallChange((0, 1), N | E | S)]

    def test_records_generator_events(self,
                                      make_config: MakeConfig) -> None:
        """record() keeps what the generator reported."""
        maze = session_module._RecordingMaze(make_config())
        maze.record((1, 2), Kind.MAYBE)
        assert maze.history == [CellEvent((1, 2), Kind.MAYBE)]


def test_dead_ends(make_maze: MakeMaze) -> None:
    """Cells with a single opening are dead ends."""
    maze = make_maze(width=3, height=1, exit=(2, 0))
    assert dead_ends(maze) == 0
    maze.open_path((0, 0), E)
    assert dead_ends(maze) == 2
    maze.open_path((0, 1), E)
    assert dead_ends(maze) == 2  # the two ends of the corridor


def test_dead_ends_ignore_the_logo(make_maze: MakeMaze,
                                   monkeypatch: pytest.MonkeyPatch) -> None:
    """Logo cells are never counted as dead ends."""
    maze = make_maze(width=2, height=1, exit=(1, 0))
    maze.open_path((0, 0), E)
    monkeypatch.setattr(maze, "in_logo", lambda cell: cell == (0, 0))
    assert dead_ends(maze) == 1


def test_new_seed() -> None:
    """New seeds are six hex digits, and not always the same."""
    seeds = {session_module._new_seed() for _ in range(20)}
    assert all(re.fullmatch(r"[0-9a-f]{6}", seed) for seed in seeds)
    assert len(seeds) > 1


def make_run(maze: Maze, history: list[Event], carved: int) -> MazeRun:
    """A MazeRun for *maze* with a made-up *history*."""
    return MazeRun(maze=maze, algorithm="test", history=history,
                   carved=carved, path=[], dead_ends=0, braided=True,
                   elapsed=0.0, write_error=None)


class TestReplay:
    """Replay, which steps through how a maze was built."""

    def test_starts_walled_up(self, session: Session) -> None:
        """A replay starts from a fully walled maze, carving."""
        replay = Replay(session.current)
        assert all(walls == CLOSED for _, _, walls in replay.maze)
        assert replay.position == 0
        assert replay.touched == 0
        assert replay.walk == []
        assert replay.playable == 80 - 18
        assert not replay.done
        assert replay.phase == "carving"

    def test_does_not_touch_the_run(self, session: Session) -> None:
        """Replaying leaves the run's maze and history as they were."""
        run = session.current
        grid = [row[:] for row in run.maze.grid]
        length = len(run.history)
        replay = Replay(run)
        replay.finish()
        assert run.maze.grid == grid
        assert len(run.history) == length

    def test_finish_rebuilds_the_maze(self, session: Session) -> None:
        """Replaying everything gives back the finished maze."""
        replay = Replay(session.current)
        replay.finish()
        assert replay.done
        assert replay.phase == "done"
        assert replay.maze.grid == session.current.maze.grid
        assert replay.walk == []
        assert replay.touched == sum(1 for _, _, walls in replay.maze
                                     if walls != CLOSED)
        assert replay.touched == replay.playable

    def test_advance_steps_through_the_history(self,
                                               session: Session) -> None:
        """advance() moves by as many events as asked, up to the end."""
        replay = Replay(session.current)
        replay.advance(5)
        assert replay.position == 5
        replay.advance(0)
        assert replay.position == 5
        replay.advance(10 ** 9)
        assert replay.position == len(session.current.history)
        replay.advance(1)  # nothing left
        assert replay.position == len(session.current.history)

    def test_phases_of_a_braided_run(self, write_config: WriteConfig,
                                     in_tmp: Path) -> None:
        """The phase goes from carving to braiding to done."""
        run = Session(write_config(config_with(PERFECT="False"))).current
        replay = Replay(run)
        replay.advance(run.carved - 1)
        assert replay.phase == "carving"
        replay.advance(1)
        assert replay.phase == "braiding"
        replay.finish()
        assert replay.phase == "done"
        assert replay.maze.grid == run.maze.grid

    def test_walk(self, make_maze: MakeMaze) -> None:
        """The walk follows MAYBE, RESET, OPEN and MAZE_RESET events."""
        maze = make_maze(width=4, height=1, exit=(3, 0))
        history: list[Event] = [
            CellEvent((0, 0), Kind.MAYBE),
            CellEvent((0, 1), Kind.MAYBE),
            CellEvent((0, 2), Kind.MAYBE),
            CellEvent((0, 2), Kind.RESET),     # a loop is erased
            CellEvent((0, 0), Kind.OPEN),      # a cell joins the maze
            CellEvent((0, 3), Kind.MAYBE),
            CellEvent((0, 0), Kind.MAZE_RESET),
            CellEvent((0, 1), Kind.MAYBE),
            CellEvent((0, 3), Kind.OPEN),      # not on the walk: ignored
        ]
        replay = Replay(make_run(maze, history, len(history)))
        walks = []
        for _ in history:
            replay.advance(1)
            walks.append(list(replay.walk))
        assert walks == [
            [(0, 0)],
            [(0, 0), (0, 1)],
            [(0, 0), (0, 1), (0, 2)],
            [(0, 0), (0, 1)],
            [(0, 1)],
            [(0, 1), (0, 3)],
            [],
            [(0, 1)],
            [],  # done: the walk is dropped
        ]

    def test_walk_is_dropped_once_done(self, make_maze: MakeMaze) -> None:
        """The walk is cleared when the replay ends."""
        maze = make_maze(width=2, height=1, exit=(1, 0))
        replay = Replay(make_run(maze, [CellEvent((0, 0), Kind.MAYBE)], 1))
        replay.advance(1)
        assert replay.done
        assert replay.walk == []

    def test_touched_counts_cells_with_an_opening(
            self, make_maze: MakeMaze) -> None:
        """touched counts the cells that have at least one wall down."""
        maze = make_maze(width=2, height=1, exit=(1, 0))
        history: list[Event] = [
            WallChange((0, 0), N | S | W),
            WallChange((0, 1), N | E | S),
            WallChange((0, 0), CLOSED),     # closed again
            WallChange((0, 1), N | S),      # still open
        ]
        replay = Replay(make_run(maze, history, 4))
        counts = []
        for _ in history:
            replay.advance(1)
            counts.append(replay.touched)
        assert counts == [1, 2, 1, 1]
        assert replay.maze[(0, 1)] == N | S

    def test_empty_history(self, make_maze: MakeMaze) -> None:
        """A run with no history is done from the start."""
        replay = Replay(make_run(make_maze(), [], 0))
        assert replay.done
        assert replay.phase == "done"
