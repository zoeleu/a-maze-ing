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

"""The screen that replays, step by step, how the maze was built."""
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import Footer, Static

from ..renderer import (CYAN, GOLD, GROUND, LOGO_COLOURS, UNTOUCHED,
                        WALL_COLOURS, AMazeIngRenderer)
from ..session import ALGORITHMS, ConfigProblem, Replay, Session
from .error import ProblemFound
from .layout import (ZOOM_BINDINGS, MazeBody, TooNarrowNotice,
                     zoom_allowed)
from .titlebar import TitleBar

MUTED = "#8A939C"
FPS = 30
SPEEDS = [2, 4, 8, 16, 32, 64, 128]  # history events replayed per frame
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
BAR_WIDTH = 40


class GeneratorScreen(Screen[None]):
    """Replays the session's current maze, wall by wall, then shows the
    finished maze with its shortest path."""

    BINDINGS = [
        Binding("space", "pause", "Pause", key_display="Space"),
        Binding("space", "resume", "Resume", key_display="Space"),
        Binding("r", "replay", "Replay", key_display="R"),
        Binding("s", "skip", "Skip to end", key_display="S"),
        Binding("minus", "slower", "Slower", key_display="-"),
        Binding("plus,equals_sign", "faster", "Faster", key_display="+"),
        Binding("a", "algorithm", "Algorithm", key_display="A"),
        *ZOOM_BINDINGS,
        Binding("escape", "back", "Back", key_display="Esc"),
    ]

    def __init__(self, session: Session) -> None:
        """Create the screen to replay *session*'s current maze."""
        super().__init__()
        self.session = session
        self.replay = Replay(session.current)
        self.speed = 3
        self.paused = False
        self.frame = 0
        self.timer: Timer | None = None

    def compose(self) -> ComposeResult:
        """Lay out the title bar, maze, side panels, progress and keys."""
        yield TitleBar(self.session.config_path)
        with MazeBody(self.session.config.width,
                      self.session.config.height):
            yield TooNarrowNotice(id="too-narrow", classes="panel")
            with Center(id="maze-holder"):
                with ScrollableContainer(id="maze-panel"):
                    yield AMazeIngRenderer(dim_untouched=True)
            with Vertical(id="side"):
                yield Static(id="algorithms", classes="panel")
                yield Static(id="progress", classes="panel")
                yield Static(self._legend(), id="legend", classes="panel")
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        """Start the replay."""
        renderer = self.query_one(AMazeIngRenderer)
        renderer.wall_colour = WALL_COLOURS[self.session.wall_colour].hex
        renderer.logo_colour = LOGO_COLOURS[self.session.logo_colour].hex
        renderer.expanded = self.session.expanded
        self.timer = self.set_interval(1 / FPS, self._tick)
        self._draw()

    # called by textual to check whether a key binding is offered,
    # when the footer is drawn, and when a key is pressed
    def check_action(self, action: str,
                     parameters: tuple[object, ...]) -> bool | None:
        """Offer only the keys that make sense right now."""
        zoom = zoom_allowed(self, action)
        if zoom is not None:
            return zoom
        done = self.replay.done
        if action == "pause":
            return not done and not self.paused
        if action == "resume":
            return not done and self.paused
        if action == "skip":
            return not done
        if action == "replay":
            return done
        if action == "algorithm":
            return len(ALGORITHMS) > 1
        return True

    def _tick(self) -> None:
        """Replay the next few history events."""
        if self.paused or self.replay.done:
            return
        self.frame += 1
        self.replay.advance(SPEEDS[self.speed])
        self._draw()
        if self.replay.done:
            self.refresh_bindings()

    def _draw(self) -> None:
        """Bring every part of the screen up to date with the replay."""
        replay = self.replay
        run = replay.run
        config = run.maze.config
        done = replay.done

        renderer = self.query_one(AMazeIngRenderer)
        if done:
            renderer.show(run.maze, run.path)
        else:
            renderer.show(replay.maze, trail=replay.walk)

        status = "DONE" if done else "PAUSED" if self.paused \
            else "GENERATING"
        self.query_one(TitleBar).show(
            status, tone="cyan", dims=f"{config.width}×{config.height}",
            seed=self.session.seed)

        # show selected algorithm in gold, and the others in muted colour
        self.query_one("#algorithms", Static).update(Text("\n").join(
            Text(f"▸ {name}" if index == self.session.algorithm
                 else f"  {name}",
                 GOLD.hex if index == self.session.algorithm else MUTED)
            for index, (name, _) in enumerate(ALGORITHMS)))

        progress = Table.grid(expand=True)
        progress.add_column(style=MUTED)
        progress.add_column(justify="right")
        progress.add_row("phase", replay.phase)
        progress.add_row("cells reached",
                         f"{replay.touched} / {replay.playable}")
        progress.add_row("walk", str(len(replay.walk)))
        progress.add_row("speed", f"×{2 ** self.speed} "
                         f"({SPEEDS[self.speed] * FPS}/s)")
        self.query_one("#progress", Static).update(progress)

        total = max(len(run.history), 1)
        share = replay.position / total
        filled = round(share * BAR_WIDTH)
        if done:
            spinner = "✓"
        elif self.paused:
            spinner = "‖"
        else:
            spinner = SPINNER[self.frame % len(SPINNER)]
        line = Text.assemble(
            (spinner, CYAN.hex), "  ",
            ("█" * filled + "░" * (BAR_WIDTH - filled), CYAN.hex),
            f"  {share:4.0%}")
        if done:
            line.append(f"  maze complete · shortest path "
                        f"{len(run.path) - 1}", MUTED)
        self.query_one("#status", Static).update(line)

    @staticmethod
    def _legend() -> Text:
        """What the replay's colours mean."""
        swatches = [
            (GOLD.hex, "walk head"),
            (GROUND.blend(CYAN, 0.4).hex, "random walk"),
            (UNTOUCHED.hex, "not reached yet"),
        ]
        return Text("\n").join(
            Text.assemble(("  ", f"on {colour}"), f" {label}")
            for colour, label in swatches)

    def _changed(self) -> None:
        """Redraw, and refresh the keys that depend on the state."""
        self._draw()
        self.refresh_bindings()

    def action_pause(self) -> None:
        """Stop the replay where it is."""
        self.paused = True
        self._changed()

    def action_resume(self) -> None:
        """Carry on with the replay."""
        self.paused = False
        self._changed()

    def action_skip(self) -> None:
        """Jump to the finished maze."""
        self.replay.finish()
        self._changed()

    def action_replay(self) -> None:
        """Start the replay again from a fully walled grid."""
        self.replay = Replay(self.session.current)
        self.paused = False
        self._changed()

    def action_slower(self) -> None:
        """Replay fewer history events per frame."""
        self.speed = max(0, self.speed - 1)
        self._draw()

    def action_faster(self) -> None:
        """Replay more history events per frame."""
        self.speed = min(len(SPEEDS) - 1, self.speed + 1)
        self._draw()

    def action_algorithm(self) -> None:
        """Rebuild the maze with the next generator and replay it."""
        try:
            self.session.next_algorithm()
        except ConfigProblem as problem:
            self.post_message(ProblemFound(problem))
            return
        self.action_replay()

    def action_expand(self) -> None:
        """Draw the maze full size, even though it then scrolls."""
        self.session.expanded = True
        self.query_one(AMazeIngRenderer).expanded = True
        self.refresh_bindings()

    def action_shrink(self) -> None:
        """Draw the maze compact again, so it fits."""
        self.session.expanded = False
        self.query_one(AMazeIngRenderer).expanded = False
        self.refresh_bindings()

    def action_back(self) -> None:
        """Return to the main screen."""
        self.dismiss()
