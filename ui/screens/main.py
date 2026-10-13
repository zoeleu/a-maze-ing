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

"""The screen that shows the maze and lets the user play with it."""
from typing import TYPE_CHECKING, Callable

from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from ..renderer import LOGO_COLOURS, WALL_COLOURS, AMazeIngRenderer
from ..session import ALGORITHMS, MazeRun, Session
from .algorithms import AlgorithmPicker
from .layout import (ZOOM_BINDINGS, MazeBody, TooNarrowNotice,
                     zoom_allowed)
from .generator import GeneratorScreen
from .titlebar import TitleBar

if TYPE_CHECKING:
    # only for the type checker: the app imports this module
    from ..app import AMazeIngApp

MUTED = "#8A939C"
GREEN = "#7FD18B"
AMBER = "#F2C14E"
RED = "#F25F5C"


def readout(*rows: tuple[str, str]) -> Table:
    """Label / value pairs, the labels muted and the values right-aligned.
    Useful for the statistics panels."""
    table = Table.grid(expand=True)
    table.add_column(style=MUTED)
    table.add_column(justify="right")
    for label, value in rows:
        table.add_row(label, value)
    return table


def badge(run: MazeRun) -> tuple[str, str]:
    """The title bar badge and its tone for the maze's mode."""
    if run.maze.config.perfect:
        return "PERFECT", "gold"
    return "PAC-MAN", "cyan"


