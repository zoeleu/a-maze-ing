"""The main screen, the replay screen and how they lay the maze out."""
import dataclasses
import math
from typing import Any

import pytest
from textual.pilot import Pilot
from textual.screen import Screen
from textual.timer import Timer, TimerCallback
from textual.widgets import Button, Label, Static

from mazegen import WilsonsGenerator
from ui import app as app_module
from ui import session as session_module
from ui.mlx_window import WindowState
from ui.renderer import (LOGO_COLOURS, WALL_COLOURS, AMazeIngRenderer,
                         Tile)
from ui.screens import (ErrorScreen, GeneratorScreen, MainScreen,
                        MazeBody, ProblemFound, badge, readout)
from ui.screens import generator as generator_module
from ui.screens import main as main_module
from ui.session import ConfigProblem, MazeRun, Session
from tests.helpers import VALID_CONFIG, WriteConfig
from tests.ui.helpers import Drive, fake_window, plain, state_of

pytestmark = pytest.mark.ui

TWO_ALGORITHMS = [("first (walk)", WilsonsGenerator),
                  ("second (walk)", WilsonsGenerator)]
ONE_ALGORITHM = [("only (walk)", WilsonsGenerator)]


def sized(write_config: WriteConfig, width: int, height: int,
          perfect: bool = True) -> str:
    """A config for a maze of *width* x *height*, exit in the far corner."""
    return write_config(
        VALID_CONFIG.replace("WIDTH=10", f"WIDTH={width}")
        .replace("HEIGHT=8", f"HEIGHT={height}")
        .replace("EXIT=9,7", f"EXIT={width - 1},{height - 1}")
        .replace("PERFECT=True", f"PERFECT={perfect}"))


Ticks = list[tuple[float, TimerCallback | None]]


@pytest.fixture(autouse=True)
def manual_ticks(monkeypatch: pytest.MonkeyPatch) -> Ticks:
    """Create the replay screen's timer paused, so the replay only moves when
    a test calls _tick() itself, whatever the speed of the machine. Returns
    the interval and callback each replay timer was created with."""
    created: Ticks = []

    def paused_interval(self: GeneratorScreen, interval: float,
                        callback: TimerCallback | None = None,
                        **kwargs: Any) -> Timer:
        """Stand-in for set_interval: the replay's timer never fires, and
        Textual's own timers are left alone."""
        if callback == self._tick:
            created.append((interval, callback))
            kwargs["pause"] = True
        return Screen.set_interval(self, interval, callback, **kwargs)
    monkeypatch.setattr(GeneratorScreen, "set_interval", paused_interval)
    return created


def main_screen(pilot: Pilot[None]) -> MainScreen:
    """The current screen, which must be the main screen."""
    screen = pilot.app.screen
    assert isinstance(screen, MainScreen)
    return screen


def generator_screen(pilot: Pilot[None]) -> GeneratorScreen:
    """The current screen, which must be the replay screen."""
    screen = pilot.app.screen
    assert isinstance(screen, GeneratorScreen)
    return screen


def text_of(pilot: Pilot[None], selector: str) -> str:
    """The text of the Static matching *selector* on the current screen."""
    return plain(pilot.app.screen.query_one(selector, Static))


def badge_of(pilot: Pilot[None]) -> str:
    """The text of the title bar's badge."""
    return plain(pilot.app.screen.query_one("#badge", Label))


def offered(pilot: Pilot[None], action: str) -> bool | None:
    """Whether the current screen offers *action* right now."""
    return pilot.app.screen.check_action(action, ())


class TestHelpers:
    """The small helpers the main screen is built with."""

    def test_readout(self) -> None:
        """readout() makes a two-column table with right-aligned values."""
        table = readout(("a", "1"), ("b", "2"))
        assert table.row_count == 2
        assert len(table.columns) == 2
        assert table.columns[1].justify == "right"

    def test_badge(self, valid_config: str, in_tmp: object) -> None:
        """The badge reads PERFECT in gold or PAC-MAN in cyan."""
        session = Session(valid_config)
        assert badge(session.current) == ("PERFECT", "gold")
        assert badge(session.toggle_perfect()) == ("PAC-MAN", "cyan")


