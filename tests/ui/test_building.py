"""Building a maze on its own thread, behind the BuildingScreen."""
import threading

import pytest
from textual.pilot import Pilot
from textual.widgets import ProgressBar, Static

from ui import AMazeIngApp
from ui.screens import BuildingScreen, ErrorScreen, MainScreen
from ui.screens.building import from_thread, progress_reporter
from ui.session import MazeRun, Session
from tests.ui.helpers import Drive, built, plain

pytestmark = pytest.mark.ui

# How long to wait for the build thread, in steps of 10 ms: 10 seconds
WAIT_STEPS = 1000


def held_build(monkeypatch: pytest.MonkeyPatch) -> threading.Event:
    """Make R's build report "carving 5 / 10", then wait until the returned
    event is set. It returns the current maze rather than building one: the
    thread may outlive the test, and must not write files meanwhile."""
    release = threading.Event()

    def held(self: Session) -> MazeRun:
        """Stand-in for Session.regenerate, on the build thread."""
        assert self.progress is not None
        self.progress("carving", 5, 10)
        release.wait(WAIT_STEPS / 100)
        return self.current
    monkeypatch.setattr(Session, "regenerate", held)
    return release


async def step_text(pilot: Pilot[None], expected: str) -> str:
    """The BuildingScreen's step line, once it reads *expected* or after
    10 seconds: the build thread updates it in its own time."""
    text = ""
    for _ in range(WAIT_STEPS):
        text = plain(pilot.app.screen.query_one("#building-step", Static))
        if text == expected:
            break
        await pilot.pause(0.01)
    return text


class TestBuilding:
    """What the user sees while a maze is built."""

    def test_shows_the_progress(self, drive: Drive, valid_config: str,
                                monkeypatch: pytest.MonkeyPatch) -> None:
        """While R rebuilds the maze, the BuildingScreen shows what the
        build reports, then gives way to the main screen."""
        release = held_build(monkeypatch)

        async def scenario(pilot: Pilot[None]) -> None:
            """Press R, check the progress shown, then let the build end."""
            await pilot.press("r")
            screen = pilot.app.screen
            assert isinstance(screen, BuildingScreen)
            assert await step_text(pilot, "carving 50% (5 / 10)") == \
                "carving 50% (5 / 10)"
            bar = screen.query_one(ProgressBar)
            assert (bar.total, bar.progress) == (10, 5)
            release.set()
            await built(pilot)
            assert isinstance(pilot.app.screen, MainScreen)
        drive(valid_config, scenario)

    def test_a_step_without_a_total(self, drive: Drive,
                                    valid_config: str) -> None:
        """A step that cannot tell how far it has got shows a busy bar."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Show a BuildingScreen and give it a step without a total."""
            screen = BuildingScreen()
            await pilot.app.push_screen(screen)
            screen.show("solving", 0, 0)
            assert plain(screen.query_one("#building-step", Static)) == \
                "solving..."
            assert screen.query_one(ProgressBar).total is None
        drive(valid_config, scenario)

    def test_progress_before_the_screen_is_drawn(
            self, drive: Drive, valid_config: str) -> None:
        """Progress reported before the screen is drawn shows once it is:
        a step like "writing" reports only once."""
        async def scenario(pilot: Pilot[None]) -> None:
            """Report, then show the screen and check the report is on it."""
            screen = BuildingScreen()
            screen.show("writing", 0, 0)
            await pilot.app.push_screen(screen)
            assert plain(screen.query_one("#building-step", Static)) == \
                "writing..."
        drive(valid_config, scenario)

    def test_quitting_does_not_wait(self, drive: Drive, valid_config: str,
                                    monkeypatch: pytest.MonkeyPatch) -> None:
        """Q quits while a maze is still being built."""
        release = held_build(monkeypatch)

        async def scenario(pilot: Pilot[None]) -> None:
            """Press R, then Q before the build is done."""
            await pilot.press("r")
            assert isinstance(pilot.app.screen, BuildingScreen)
            await pilot.press("q")
            await pilot.pause()
            assert not pilot.app.is_running
            release.set()
        drive(valid_config, scenario)

    def test_unexpected_error(self, drive: Drive, valid_config: str,
                              monkeypatch: pytest.MonkeyPatch) -> None:
        """An error the build does not expect, like running out of memory,
        shows the error screen instead of leaving the BuildingScreen up."""
        def fail(self: Session) -> MazeRun:
            """Stand-in for Session.regenerate: runs out of memory."""
            raise MemoryError("no room")
        monkeypatch.setattr(Session, "regenerate", fail)

        async def scenario(pilot: Pilot[None]) -> None:
            """Press R and check the error screen."""
            await pilot.press("r")
            await built(pilot)
            screen = pilot.app.screen
            assert isinstance(screen, ErrorScreen)
            assert screen.problem.title == "Build failed"
            assert screen.problem.detail == "MemoryError: no room"
        drive(valid_config, scenario)


def test_nothing_reaches_a_stopped_app() -> None:
    """Once the app has stopped, as when the user quit mid-build, what the
    build thread sends it is dropped."""
    app = AMazeIngApp("unused.txt")
    called: list[int] = []
    from_thread(app, called.append, 1)
    progress_reporter(app)("carving", 1, 2)
    assert called == []
