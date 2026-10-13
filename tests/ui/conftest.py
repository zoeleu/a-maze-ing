"""Fixtures to drive the Textual app headless, through its pilot."""
import asyncio
from pathlib import Path

import pytest

from ui import AMazeIngApp
from ui import app as app_module
from tests.ui.helpers import Drive, FakeMazeWindow, Scenario, built


@pytest.fixture(autouse=True)
def no_real_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give every app a FakeMazeWindow, so no test opens an MLX window."""
    monkeypatch.setattr(app_module, "MazeWindow", FakeMazeWindow)


@pytest.fixture
def drive(in_tmp: Path) -> Drive:
    """Run the app for a config, play *scenario* on it, and return the app
    once it has shut down. Runs in the test's temporary directory, where
    the maze is written."""
    def run(config_path: str, scenario: Scenario,
            size: tuple[int, int] = (120, 40)) -> AMazeIngApp:
        """Run the app on *config_path* in a *size* terminal, play *scenario*,
        and return the app once it has shut down."""
        app = AMazeIngApp(config_path)

        async def main() -> None:
            """Start the app headless and hand its pilot to the scenario."""
            async with app.run_test(size=size) as pilot:
                await built(pilot)
                await scenario(pilot)
        asyncio.run(main())
        return app
    return run