class TestStatus:
    """The status line under the maze."""

    @pytest.fixture
    def run(self, valid_config: str, in_tmp: object) -> MazeRun:
        """A finished run for the valid config."""
        return Session(valid_config).current

    @pytest.mark.parametrize(("elapsed", "took"), [
        (0.0, "<1 ms"), (0.0009, "<1 ms"), (0.001, "1 ms"),
        (0.0123, "12 ms"), (2.5, "2500 ms"),
    ])
    def test_build_time(self, run: MazeRun, elapsed: float,
                        took: str) -> None:
        """The build time is shown in whole milliseconds, or <1 ms."""
        status = MainScreen._status(dataclasses.replace(run,
                                                        elapsed=elapsed))
        assert status.plain == f"✓ wrote maze.txt · built in {took}"

    def test_write_error(self, run: MazeRun) -> None:
        """A failed write is shown with the reason."""
        status = MainScreen._status(dataclasses.replace(
            run, elapsed=0.0, write_error="Is a directory"))
        assert status.plain == ("✗ could not write maze.txt: Is a directory"
                                " · built in <1 ms")

    def test_dead_ends_left(self, run: MazeRun) -> None:
        """Dead ends that could not be removed are mentioned."""
        status = MainScreen._status(dataclasses.replace(run, braided=False))
        assert status.plain.endswith(" · some dead ends could not be "
                                     "removed")


