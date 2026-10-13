"""The Textual app, its error screen, title bar and `python -m lib.ui`."""
import runpy
import sys
from pathlib import Path

import pytest
from textual.app import App
from textual.pilot import Pilot
from textual.widgets import Label, Static

from lib.ui import AMazeIngApp
from lib.ui.screens import (TONES, ErrorScreen, MainScreen, ProblemFound,
                            TitleBar)
from lib.ui.session import ConfigProblem
from tests.helpers import VALID_CONFIG, WriteConfig
from tests.ui.helpers import Drive, fake_window, plain

pytestmark = pytest.mark.ui


class TestApp:
    """The app itself: which screen it shows, and what it prints."""

    def test_shows_the_maze(self, drive: Drive, valid_config: str) -> None:
        """A valid config opens on the main screen."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Check the main screen is the only one above the default."""
            assert isinstance(pilot.app.screen, MainScreen)
            assert len(pilot.app.screen_stack) == 2
        app = drive(valid_config, scenario)
        assert app.title == "A-Maze-ing"

    def test_shows_what_is_wrong(self, drive: Drive,
                                 write_config: WriteConfig) -> None:
        """A broken config opens on the error screen."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Check the error screen explains the missing keys."""
            screen = pilot.app.screen
            assert isinstance(screen, ErrorScreen)
            assert screen.problem.title == "Missing keys"
        drive(write_config("WIDTH=3\n"), scenario)

    def test_quits_on_q(self, drive: Drive, valid_config: str) -> None:
        """Q quits the app."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Press Q and check the app stopped."""
            await pilot.press("q")
            await pilot.pause()
            assert not pilot.app.is_running
        drive(valid_config, scenario)

    def test_reload_after_fixing_the_config(
            self, drive: Drive, write_config: WriteConfig) -> None:
        """Fixing the config and pressing R shows the maze."""
        path = write_config(VALID_CONFIG.replace("WIDTH=10", "WIDTH=x"))

        async def scenario(pilot: Pilot[None]) -> None:
            """Fix the file, reload, and check the main screen replaced the
            error."""
            assert isinstance(pilot.app.screen, ErrorScreen)
            Path(path).write_text(VALID_CONFIG)
            await pilot.press("r")
            await pilot.pause()
            assert isinstance(pilot.app.screen, MainScreen)
            assert len(pilot.app.screen_stack) == 2
        drive(path, scenario)

    def test_reload_a_config_that_is_still_wrong(
            self, drive: Drive, write_config: WriteConfig) -> None:
        """Reloading a config that is still broken shows the new problem."""
        path = write_config("WIDTH=3\n")

        async def scenario(pilot: Pilot[None]) -> None:
            """Break the file differently, reload, and check only the new error
            shows."""
            Path(path).write_text("HEIGHT=3\n")
            await pilot.press("r")
            await pilot.pause()
            screen = pilot.app.screen
            assert isinstance(screen, ErrorScreen)
            assert "WIDTH" in screen.problem.detail
            assert len(pilot.app.screen_stack) == 2
        drive(path, scenario)

    def test_problem_found_shows_the_error_screen(
            self, drive: Drive, valid_config: str) -> None:
        """A ProblemFound from any screen switches to the error screen."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Post a problem and check the error screen shows that one."""
            problem = ConfigProblem("Broken", "it broke", valid_config)
            pilot.app.screen.post_message(ProblemFound(problem))
            await pilot.pause()
            screen = pilot.app.screen
            assert isinstance(screen, ErrorScreen)
            assert screen.problem is problem
        drive(valid_config, scenario)

    def test_keeps_what_the_library_prints(
            self, drive: Drive, write_config: WriteConfig) -> None:
        """What the library prints while the UI runs is kept for later."""
        small = (VALID_CONFIG.replace("WIDTH=10", "WIDTH=4")
                 .replace("HEIGHT=8", "HEIGHT=3")
                 .replace("EXIT=9,7", "EXIT=3,2"))

        async def scenario(pilot: Pilot[None]) -> None:
            """Nothing to do: building the small maze is what prints."""
            pass
        app = drive(write_config(small), scenario)
        assert any("too small for the 42 logo" in text and stderr
                   for text, stderr in app._printed)

    def test_run_prints_each_message_once(
            self, monkeypatch: pytest.MonkeyPatch,
            capsys: pytest.CaptureFixture[str]) -> None:
        """After the UI exits, each kept line is printed once, to the stream it
        was meant for."""
        monkeypatch.setattr(App, "run", lambda self, *a, **k: None)
        app = AMazeIngApp("config.txt")
        app._printed = [("warn\n", True), ("note\n", False),
                        ("warn\n", True), ("one\ntwo\n", False)]
        app.run()
        captured = capsys.readouterr()
        assert captured.out == "note\none\ntwo\n"
        assert captured.err == "warn\n"

    def test_run_closes_the_mlx_window(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        """After the UI exits, the MLX window and its display are closed,
        even if the app failed."""
        def crash(self: App[None], *args: object, **kwargs: object) -> None:
            """Stand-in for App.run: fails."""
            raise RuntimeError("boom")
        monkeypatch.setattr(App, "run", crash)
        app = AMazeIngApp("config.txt")
        with pytest.raises(RuntimeError):
            app.run()
        assert fake_window(app).closed


class TestErrorScreen:
    """The screen that explains what is wrong with the config."""

    def test_points_at_the_line(self, drive: Drive,
                                write_config: WriteConfig) -> None:
        """A problem on a line shows that line, a caret under the wrong part,
        and a red ERROR badge."""
        path = write_config(VALID_CONFIG.replace("ENTRY=0,0", "ENTRY=0,99"))

        async def scenario(pilot: Pilot[None]) -> None:
            """Check the title, location, excerpt and badge."""
            screen = pilot.app.screen
            assert plain(screen.query_one("#error-title", Static)) == \
                "✗ Out of bounds"
            assert plain(screen.query_one("#error-where", Static)) == \
                "config.txt:L4"
            excerpt = plain(screen.query_one("#excerpt", Static))
            assert "› 4 │ ENTRY=0,99" in excerpt
            assert "^^ y must be between 0 and 7" in excerpt
            assert not screen.query("#error-detail")
            badge = screen.query_one("#badge", Label)
            assert plain(badge) == "ERROR"
            assert badge.has_class("-red")
        drive(path, scenario)

    def test_explains_when_there_is_no_line(self, drive: Drive,
                                            tmp_path: Path) -> None:
        """A problem not tied to a line is explained in words instead."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Check the detail and reload hint are shown, not an excerpt."""
            screen = pilot.app.screen
            assert plain(screen.query_one("#error-where", Static)) == \
                "missing.txt"
            assert "There is no file at" in plain(
                screen.query_one("#error-detail", Static))
            assert not screen.query("#excerpt")
            assert "Press R" in plain(screen.query_one("#error-hint",
                                                       Static))
        drive(str(tmp_path / "missing.txt"), scenario)

    def test_excerpt(self) -> None:
        """The excerpt shows two lines either side, the caret, and pads the
        offending line to the widest row."""
        lines = [f"LINE{n}" for n in range(10)]
        lines[5] = "KEY=bad"
        screen = ErrorScreen(ConfigProblem("T", "why", "p", key="KEY"))
        excerpt = screen._excerpt(lines, 5, 4, 7).plain.split("\n")
        assert [line.rstrip() for line in excerpt] == [
            "  4 │ LINE3",
            "  5 │ LINE4",
            "› 6 │ KEY=bad",
            "    │     ^^^ why",
            "  7 │ LINE6",
            "  8 │ LINE7",
        ]
        # the offending line is padded to the widest row, the caret's
        assert len(excerpt[2]) == len(excerpt[3]) == 17

    def test_excerpt_at_the_top_of_the_file(self) -> None:
        """The excerpt does not reach before the first line."""
        screen = ErrorScreen(ConfigProblem("T", "d", "p", line=0))
        excerpt = screen._excerpt(["A", "B"], 0, 0, 1).plain.split("\n")
        assert excerpt[0].startswith("› 1 │ A")
        assert excerpt[1] == "    │ ^ d"
        assert excerpt[2] == "  2 │ B"
        assert len(excerpt) == 3

    def test_reload_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """R asks the app to reload, with a Reload message."""
        screen = ErrorScreen(ConfigProblem("T", "d", "p"))
        posted: list[object] = []
        monkeypatch.setattr(screen, "post_message", posted.append)
        screen.action_reload()
        assert len(posted) == 1
        assert isinstance(posted[0], ErrorScreen.Reload)


class TestTitleBar:
    """The bar across the top of every screen."""

    def test_labels(self, drive: Drive, valid_config: str) -> None:
        """The bar shows the app, the config file, the size, the seed and the
        mode."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Check every label of the main screen's bar."""
            bar = pilot.app.screen.query_one(TitleBar)
            assert bar.config_path == valid_config
            assert plain(bar.query_one("#brand", Label)) == "A-MAZE-ING"
            assert plain(bar.query_one("#source", Label)) == "config.txt"
            assert plain(bar.query_one("#dims", Label)) == "10×8"
            assert plain(bar.query_one("#seed", Label)) == "seed 42"
            assert plain(bar.query_one("#badge", Label)) == "PERFECT"
        drive(valid_config, scenario)

    @pytest.mark.parametrize("tone", TONES)
    def test_tones(self, drive: Drive, valid_config: str,
                   tone: str) -> None:
        """The badge takes exactly the tone it is given."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Show a badge in *tone* and check its classes, and that dims and
            seed are cleared."""
            bar = pilot.app.screen.query_one(TitleBar)
            bar.show("BADGE", tone=tone)
            badge = bar.query_one("#badge", Label)
            assert [name for name in TONES
                    if badge.has_class(f"-{name}")] == [tone]
            # no dims or seed given: they are cleared
            assert plain(bar.query_one("#dims", Label)) == ""
            assert plain(bar.query_one("#seed", Label)) == ""
        drive(valid_config, scenario)


class TestMainModule:
    """Running the UI with python3 -m lib.ui."""

    def run(self, monkeypatch: pytest.MonkeyPatch, *args: str) -> None:
        """Run lib.ui as the main module with *args* on the command line."""
        monkeypatch.setattr(sys, "argv", ["lib.ui", *args])
        runpy.run_module("lib.ui", run_name="__main__", alter_sys=True)

    @pytest.mark.parametrize("args", [(), ("a.txt", "b.txt")])
    def test_usage(self, monkeypatch: pytest.MonkeyPatch,
                   capsys: pytest.CaptureFixture[str],
                   args: tuple[str, ...]) -> None:
        """Anything but one argument prints the usage and exits with 1."""
        with pytest.raises(SystemExit) as info:
            self.run(monkeypatch, *args)
        assert info.value.code == 1
        assert "usage: python3 -m lib.ui <config file>" in \
            capsys.readouterr().err

    def test_runs_the_app(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With a config, the app is created for it and run."""
        ran: list[str] = []
        monkeypatch.setattr(AMazeIngApp, "run",
                            lambda self: ran.append(self.config_path))
        self.run(monkeypatch, "config.txt")
        assert ran == ["config.txt"]
