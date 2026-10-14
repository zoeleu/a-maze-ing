# A-Maze-Ing - A 42 School project to generate mazes.
# Copyright (C) 2026 Zoe T. Leullier
# Copyright (C) 2026 Flora P. C. Carvalho
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""The Textual application: picks the screen to show, builds the mazes on a
thread of their own, keeps the console output the library prints while the
UI owns the terminal, and mirrors the maze in an MLX window when the
terminal is too narrow or too short for it."""
import sys
import threading
from pathlib import Path
from typing import Any, Awaitable, Callable, TypeVar

from textual import events, on
from textual.app import App
from textual.binding import Binding
from textual.screen import Screen
from textual.widget import AwaitMount

from .memory import OUT_OF_MEMORY, too_big, warning
from .mlx_window import MazeWindow, WindowState
from .renderer import AMazeIngRenderer
from .screens.building import (BuildingScreen, from_thread,
                               progress_reporter)
from .screens.error import ErrorScreen, ProblemFound
from .screens.layout import MazeBody
from .screens.main import MainScreen
from .screens.memory_warning import MemoryWarning
from .session import ConfigProblem, Session, load_config

# How often the MLX window's events are handled, per second
WINDOW_FPS = 30

# What a build returns: a Session, or a MazeRun
Result = TypeVar("Result")


class AMazeIngApp(App[None]):
    """Shows the maze built from a config file, or what is wrong with it."""

    CSS_PATH = "a_maze_ing.tcss"
    TITLE = "A-Maze-ing"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [
        Binding("w", "open_window", "Open window", key_display="W"),
        Binding("q", "quit", "Quit", key_display="Q"),
    ]

    def __init__(self, config_path: str) -> None:
        """Create the app for the config at *config_path*."""
        super().__init__()
        self.config_path = config_path
        self._printed: list[tuple[str, bool]] = []
        self.maze_window = MazeWindow(
            f"A-Maze-ing - {Path(config_path).name}")
        self._window_seen: tuple[bool, WindowState] | None = None

    def on_mount(self) -> None:
        """Hold back what the library prints, load the config, and start
        handling the MLX window's events."""
        self.begin_capture_print(self)
        self.set_interval(1 / WINDOW_FPS, self._pump_window)
        self.load()

    def _pump_window(self) -> None:
        """Handle the MLX window's events; if the user closed it, offer
        the button again."""
        if self.maze_window.pump():
            self.sync_window()

    def load(self) -> None:
        """Read the config and build a maze, showing how far it has got,
        then show it, or explain why that failed. If the maze may not fit
        in memory, ask first."""
        try:
            config = load_config(self.config_path)
        except ConfigProblem as problem:
            self._show(ErrorScreen(problem))
            return
        # 2 mazes: the interface keeps the old one while it builds a new one
        size = (config.width, config.height)
        if not too_big(*size, mazes=2):
            self._load_session()
            return

        def answered(accepted: bool | None) -> None:
            """Build the maze if the user accepted the risk, quit if not."""
            if accepted:
                self._load_session()
            else:
                self.exit()
        # only a warning: the cap set by limit_memory() keeps the computer
        # safe either way, so the user may still try
        self._show(MemoryWarning(warning(*size, mazes=2)), answered)

    def _load_session(self) -> None:
        """Build the session's first maze behind the BuildingScreen, then
        show it, or explain why that failed."""
        def load_session() -> Session:
            """Read the config and build its first maze, reporting how far
            it has got to the BuildingScreen."""
            return Session(self.config_path,
                           progress=progress_reporter(self))

        def show_maze(session: Session) -> AwaitMount:
            """Show the main screen for the new session."""
            return self._show(MainScreen(session))

        self.build(build_maze=load_session, when_built=show_maze)

    def build(self, build_maze: Callable[[], Result],
              when_built: Callable[[Result], Awaitable[Any] | None]
              ) -> None:
        """Run *build_maze* on a thread of its own behind the BuildingScreen.
        Then, back on the interface's thread, call *when_built* with what
        *build_maze* returned, or show the problem if it failed.

        A big maze takes minutes to build: on the interface's thread, it
        would freeze the interface until done. Python's GIL lets only one
        thread run Python code at a time, so this does not build any faster,
        but Python switches threads every few milliseconds, which keeps the
        interface drawing.

        The thread is a daemon: it is stopped with the program, so quitting
        never waits for a build to finish.
        """
        self.push_screen(BuildingScreen())
        # A thread is a second line of work running inside the same program,
        # alongside the first. Normally a program does one thing at a time:
        # while it builds a maze, it cannot redraw the screen or read keys,
        # so the interface would freeze for minutes. Here, the interface's
        # thread keeps drawing and reading keys, while this new thread runs
        # _run_build(), which builds the maze. start() launches it and
        # returns at once, without waiting for the maze.
        # daemon=True: when the program ends, Python stops this thread
        # instead of waiting for it, so Q quits even mid-build.
        threading.Thread(target=self._run_build,
                         args=(build_maze, when_built),
                         name="maze-build", daemon=True).start()

    def _run_build(self, build_maze: Callable[[], Result],
                   when_built: Callable[[Result], Awaitable[Any] | None]
                   ) -> None:
        """The build thread itself: it runs this function, and ends when the
        function returns. Builds the maze, then hands the result over to the
        interface's thread. Any error is shown rather than raised: raised
        here, it would leave the BuildingScreen up for good."""
        # This thread must not change the screens itself: Textual is not
        # thread-safe, so two threads changing the same screen at once could
        # leave it half-updated or crash. from_thread() asks the interface's
        # thread to run the function instead (see there).
        problem: ConfigProblem | None = None
        try:
            result = build_maze()
        except ConfigProblem as error:
            # without its traceback, which keeps the build's data alive
            problem = error.with_traceback(None)
        except MemoryError:
            # past the cap set by limit_memory(): the build stops here
            # instead of freezing the computer
            problem = ConfigProblem("Out of memory", OUT_OF_MEMORY,
                                    self.config_path)
        except Exception as error:
            problem = ConfigProblem(
                "Build failed", f"{type(error).__name__}: {error}",
                self.config_path)
        # The problem is shown only now, out of the except blocks: while one
        # runs, the error keeps the half-built maze in memory. After a
        # MemoryError, the interface needs that memory back to draw the
        # error screen.
        if problem is not None:
            from_thread(self, self._show_problem, problem)
            return
        # the maze is built, but only the interface's thread can show it
        from_thread(self, self._built, when_built, result)

    async def _built(self,
                     when_built: Callable[[Result], Awaitable[Any] | None],
                     result: Result) -> None:
        """On the interface's thread: remove the BuildingScreen and hand
        *result* to *when_built*, waiting for the screen it shows, if any.
        The build thread waits for this, so it only ends once the new maze
        is on screen."""
        # The screens form a stack, like a pile of cards: the one on top is
        # shown. pop_screen() takes the BuildingScreen off the top, which
        # shows the screen below it again.
        # This function is async so it can wait (await) for that, and for
        # the screen when_built shows, to be done: Textual changes screens
        # in steps, between its other tasks, not all at once.
        await self.pop_screen()
        shown = when_built(result)
        if shown is not None:
            await shown

    def _show_problem(self, problem: ConfigProblem) -> AwaitMount:
        """On the interface's thread: show what stopped the build."""
        return self._show(ErrorScreen(problem))

    def _show(self, screen: Screen[Any],
              answered: Callable[[Any], None] | None = None) -> AwaitMount:
        """Make *screen* the only one above the default screen; *answered*
        is called with its result, for a dialog. Returns what to await for
        it to be on screen."""
        while len(self.screen_stack) > 1:
            self.pop_screen()
        return self.push_screen(screen, answered)

    def on_print(self, event: events.Print) -> None:
        """Keep printed text, to pass on to the console on exit."""
        self._printed.append((event.text, event.stderr))

    def on_problem_found(self, message: ProblemFound) -> None:
        """Show what is wrong with the config."""
        self._show(ErrorScreen(message.problem))

    def on_error_screen_reload(self, message: ErrorScreen.Reload) -> None:
        """Read the config again."""
        self.load()

    def _maze_body(self) -> MazeBody | None:
        """The current screen's MazeBody, if it shows a maze."""
        return next(iter(self.screen.query(MazeBody)), None)

    def _window_wanted(self) -> bool:
        """Whether the maze is too big for the terminal, so the MLX
        window may show it."""
        body = self._maze_body()
        return body is not None and body.replaced

    @on(AMazeIngRenderer.Changed)
    @on(MazeBody.Changed)
    def sync_window(self) -> None:
        """Keep the MLX window, if the user opened it, in step with the
        current screen's drawing, close it once the maze fits again, and
        tell the screen how it is doing. Never opens it."""
        wanted = self._window_wanted()
        if not wanted:
            self.maze_window.hide()
        elif self.maze_window.state is WindowState.OPEN:
            frame = self.screen.query_one(AMazeIngRenderer).frame()
            if frame is not None:
                self.maze_window.show(frame)
        body = self._maze_body()
        if body is not None:
            body.set_window_state(self.maze_window.state,
                                  self.maze_window.error)
        # the W key depends on both; only refresh when they change, as this
        # runs for every frame of a replay
        seen = (wanted, self.maze_window.state)
        if seen != self._window_seen:
            self._window_seen = seen
            self.refresh_bindings()

    def check_action(self, action: str,
                     parameters: tuple[object, ...]) -> bool | None:
        """Offer W only when the maze does not fit and its window is not
        open."""
        if action == "open_window":
            return self._window_wanted() and \
                self.maze_window.state is not WindowState.OPEN
        return True

    def action_open_window(self) -> None:
        """Open the MLX window on the current drawing (W, or the notice's
        button)."""
        if not self._window_wanted():
            return
        frame = self.screen.query_one(AMazeIngRenderer).frame()
        if frame is not None:
            self.maze_window.open(frame)
        self.sync_window()

    def run(self, *args: Any, **kwargs: Any) -> None:
        """Run the app, close the MLX window, then print what the library
        printed meanwhile.

        Each message is printed once, even if several mazes printed it.
        """
        try:
            super().run(*args, **kwargs)
        finally:
            self.maze_window.close()
        for stderr, stream in ((False, sys.stdout), (True, sys.stderr)):
            text = "".join(t for t, err in self._printed if err == stderr)
            for line in dict.fromkeys(text.splitlines()):
                print(line, file=stream)