class TestMainScreen:
    """The screen that shows the maze and lets the user play with it."""

    def test_panels(self, drive: Drive, valid_config: str) -> None:
        """The panels show the config, the numbers, the status and the maze."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Check every panel against the session's current run."""
            run = main_screen(pilot).session.current
            config = text_of(pilot, "#config")
            assert config.split("\n") == [
                "WIDTH=10", "HEIGHT=8", "ENTRY=0,0", "EXIT=9,7",
                "OUTPUT_FILE=maze.txt", "PERFECT=True", "SEED=42"]
            stats = text_of(pilot, "#stats")
            for label, value in (("mode", "perfect"),
                                 ("algorithm", "wilson's"),
                                 ("shortest path", str(len(run.path) - 1)),
                                 ("dead ends", str(run.dead_ends)),
                                 ("walls", "chalk"), ("42", "violet")):
                assert any(line.split() == [*label.split(), value]
                           for line in stats.splitlines())
            assert text_of(pilot, "#status").startswith("✓ wrote maze.txt")
            assert badge_of(pilot) == "PERFECT"
            renderer = pilot.app.screen.query_one(AMazeIngRenderer)
            assert renderer.maze is run.maze
            assert renderer.path == run.path
            assert not pilot.app.screen.query_one("#warning").display
            assert text_of(pilot, "#note") == ""
        drive(valid_config, scenario)

    def test_warns_when_the_logo_does_not_fit(
            self, drive: Drive, write_config: WriteConfig) -> None:
        """A maze too small for the logo gets a banner and a note."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Check the banner is shown and both texts."""
            assert pilot.app.screen.query_one("#warning").display
            assert "7×5 is too small for the “42” pattern" in \
                text_of(pilot, "#warning")
            assert "also printed to the console" in text_of(pilot, "#note")
        drive(sized(write_config, 7, 5), scenario)

    def test_regenerate(self, drive: Drive, valid_config: str) -> None:
        """R builds a new maze from a new seed, shown everywhere."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Press R and check the run, the seed, the bar and the config
            panel."""
            screen = main_screen(pilot)
            first = screen.session.current
            await pilot.press("r")
            assert screen.session.current is not first
            seed = screen.session.seed
            assert seed != "42"
            assert plain(screen.query_one("#seed", Label)) == f"seed {seed}"
            assert f"SEED={seed}" in text_of(pilot, "#config")
        drive(valid_config, scenario)

    def test_toggle_path(self, drive: Drive, valid_config: str) -> None:
        """P hides and shows the path, offering only the key that applies."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Press P twice, checking the path and the keys offered."""
            renderer = pilot.app.screen.query_one(AMazeIngRenderer)
            assert offered(pilot, "hide_path")
            assert not offered(pilot, "show_path")
            await pilot.press("p")
            assert not renderer.show_path
            assert offered(pilot, "show_path")
            assert not offered(pilot, "hide_path")
            await pilot.press("p")
            assert renderer.show_path
        drive(valid_config, scenario)

    def test_wall_colours_cycle(self, drive: Drive,
                                valid_config: str) -> None:
        """C cycles through the wall colours and back to the first."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Press C once, check the colour, then go round to the first."""
            screen = main_screen(pilot)
            renderer = screen.query_one(AMazeIngRenderer)
            await pilot.press("c")
            assert screen.session.wall_colour == 1
            assert renderer.wall_colour == WALL_COLOURS[1].hex
            assert WALL_COLOURS[1].name in text_of(pilot, "#stats")
            for _ in range(len(WALL_COLOURS) - 1):
                await pilot.press("c")
            assert screen.session.wall_colour == 0
        drive(valid_config, scenario)

    def test_logo_colours_cycle(self, drive: Drive,
                                valid_config: str) -> None:
        """F cycles through the 42 colours and back to the first."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Press F once, check the colour, then go round to the first."""
            screen = main_screen(pilot)
            renderer = screen.query_one(AMazeIngRenderer)
            await pilot.press("f")
            assert screen.session.logo_colour == 1
            assert renderer.logo_colour == LOGO_COLOURS[1].hex
            assert LOGO_COLOURS[1].name in text_of(pilot, "#stats")
            for _ in range(len(LOGO_COLOURS) - 1):
                await pilot.press("f")
            assert screen.session.logo_colour == 0
        drive(valid_config, scenario)

    def test_toggle_mode(self, drive: Drive, valid_config: str) -> None:
        """M switches between perfect and pac-man, keeping the seed."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Press M twice, checking the badge, the stats and the config."""
            screen = main_screen(pilot)
            await pilot.press("m")
            assert screen.session.config.perfect is False
            assert badge_of(pilot) == "PAC-MAN"
            assert "pac-man" in text_of(pilot, "#stats")
            assert "PERFECT=False" in text_of(pilot, "#config")
            assert screen.session.seed == "42"
            await pilot.press("m")
            assert badge_of(pilot) == "PERFECT"
        drive(valid_config, scenario)

    @pytest.mark.parametrize(("key", "method"), [
        ("r", "regenerate"), ("m", "toggle_perfect"),
    ])
    def test_problems_show_the_error_screen(
            self, drive: Drive, valid_config: str,
            monkeypatch: pytest.MonkeyPatch, key: str, method: str) -> None:
        """A problem while rebuilding the maze shows the error screen."""
        def fail(self: Session) -> MazeRun:
            """Stand-in for the session method: always fails."""
            raise ConfigProblem("Impossible maze", "no room",
                                self.config_path)
        monkeypatch.setattr(Session, method, fail)

        async def scenario(pilot: Pilot[None]) -> None:
            """Press *key* and check the error screen shows the problem."""
            await pilot.press(key)
            await pilot.pause()
            screen = pilot.app.screen
            assert isinstance(screen, ErrorScreen)
            assert screen.problem.detail == "no room"
        drive(valid_config, scenario)

    def test_animate_and_back(self, drive: Drive, valid_config: str) -> None:
        """G opens the replay of the same session, and Esc comes back."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Open the replay, check its session, and go back."""
            main = main_screen(pilot)
            await pilot.press("g")
            replay = generator_screen(pilot)
            assert replay.session is main.session
            await pilot.press("escape")
            await pilot.pause()
            assert pilot.app.screen is main
        drive(valid_config, scenario)

    def test_catches_up_after_the_replay_screen(
            self, drive: Drive, valid_config: str,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """Changes made on the replay screen show once back on the main one."""
        monkeypatch.setattr(session_module, "ALGORITHMS", TWO_ALGORITHMS)
        monkeypatch.setattr(generator_module, "ALGORITHMS", TWO_ALGORITHMS)

        async def scenario(pilot: Pilot[None]) -> None:
            """Switch algorithm on the replay screen, go back, and check the
            stats."""
            await pilot.press("g", "a", "escape")
            await pilot.pause()
            main_screen(pilot)
            assert "second" in text_of(pilot, "#stats")
        drive(valid_config, scenario)


class TestGeneratorScreen:
    """The screen that replays how the maze was built."""

    async def open(self, pilot: Pilot[None]) -> GeneratorScreen:
        """Open the replay screen from the main screen and return it."""
        await pilot.press("g")
        await pilot.pause()
        return generator_screen(pilot)

    def test_ticks_move_the_replay(self, drive: Drive, valid_config: str,
                                   manual_ticks: Ticks) -> None:
        """The screen ticks FPS times a second, each tick replays the speed's
        number of events, and untouched cells are drawn dimmed."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Check the timer, tick once and check the replay moved on."""
            screen = await self.open(pilot)
            assert manual_ticks == [(1 / generator_module.FPS, screen._tick)]
            assert badge_of(pilot) == "GENERATING"
            assert screen.replay.position == 0
            screen._tick()
            assert screen.replay.position == \
                generator_module.SPEEDS[screen.speed]
            assert screen.frame == 1
            renderer = screen.query_one(AMazeIngRenderer)
            assert renderer.dim_untouched
            assert renderer.maze is screen.replay.maze
        drive(valid_config, scenario)

    def test_finishes_on_its_own(self, drive: Drive,
                                 write_config: WriteConfig) -> None:
        """Ticked to the end, the replay shows the finished maze and its
        path."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Tick until done, then check the screen and the keys offered."""
            screen = await self.open(pilot)
            events = len(screen.replay.run.history)
            while not screen.replay.done:
                screen._tick()
            per_tick = generator_module.SPEEDS[screen.speed]
            assert screen.frame == math.ceil(events / per_tick)
            assert badge_of(pilot) == "DONE"
            run = screen.session.current
            status = text_of(pilot, "#status")
            assert status.startswith("✓")
            assert "100%" in status
            assert f"shortest path {len(run.path) - 1}" in status
            renderer = screen.query_one(AMazeIngRenderer)
            assert renderer.maze is run.maze
            assert renderer.path == run.path
            assert offered(pilot, "replay")
            assert not offered(pilot, "pause")
            assert not offered(pilot, "skip")
        drive(sized(write_config, 3, 3), scenario)

    def test_pause_and_resume(self, drive: Drive,
                              valid_config: str) -> None:
        """Space pauses and resumes the replay."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Pause, check nothing moves, then resume."""
            screen = await self.open(pilot)
            assert offered(pilot, "pause")
            assert not offered(pilot, "resume")
            await pilot.press("space")
            assert screen.paused
            assert badge_of(pilot) == "PAUSED"
            assert text_of(pilot, "#status").startswith("‖")
            assert offered(pilot, "resume")
            assert not offered(pilot, "pause")
            screen._tick()
            assert screen.replay.position == 0
            assert screen.frame == 0
            await pilot.press("space")
            assert not screen.paused
            assert badge_of(pilot) == "GENERATING"
            screen._tick()
            assert screen.replay.position > 0
        drive(valid_config, scenario)

    def test_skip_then_replay(self, drive: Drive, valid_config: str) -> None:
        """S skips to the end, and R then replays from the start."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Skip, check it is done, then replay."""
            screen = await self.open(pilot)
            assert not offered(pilot, "replay")
            await pilot.press("space", "s")
            assert screen.replay.done
            assert badge_of(pilot) == "DONE"
            await pilot.press("r")
            assert screen.replay.position == 0
            assert not screen.paused  # replaying resumes
            assert screen.replay.run is screen.session.current
        drive(valid_config, scenario)

    def test_speed(self, drive: Drive, valid_config: str) -> None:
        """- and + change the speed, within its limits."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Slow down past the slowest and speed up past the fastest."""
            screen = await self.open(pilot)
            speeds = generator_module.SPEEDS
            assert screen.speed == 3
            await pilot.press("minus")
            assert screen.speed == 2
            assert "×4 (" in text_of(pilot, "#progress")
            await pilot.press(*["minus"] * 5)
            assert screen.speed == 0
            await pilot.press(*["plus"] * 10)
            assert screen.speed == len(speeds) - 1
            await pilot.press("minus", "equals_sign")
            assert screen.speed == len(speeds) - 1
            fps = generator_module.FPS
            assert f"({speeds[-1] * fps}/s)" in text_of(pilot, "#progress")
        drive(valid_config, scenario)

    def test_panels(self, drive: Drive, valid_config: str) -> None:
        """The side panels show the algorithm, the progress and the legend."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Pause, then check each side panel."""
            screen = await self.open(pilot)
            await pilot.press("space")
            assert text_of(pilot, "#algorithms").split("\n") == [
                "▸ wilson's (loop-erased walk)",
                "  backtracker (depth-first search)"]
            progress = text_of(pilot, "#progress")
            assert "phase" in progress and "carving" in progress
            assert f"/ {screen.replay.playable}" in progress
            legend = text_of(pilot, "#legend")
            for label in ("walk head", "random walk", "not reached yet"):
                assert label in legend
        drive(valid_config, scenario)

    def test_one_algorithm_cannot_be_switched(
            self, drive: Drive, valid_config: str,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """With a single algorithm, A is not offered."""
        monkeypatch.setattr(session_module, "ALGORITHMS", ONE_ALGORITHM)
        monkeypatch.setattr(generator_module, "ALGORITHMS", ONE_ALGORITHM)

        async def scenario(pilot: Pilot[None]) -> None:
            """Check the algorithm key is not offered."""
            await self.open(pilot)
            assert not offered(pilot, "algorithm")
        drive(valid_config, scenario)

    def test_switch_algorithm(self, drive: Drive, valid_config: str,
                              monkeypatch: pytest.MonkeyPatch) -> None:
        """A rebuilds the maze with the next algorithm and replays it."""
        monkeypatch.setattr(session_module, "ALGORITHMS", TWO_ALGORITHMS)
        monkeypatch.setattr(generator_module, "ALGORITHMS", TWO_ALGORITHMS)

        async def scenario(pilot: Pilot[None]) -> None:
            """Skip, switch, and check the new maze is being replayed."""
            screen = await self.open(pilot)
            assert offered(pilot, "algorithm")
            await pilot.press("s", "a")
            assert screen.session.algorithm == 1
            assert not screen.replay.done  # replaying the new maze
            assert text_of(pilot, "#algorithms").split("\n") == [
                "  first (walk)", "▸ second (walk)"]
        drive(valid_config, scenario)

    def test_switch_algorithm_problem(
            self, drive: Drive, valid_config: str,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """A problem while switching algorithm shows the error screen."""
        monkeypatch.setattr(generator_module, "ALGORITHMS", TWO_ALGORITHMS)

        def fail(self: Session, index: int) -> MazeRun:
            """Stand-in for Session.set_algorithm: always fails."""
            raise ConfigProblem("Impossible maze", "no room",
                                self.config_path)
        monkeypatch.setattr(Session, "set_algorithm", fail)

        async def scenario(pilot: Pilot[None]) -> None:
            """Press A and check the error screen shows."""
            await self.open(pilot)
            await pilot.press("a")
            await pilot.pause()
            assert isinstance(pilot.app.screen, ErrorScreen)
        drive(valid_config, scenario)

    def test_keeps_the_colours(self, drive: Drive, valid_config: str) -> None:
        """The replay uses the colours chosen on the main screen."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Change both colours, open the replay, and check them."""
            await pilot.press("c", "f", "f")
            screen = await self.open(pilot)
            renderer = screen.query_one(AMazeIngRenderer)
            assert renderer.wall_colour == WALL_COLOURS[1].hex
            assert renderer.logo_colour == LOGO_COLOURS[2].hex
        drive(valid_config, scenario)


class TestLayout:
    """How the screens arrange the maze and the panels in the terminal."""

    def test_side_by_side_at_full_size(self, drive: Drive,
                                       valid_config: str) -> None:
        """With room to spare, the panels sit beside a full-size maze."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Check the layout and tile size, and that zoom is not offered."""
            body = pilot.app.screen.query_one(MazeBody)
            assert (body.cols, body.rows) == (10, 8)
            assert not body.has_class("-stacked")
            renderer = pilot.app.screen.query_one(AMazeIngRenderer)
            assert renderer.fits and not renderer.compact
            assert not pilot.app.screen.query_one("#too-narrow").display
            assert pilot.app.screen.query_one("#maze-panel").display
            assert not offered(pilot, "expand")
            assert not offered(pilot, "shrink")
        drive(valid_config, scenario)

    def test_compact_when_full_size_does_not_fit(
            self, drive: Drive, write_config: WriteConfig) -> None:
        """Without room for full size, the maze is compact and Z expands it."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Expand and shrink with Z, checking the keys each time."""
            screen = main_screen(pilot)
            renderer = screen.query_one(AMazeIngRenderer)
            assert not screen.query_one(MazeBody).has_class("-stacked")
            assert renderer.compact and not renderer.fits
            assert offered(pilot, "expand")
            assert not offered(pilot, "shrink")
            await pilot.press("z")
            assert screen.session.expanded
            assert renderer.expanded and not renderer.compact
            assert offered(pilot, "shrink")
            assert not offered(pilot, "expand")
            await pilot.press("z")
            assert not screen.session.expanded
            assert renderer.compact
        drive(sized(write_config, 40, 20), scenario, size=(140, 40))

    def test_zoom_on_the_replay_screen(self, drive: Drive,
                                       write_config: WriteConfig) -> None:
        """Z works on the replay screen too, and the choice carries over."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Zoom on the replay screen, then check the main screen."""
            await pilot.press("g")
            await pilot.pause()
            screen = generator_screen(pilot)
            renderer = screen.query_one(AMazeIngRenderer)
            await pilot.press("z")
            assert screen.session.expanded and renderer.expanded
            await pilot.press("z")
            assert not screen.session.expanded and not renderer.expanded
            # the choice is shared with the main screen
            await pilot.press("z", "escape")
            await pilot.pause()
            main = main_screen(pilot)
            assert main.query_one(AMazeIngRenderer).expanded
        drive(sized(write_config, 40, 20), scenario, size=(140, 40))

    def test_panels_go_below_when_narrow(
            self, drive: Drive, write_config: WriteConfig) -> None:
        """If the maze does not fit beside the panels, they go below it."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Check the body is stacked and the maze still shown."""
            assert pilot.app.screen.query_one(MazeBody).has_class(
                "-stacked")
            assert pilot.app.screen.query_one("#maze-panel").display
        drive(sized(write_config, 40, 20), scenario, size=(100, 40))

    def test_too_narrow(self, drive: Drive,
                        write_config: WriteConfig) -> None:
        """A terminal far too narrow shows a notice instead of the maze."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Check the notice replaces the maze and zoom is not offered."""
            screen = pilot.app.screen
            assert screen.query_one("#too-narrow").display
            assert not screen.query_one("#maze-panel").display
            notice = text_of(pilot, "#too-narrow-text")
            assert notice.startswith("Terminal too narrow")
            assert "The maze needs at least" in notice
            assert not offered(pilot, "expand")
            assert not offered(pilot, "shrink")
        drive(sized(write_config, 40, 20), scenario, size=(50, 30))

    def test_follows_terminal_resizes(self, drive: Drive,
                                      write_config: WriteConfig) -> None:
        """The layout is redone when the terminal is resized."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Widen the terminal and check the maze comes back beside the
            panels."""
            screen = pilot.app.screen
            assert screen.query_one("#too-narrow").display
            await pilot.resize_terminal(160, 40)
            await pilot.pause()
            assert not screen.query_one("#too-narrow").display
            assert not screen.query_one(MazeBody).has_class("-stacked")
        drive(sized(write_config, 40, 20), scenario, size=(50, 30))


class TestMlxWindow:
    """The MLX window the user can open while the terminal is too narrow.
    The tests use a FakeMazeWindow (see tests/ui/conftest.py)."""

    @staticmethod
    def renderer(pilot: Pilot[None]) -> AMazeIngRenderer:
        """The current screen's renderer."""
        return pilot.app.screen.query_one(AMazeIngRenderer)

    @staticmethod
    def button(pilot: Pilot[None]) -> Button:
        """The notice's button that opens the window."""
        return pilot.app.screen.query_one("#open-window", Button)

    def test_never_opens_on_its_own(self, drive: Drive,
                                    write_config: WriteConfig) -> None:
        """A terminal too narrow for the maze only offers the window: a
        button, and W."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Check nothing opened, and the button and key are offered."""
            window = fake_window(pilot.app)
            assert window.state is WindowState.HIDDEN
            assert window.frames == []
            assert self.button(pilot).display
            assert str(self.button(pilot).label) == "Open in a window (W)"
            assert pilot.app.check_action("open_window", ())
        drive(sized(write_config, 40, 20), scenario, size=(50, 30))

    def test_not_offered_when_the_maze_fits(self, drive: Drive,
                                            valid_config: str) -> None:
        """With room for the maze, there is nothing to open."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Check W is not offered and the notice is hidden."""
            assert not pilot.app.check_action("open_window", ())
            assert not pilot.app.screen.query_one("#too-narrow").display
        drive(valid_config, scenario)

    @pytest.mark.parametrize("how", ["click", "key"])
    def test_the_user_opens_it(self, drive: Drive, write_config: WriteConfig,
                               how: str) -> None:
        """Clicking the button, or pressing W, opens the window on the
        drawing; the notice says so and the button goes."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Open the window and check the frame and the notice."""
            if how == "click":
                await pilot.click("#open-window")
            else:
                await pilot.press("w")
            window = fake_window(pilot.app)
            assert window.state is WindowState.OPEN
            assert window.frames[-1] == self.renderer(pilot).frame()
            assert "It is shown in a separate window." in \
                text_of(pilot, "#too-narrow-text")
            assert not self.button(pilot).display
            assert not pilot.app.check_action("open_window", ())
        drive(sized(write_config, 40, 20), scenario, size=(50, 30))

    def test_follows_the_drawing(self, drive: Drive,
                                 write_config: WriteConfig) -> None:
        """Once open, changing the wall colour or hiding the path updates
        the window."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Open, press C and P, checking the latest frame each time."""
            await pilot.press("w")
            window = fake_window(pilot.app)
            await pilot.press("c")
            assert window.frames[-1] == self.renderer(pilot).frame()
            wall = list(Tile).index(Tile.WALL)
            assert window.frames[-1].colours[wall] == \
                int(WALL_COLOURS[1].hex[1:], 16)
            await pilot.press("p")
            assert list(Tile).index(Tile.PATH) not in window.frames[-1].tiles
        drive(sized(write_config, 40, 20), scenario, size=(50, 30))

    def test_replay_ticks_reach_the_window(
            self, drive: Drive, write_config: WriteConfig) -> None:
        """A tick run by the replay screen itself, as its timer does,
        updates the window. Its messages have the screen as sender, which
        they cannot bubble past, so they must go to the app directly."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Open the window and the replay, tick from the screen, and
            check the frame."""
            await pilot.press("w", "g")
            await pilot.pause()
            screen = generator_screen(pilot)
            window = fake_window(pilot.app)
            before = window.frames[-1]
            screen.call_later(screen._tick)
            await pilot.pause()
            assert window.frames[-1] == self.renderer(pilot).frame()
            assert window.frames[-1] != before
        drive(sized(write_config, 40, 20), scenario, size=(50, 30))

    def test_closed_by_the_user(self, drive: Drive,
                                write_config: WriteConfig) -> None:
        """When the user closes the window, the button comes back, and
        nothing reopens it but the user."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Open, close as the user would, and change the drawing."""
            await pilot.press("w")
            window = fake_window(pilot.app)
            window.close_on_next_pump = True
            app = pilot.app
            assert isinstance(app, app_module.AMazeIngApp)
            app._pump_window()
            assert window.state is WindowState.HIDDEN
            assert self.button(pilot).display
            assert app.check_action("open_window", ())
            await pilot.press("c")
            assert state_of(window) is WindowState.HIDDEN
        drive(sized(write_config, 40, 20), scenario, size=(50, 30))

    def test_failure_is_explained(self, drive: Drive,
                                  write_config: WriteConfig) -> None:
        """A window that could not open says why, and offers to try
        again."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Fail the window and check the notice and the button."""
            window = fake_window(pilot.app)
            window.state = WindowState.FAILED
            window.error = "cannot connect to the display"
            app = pilot.app
            assert isinstance(app, app_module.AMazeIngApp)
            app.sync_window()
            assert ("Could not open a window: cannot connect to the "
                    "display.") in \
                text_of(pilot, "#too-narrow-text").replace("\n", " ")
            assert str(self.button(pilot).label) == "Try again (W)"
            assert app.check_action("open_window", ())
            await pilot.press("w")
            assert state_of(window) is WindowState.OPEN
        drive(sized(write_config, 40, 20), scenario, size=(50, 30))

    def test_closed_once_the_terminal_is_wide_enough(
            self, drive: Drive, write_config: WriteConfig) -> None:
        """Widening the terminal so the maze fits closes the window, and
        narrowing it again does not reopen it."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Open, widen, then narrow again."""
            await pilot.press("w")
            window = fake_window(pilot.app)
            await pilot.resize_terminal(160, 40)
            await pilot.pause()
            assert window.state is WindowState.HIDDEN
            assert not pilot.app.check_action("open_window", ())
            await pilot.resize_terminal(50, 30)
            await pilot.pause()
            assert state_of(window) is WindowState.HIDDEN
            assert pilot.app.check_action("open_window", ())
        drive(sized(write_config, 40, 20), scenario, size=(50, 30))

    def test_closed_on_the_error_screen(self, drive: Drive,
                                        write_config: WriteConfig) -> None:
        """With no maze left to show, the window closes."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Open, show a problem, then check the window is hidden."""
            await pilot.press("w")
            window = fake_window(pilot.app)
            problem = ConfigProblem("Broken", "it broke", "config.txt")
            pilot.app.screen.post_message(ProblemFound(problem))
            await pilot.pause()
            assert isinstance(pilot.app.screen, ErrorScreen)
            assert window.state is WindowState.HIDDEN
        drive(sized(write_config, 40, 20), scenario, size=(50, 30))


ALGORITHM_NAMES = ["wilson's (loop-erased walk)",
                   "backtracker (depth-first search)"]


async def click_algorithm(pilot: Pilot[None], line: int) -> None:
    """Click *line* of the algorithm list, counting from its top border
    (line 0); the first algorithm is on line 1."""
    # x=3: past the border and the padding, on the name
    assert await pilot.click("#algorithms", offset=(3, line))
    await pilot.pause()


def marked(pilot: Pilot[None]) -> list[str]:
    """The algorithm list's lines, the selected one starting with ▸."""
    return text_of(pilot, "#algorithms").split("\n")


class TestAlgorithmPicker:
    """Choosing the algorithm, by clicking the list or with A, on the main
    and the replay screen."""

    def test_main_screen_lists_the_algorithms(self, drive: Drive,
                                              valid_config: str) -> None:
        """The main screen lists every algorithm, the one in use marked."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Check the list."""
            main_screen(pilot)
            assert marked(pilot) == [f"▸ {ALGORITHM_NAMES[0]}",
                                     f"  {ALGORITHM_NAMES[1]}"]
        drive(valid_config, scenario)

    def test_a_cycles_on_the_main_screen(self, drive: Drive,
                                         valid_config: str) -> None:
        """A rebuilds the maze from the same seed with the next algorithm,
        and back to the first after the last."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Press A twice, checking the maze, list and stats."""
            screen = main_screen(pilot)
            wilsons = screen.session.current
            assert offered(pilot, "algorithm")
            await pilot.press("a")
            assert screen.session.algorithm == 1
            assert screen.session.seed == "42"
            assert screen.session.current.maze.grid != wilsons.maze.grid
            assert marked(pilot)[1] == f"▸ {ALGORITHM_NAMES[1]}"
            assert "backtracker" in text_of(pilot, "#stats")
            renderer = screen.query_one(AMazeIngRenderer)
            assert renderer.maze is screen.session.current.maze
            await pilot.press("a")
            assert screen.session.algorithm == 0
            assert marked(pilot)[0] == f"▸ {ALGORITHM_NAMES[0]}"
        drive(valid_config, scenario)

    def test_click_switches_on_the_main_screen(self, drive: Drive,
                                               valid_config: str) -> None:
        """Clicking an algorithm rebuilds the maze with it."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Click the backtracker, then Wilson's again."""
            screen = main_screen(pilot)
            await click_algorithm(pilot, 2)
            assert screen.session.algorithm == 1
            assert marked(pilot)[1] == f"▸ {ALGORITHM_NAMES[1]}"
            assert "backtracker" in text_of(pilot, "#stats")
            await click_algorithm(pilot, 1)
            assert screen.session.algorithm == 0
            assert "wilson's" in text_of(pilot, "#stats")
        drive(valid_config, scenario)

    @pytest.mark.parametrize("line", [0, 1])
    def test_clicks_that_change_nothing(self, drive: Drive,
                                        valid_config: str, line: int) -> None:
        """Clicking the border, or the algorithm already in use, keeps the
        maze as it is."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Click and check the maze was not rebuilt."""
            screen = main_screen(pilot)
            run = screen.session.current
            await click_algorithm(pilot, line)
            assert screen.session.current is run
            assert screen.session.algorithm == 0
        drive(valid_config, scenario)

    def test_one_algorithm_is_not_offered(
            self, drive: Drive, valid_config: str,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """With a single algorithm, the main screen does not offer A."""
        monkeypatch.setattr(session_module, "ALGORITHMS", ONE_ALGORITHM)
        monkeypatch.setattr(main_module, "ALGORITHMS", ONE_ALGORITHM)

        async def scenario(pilot: Pilot[None]) -> None:
            """Check A is not offered, and the list has one line."""
            main_screen(pilot)
            assert not offered(pilot, "algorithm")
            assert marked(pilot) == ["▸ only (walk)"]
        drive(valid_config, scenario)

    def test_problem_on_the_main_screen(
            self, drive: Drive, valid_config: str,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """A problem while switching algorithm shows the error screen."""
        def fail(self: Session, index: int) -> MazeRun:
            """Stand-in for Session.set_algorithm: always fails."""
            raise ConfigProblem("Impossible maze", "no room",
                                self.config_path)
        monkeypatch.setattr(Session, "set_algorithm", fail)

        async def scenario(pilot: Pilot[None]) -> None:
            """Press A and check the error screen shows."""
            await pilot.press("a")
            await pilot.pause()
            assert isinstance(pilot.app.screen, ErrorScreen)
        drive(valid_config, scenario)

    def test_click_switches_on_the_replay_screen(self, drive: Drive,
                                                 valid_config: str) -> None:
        """On the replay screen, clicking an algorithm rebuilds the maze
        with it and replays the new one."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Skip the replay, click the backtracker, check it replays."""
            await pilot.press("g")
            await pilot.pause()
            screen = generator_screen(pilot)
            await pilot.press("s")
            assert screen.replay.done
            await click_algorithm(pilot, 2)
            assert screen.session.algorithm == 1
            assert not screen.replay.done
            assert screen.replay.run is screen.session.current
            assert marked(pilot)[1] == f"▸ {ALGORITHM_NAMES[1]}"
        drive(valid_config, scenario)

    def test_choice_carries_across_screens(self, drive: Drive,
                                           valid_config: str) -> None:
        """An algorithm picked on one screen is the one marked, and used, on
        the other."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Pick on the main screen, check the replay screen, pick there,
            and check the main screen again."""
            await pilot.press("a", "g")
            await pilot.pause()
            assert marked(pilot)[1] == f"▸ {ALGORITHM_NAMES[1]}"
            await click_algorithm(pilot, 1)
            await pilot.press("escape")
            await pilot.pause()
            main_screen(pilot)
            assert marked(pilot)[0] == f"▸ {ALGORITHM_NAMES[0]}"
            assert "wilson's" in text_of(pilot, "#stats")
        drive(valid_config, scenario)