class MainScreen(Screen[None]):
    """The maze, its config and numbers, and the keys to change it."""
    app: "AMazeIngApp"

    BINDINGS = [
        Binding("r", "regenerate", "Regenerate", key_display="R"),
        Binding("p", "hide_path", "Hide path", key_display="P"),
        Binding("p", "show_path", "Show path", key_display="P"),
        Binding("c", "wall_colour", "Wall colour", key_display="C"),
        Binding("f", "logo_colour", "42 colour", key_display="F"),
        Binding("m", "toggle_mode", "Perfect / Pac-Man", key_display="M"),
        Binding("a", "algorithm", "Algorithm", key_display="A"),
        *ZOOM_BINDINGS,
        Binding("g", "animate", "Animate", key_display="G"),
    ]

    def __init__(self, session: Session) -> None:
        """Create the screen for *session*'s current maze."""
        super().__init__()
        self.session = session

    def compose(self) -> ComposeResult:
        """Lay out the title bar, maze, side panels, status and keys."""
        yield TitleBar(self.session.config_path)
        yield Static(id="warning", classes="banner")
        with MazeBody(self.session.config.width,
                      self.session.config.height):
            yield TooNarrowNotice(id="too-narrow", classes="panel")
            with Center(id="maze-holder"):
                with ScrollableContainer(id="maze-panel"):
                    yield AMazeIngRenderer()
            with Vertical(id="side"):
                yield AlgorithmPicker(self.session.algorithm)
                yield Static(id="config", classes="panel")
                yield Static(id="stats", classes="panel")
                yield Static(id="note", classes="note")
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        """Draw the session's current maze, and offer the keys that apply
        to it."""
        self.refresh_maze()
        # The footer asks check_action() which keys to show. It can ask
        # while this screen is still being put together, when check_action()
        # cannot tell yet and hides the path keys (see there). Now that the
        # screen is complete, make the footer ask again.
        self.refresh_bindings()

    def on_screen_resume(self) -> None:
        """Catch up with changes made on another screen."""
        self.refresh_maze()

    def check_action(self, action: str,
                     parameters: tuple[object, ...]) -> bool | None:
        """Offer only the path, zoom and algorithm keys that apply."""
        zoom = zoom_allowed(self, action)
        if zoom is not None:
            return zoom
        if action == "algorithm":
            return len(ALGORITHMS) > 1
        # is_mounted turns True once the screen and all its widgets are in
        # place. Before that, the footer may already ask about the keys,
        # and the renderer below may not exist yet: query_one() would raise
        # and crash the app. Hide the keys for now; on_mount() asks again.
        if not self.is_mounted:
            return False
        showing = self.query_one(AMazeIngRenderer).show_path
        if action == "hide_path":
            return showing
        if action == "show_path":
            return not showing
        return True

    def refresh_maze(self) -> None:
        """Bring every part of the screen up to date with the session."""
        session = self.session
        run = session.current
        config = run.maze.config

        renderer = self.query_one(AMazeIngRenderer)
        renderer.wall_colour = WALL_COLOURS[session.wall_colour].hex
        renderer.logo_colour = LOGO_COLOURS[session.logo_colour].hex
        renderer.expanded = session.expanded
        renderer.show(run.maze, run.path)

        self.query_one(TitleBar).show(
            *badge(run), dims=f"{config.width}×{config.height}",
            seed=session.seed)
        self.query_one(AlgorithmPicker).select(session.algorithm)

        warning = self.query_one("#warning", Static)
        warning.display = not run.maze.has_logo
        warning.update(Text.assemble(
            ("! ", "bold"), f"{config.width}×{config.height} is too small "
            f"for the “42” pattern. Pattern omitted."))
        self.query_one("#note", Static).update(
            "" if run.maze.has_logo
            else "This warning is also printed to the console.")

        settings: list[tuple[str, object]] = [
            ("WIDTH", config.width), ("HEIGHT", config.height),
            ("ENTRY", "{},{}".format(*config.entry)),
            ("EXIT", "{},{}".format(*config.exit)),
            ("OUTPUT_FILE", config.output_file),
            ("PERFECT", config.perfect), ("SEED", session.seed),
        ]
        self.query_one("#config", Static).update(Text("\n").join(
            Text.assemble((f"{key}=", MUTED), str(value))
            for key, value in settings))

        self.query_one("#stats", Static).update(readout(
            ("mode", "perfect" if config.perfect else "pac-man"),
            ("algorithm", run.algorithm.split(" ")[0]),
            ("shortest path", str(len(run.path) - 1)),
            ("dead ends", str(run.dead_ends)),
            ("walls", WALL_COLOURS[session.wall_colour].name),
            ("42", LOGO_COLOURS[session.logo_colour].name),
        ))

        self.query_one("#status", Static).update(self._status(run))

    @staticmethod
    def _status(run: MazeRun) -> Text:
        """The line under the maze: whether the output was written, and how
        long the maze took to build."""
        output = run.maze.config.output_file
        took = f"{run.elapsed * 1000:.0f} ms" if run.elapsed >= 0.001 \
            else "<1 ms"
        if run.write_error is not None:
            status = Text.assemble(
                ("✗ ", RED), f"could not write {output}: {run.write_error}")
        else:
            status = Text.assemble(("✓ ", GREEN), f"wrote {output}")
        status.append(f" · built in {took}", MUTED)
        if not run.braided:
            status.append(" · some dead ends could not be removed", AMBER)
        return status

    def _change(self) -> None:
        """Redraw after a change, and refresh the keys that depend on it."""
        self.refresh_maze()
        self.refresh_bindings()

    def _rebuild(self, build_maze: Callable[[], MazeRun]) -> None:
        """Run *build_maze*, a session method that builds a new maze, behind
        the progress screen, then redraw."""
        # app.build() runs build_maze on another thread, so the interface
        # does not freeze while a big maze is built, then calls when_built
        # back on the interface's thread: _change() redraws the screen with
        # the new maze
        self.app.build(build_maze=build_maze,
                       when_built=lambda run: self._change())

    def action_regenerate(self) -> None:
        """Build a new maze from a fresh seed."""
        self._rebuild(self.session.regenerate)

    def action_show_path(self) -> None:
        """Draw the shortest path from entry to exit."""
        self.query_one(AMazeIngRenderer).show_path = True
        self.refresh_bindings()

    def action_hide_path(self) -> None:
        """Stop drawing the shortest path."""
        self.query_one(AMazeIngRenderer).show_path = False
        self.refresh_bindings()

    def action_wall_colour(self) -> None:
        """Switch to the next wall colour."""
        session = self.session
        session.wall_colour = (session.wall_colour + 1) % len(WALL_COLOURS)
        self._change()

    def action_logo_colour(self) -> None:
        """Switch to the next colour for the 42 pattern."""
        session = self.session
        session.logo_colour = (session.logo_colour + 1) % len(LOGO_COLOURS)
        self._change()

    def action_toggle_mode(self) -> None:
        """Rebuild the same maze as perfect or braided (pac-man)."""
        self._rebuild(self.session.toggle_perfect)

    def action_expand(self) -> None:
        """Draw the maze full size, even though it then scrolls."""
        self.session.expanded = True
        self._change()

    def action_shrink(self) -> None:
        """Draw the maze compact again, so it fits."""
        self.session.expanded = False
        self._change()

    def action_algorithm(self) -> None:
        """Rebuild the maze, from the same seed, with the next generator."""
        self._switch_algorithm((self.session.algorithm + 1) % len(ALGORITHMS))

    def on_algorithm_picker_chosen(self,
                                   message: AlgorithmPicker.Chosen) -> None:
        """Rebuild the maze, from the same seed, with the clicked
        generator."""
        self._switch_algorithm(message.index)

    def _switch_algorithm(self, index: int) -> None:
        """Rebuild the maze with ALGORITHMS[*index*]."""
        self._rebuild(lambda: self.session.set_algorithm(index))

    def action_animate(self) -> None:
        """Replay how the current maze was built."""
        self.app.push_screen(GeneratorScreen(self.session))
