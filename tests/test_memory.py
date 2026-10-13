"""ui.memory: the cap on the program's memory, and the estimate of what a
maze needs."""
import resource
from pathlib import Path

import pytest

from ui import memory
from ui.memory import (BASE_BYTES, BYTES_PER_CELL, MB, available_memory,
                       limit_memory, memory_limit, memory_needed, too_big,
                       warning)

INFINITY = resource.RLIM_INFINITY


def fake_limits(monkeypatch: pytest.MonkeyPatch, soft: int,
                hard: int) -> list[tuple[int, int]]:
    """Make the program's memory limits (*soft*, *hard*) without touching
    the real ones, and return the list setrlimit() calls are recorded in."""
    calls: list[tuple[int, int]] = []

    def setrlimit(kind: int, limits: tuple[int, int]) -> None:
        """Stand-in for resource.setrlimit(): records the new limits."""
        calls.append(limits)
    monkeypatch.setattr(resource, "getrlimit", lambda kind: (soft, hard))
    monkeypatch.setattr(resource, "setrlimit", setrlimit)
    return calls


class TestAvailableMemory:
    """Reading the available memory from /proc/meminfo."""

    def test_reads_mem_available(self, tmp_path: Path) -> None:
        """MemAvailable is read, and turned from kB into bytes."""
        meminfo = tmp_path / "meminfo"
        meminfo.write_text("MemTotal:   2048 kB\nMemAvailable:   1024 kB\n")
        assert available_memory(str(meminfo)) == 1024 * 1024

    @pytest.mark.parametrize("text", [None, "MemTotal: 2048 kB\n",
                                      "MemAvailable: lots\n"])
    def test_unknown(self, tmp_path: Path, text: str | None) -> None:
        """A missing file, line or number gives None."""
        meminfo = tmp_path / "meminfo"
        if text is not None:
            meminfo.write_text(text)
        assert available_memory(str(meminfo)) is None


class TestLimitMemory:
    """Capping the program's memory."""

    def test_caps_at_a_share_of_the_available_memory(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without a cap yet, the cap is 80% of the available memory."""
        monkeypatch.setattr(memory, "available_memory", lambda: 1000 * MB)
        calls = fake_limits(monkeypatch, INFINITY, INFINITY)
        limit_memory()
        assert calls == [(800 * MB, INFINITY)]

    def test_keeps_a_lower_cap(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A lower cap set before, e.g. with ulimit -v, is kept."""
        monkeypatch.setattr(memory, "available_memory", lambda: 1000 * MB)
        calls = fake_limits(monkeypatch, 500 * MB, INFINITY)
        limit_memory()
        assert calls == []

    def test_stays_under_the_hard_limit(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The cap cannot go above the hard limit."""
        monkeypatch.setattr(memory, "available_memory", lambda: 1000 * MB)
        calls = fake_limits(monkeypatch, INFINITY, 600 * MB)
        limit_memory()
        assert calls == [(600 * MB, 600 * MB)]

    def test_unknown_available_memory(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without knowing the available memory, nothing is capped."""
        monkeypatch.setattr(memory, "available_memory", lambda: None)
        calls = fake_limits(monkeypatch, INFINITY, INFINITY)
        limit_memory()
        assert calls == []

    @pytest.mark.parametrize(("soft", "limit"), [(INFINITY, None),
                                                 (123, 123)])
    def test_memory_limit(self, monkeypatch: pytest.MonkeyPatch, soft: int,
                          limit: int | None) -> None:
        """memory_limit() is the cap in force, or None without one."""
        fake_limits(monkeypatch, soft, INFINITY)
        assert memory_limit() == limit


class TestEstimate:
    """Estimating what a maze needs, and warning about it."""

    def test_memory_needed(self) -> None:
        """The program's own memory, plus each cell of each maze."""
        assert memory_needed(10, 20) == BASE_BYTES + 200 * BYTES_PER_CELL
        assert memory_needed(10, 20, mazes=2) == \
            BASE_BYTES + 400 * BYTES_PER_CELL

    @pytest.mark.parametrize(("limit", "big"), [
        (None, False), (BASE_BYTES + 100 * BYTES_PER_CELL, False),
        (BASE_BYTES + 99 * BYTES_PER_CELL, True),
    ])
    def test_too_big(self, monkeypatch: pytest.MonkeyPatch,
                     limit: int | None, big: bool) -> None:
        """A maze is too big when it needs more than the cap; nothing is
        too big without a cap."""
        monkeypatch.setattr(memory, "memory_limit", lambda: limit)
        assert too_big(10, 10) is big

    def test_warning(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The warning gives the size, what it needs and what is
        allowed."""
        monkeypatch.setattr(memory, "memory_limit", lambda: 1024 ** 3)
        text = warning(1000, 1000, mazes=2)
        assert "1000×1000" in text
        assert "about 4.8 GB" in text
        assert "only use 1.0 GB" in text
