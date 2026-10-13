"""Config: reading, parsing and checking the config file."""
from pathlib import Path

import pytest

from lib import Config
from tests.helpers import VALID_CONFIG, WriteConfig


def with_line(key: str, value: str | None) -> str:
    """VALID_CONFIG with *key* set to *value*, or removed if None."""
    lines = [line for line in VALID_CONFIG.splitlines()
             if not line.startswith(f"{key}=")]
    if value is not None:
        lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


def test_reads_every_key(valid_config: str) -> None:
    """Every key of a valid config ends up as a lowercase attribute."""
    config = Config(valid_config)
    assert config.width == 10
    assert config.height == 8
    assert config.entry == (0, 0)
    assert config.exit == (9, 7)
    assert config.output_file == "maze.txt"
    assert config.perfect is True
    assert config.seed == "42"


def test_parsed_types(valid_config: str) -> None:
    """Values are parsed into ints, a tuple and a bool, not left as text."""
    config = Config(valid_config)
    assert type(config.width) is int
    assert type(config.height) is int
    assert type(config.entry) is tuple
    assert type(config.perfect) is bool


def test_seed_is_optional(write_config: WriteConfig) -> None:
    """Without SEED, the seed is None."""
    config = Config(write_config(with_line("SEED", None)))
    assert config.seed is None


def test_empty_seed_is_kept_as_empty(write_config: WriteConfig) -> None:
    """An empty SEED is kept as an empty string."""
    config = Config(write_config(with_line("SEED", "")))
    assert config.seed == ""


@pytest.mark.parametrize(("text", "perfect"), [("True", True),
                                               ("False", False)])
def test_perfect(write_config: WriteConfig, text: str,
                 perfect: bool) -> None:
    """PERFECT accepts True and False."""
    assert Config(write_config(with_line("PERFECT", text))).perfect is perfect


def test_comments_and_blank_lines_are_skipped(
        write_config: WriteConfig) -> None:
    """Comment lines and blank lines are ignored."""
    text = "# header\n\n   \n" + VALID_CONFIG + "\n# trailer\n"
    assert Config(write_config(text)).width == 10


def test_spaces_around_keys_and_values_are_stripped(
        write_config: WriteConfig) -> None:
    """Spaces around a key or a value do not matter."""
    text = VALID_CONFIG.replace("WIDTH=10", "  WIDTH  =  12  ")
    assert Config(write_config(text)).width == 12


def test_value_may_contain_equals(write_config: WriteConfig) -> None:
    """Only the first = splits a line, so a value may contain one."""
    config = Config(write_config(with_line("OUTPUT_FILE", "a=b.txt")))
    assert config.output_file == "a=b.txt"


def test_last_occurrence_of_a_key_wins(write_config: WriteConfig) -> None:
    """A key given twice keeps its last value."""
    config = Config(write_config(VALID_CONFIG + "WIDTH=11\n"))
    assert config.width == 11


def test_unknown_keys_are_ignored_with_a_warning(
        write_config: WriteConfig, capsys: pytest.CaptureFixture[str]) -> None:
    """An unknown key is skipped, with a warning on stdout."""
    config = Config(write_config(VALID_CONFIG + "COLOUR=red\n"))
    assert not hasattr(config, "colour")
    assert "Unknown key `COLOUR`" in capsys.readouterr().out


def test_missing_file(tmp_path: Path) -> None:
    """A config that does not exist raises FileNotFoundError."""
    missing = tmp_path / "nope.txt"
    with pytest.raises(FileNotFoundError, match="Config file not found"):
        Config(str(missing))


def test_a_directory_is_not_a_config(tmp_path: Path) -> None:
    """A directory is rejected like a missing file."""
    with pytest.raises(FileNotFoundError):
        Config(str(tmp_path))


@pytest.mark.parametrize("key", ["WIDTH", "HEIGHT", "ENTRY", "EXIT",
                                 "OUTPUT_FILE", "PERFECT"])
def test_every_mandatory_key_is_required(write_config: WriteConfig,
                                         key: str) -> None:
    """Leaving out any mandatory key raises IndexError naming it."""
    with pytest.raises(IndexError, match=f"Missing the following keys.*"
                                         f"'{key}'"):
        Config(write_config(with_line(key, None)))


def test_missing_keys_are_all_listed(write_config: WriteConfig) -> None:
    """Every missing key is named in the same error."""
    with pytest.raises(IndexError) as info:
        Config(write_config("SEED=1\n"))
    for key in ("WIDTH", "HEIGHT", "ENTRY", "EXIT", "OUTPUT_FILE", "PERFECT"):
        assert key in str(info.value)


def test_line_without_equals(write_config: WriteConfig) -> None:
    """A line that is not KEY=VALUE is reported with its line number."""
    text = VALID_CONFIG.replace("WIDTH=10", "WIDTH 10")
    with pytest.raises(ValueError, match=r"Line 2 is not KEY=VALUE: "
                                         r"`WIDTH 10`"):
        Config(write_config(text))


@pytest.mark.parametrize(("key", "value"), [
    ("WIDTH", "ten"),
    ("WIDTH", "-5"),
    ("WIDTH", "1.5"),
    ("WIDTH", ""),
    ("HEIGHT", "8x"),
    ("ENTRY", "0"),
    ("ENTRY", "0,0,0"),
    ("ENTRY", "0, 0"),
    ("ENTRY", "(0,0)"),
    ("EXIT", "-1,0"),
    ("OUTPUT_FILE", ""),
    ("PERFECT", "true"),
    ("PERFECT", "yes"),
    ("PERFECT", "1"),
])
def test_malformed_values(write_config: WriteConfig, key: str,
                          value: str) -> None:
    """A value in the wrong format is rejected, naming its key."""
    with pytest.raises(ValueError,
                       match=rf"Invalid value `.*` at key\s+`{key}`"):
        Config(write_config(with_line(key, value)))


@pytest.mark.parametrize("key", ["WIDTH", "HEIGHT"])
def test_size_must_be_at_least_one(write_config: WriteConfig,
                                   key: str) -> None:
    """A maze must be at least one cell wide and tall."""
    with pytest.raises(ValueError, match=f"`0` at key `{key}`: must be at "
                                         f"least 1"):
        Config(write_config(with_line(key, "0")))


@pytest.mark.parametrize(("key", "value", "axis"), [
    ("ENTRY", "10,0", "x"),
    ("ENTRY", "0,8", "y"),
    ("EXIT", "99,0", "x"),
    ("EXIT", "9,8", "y"),
])
def test_cells_must_be_inside_the_maze(write_config: WriteConfig, key: str,
                                       value: str, axis: str) -> None:
    """An entry or exit outside the maze is rejected, naming the coordinate
    that is out of range."""
    with pytest.raises(ValueError, match=f"`{value}` at key `{key}`: "
                                         f"{axis} must be between"):
        Config(write_config(with_line(key, value)))


def test_last_cell_is_inside_the_maze(write_config: WriteConfig) -> None:
    """The last column is still inside the maze."""
    config = Config(write_config(with_line("ENTRY", "9,0")))
    assert config.entry == (9, 0)


def test_entry_and_exit_must_differ(write_config: WriteConfig) -> None:
    """The entry and exit cannot be the same cell."""
    with pytest.raises(ValueError, match="must be a different cell from "
                                         "ENTRY"):
        Config(write_config(with_line("EXIT", "0,0")))


@pytest.mark.parametrize("key", ["ENTRY", "EXIT"])
def test_cells_must_not_be_on_the_logo(write_config: WriteConfig,
                                       key: str) -> None:
    """The entry and exit cannot sit on the 42 pattern."""
    # (1, 1) is the top of the 4 in a 10x8 maze
    with pytest.raises(ValueError, match=f"`1,1` at key `{key}`: falls on "
                                         f"the 42 pattern"):
        Config(write_config(with_line(key, "1,1")))


def test_logo_cells_are_fine_when_the_logo_does_not_fit(
        write_config: WriteConfig) -> None:
    """In a maze too small for the logo, its cells are ordinary cells."""
    text = (with_line("WIDTH", "4").replace("EXIT=9,7", "EXIT=1,1")
            .replace("HEIGHT=8", "HEIGHT=4"))
    config = Config(write_config(text))
    assert config.exit == (1, 1)


def test_one_by_two_maze(write_config: WriteConfig) -> None:
    """The smallest maze with two distinct cells is accepted."""
    text = (VALID_CONFIG.replace("WIDTH=10", "WIDTH=1")
            .replace("HEIGHT=8", "HEIGHT=2").replace("EXIT=9,7", "EXIT=0,1"))
    config = Config(write_config(text))
    assert (config.width, config.height) == (1, 2)


def test_binary_file_is_not_a_config(tmp_path: Path) -> None:
    """A file that is not text raises UnicodeDecodeError."""
    path = tmp_path / "binary"
    path.write_bytes(b"\xff\xfe\x00\x01")
    with pytest.raises(UnicodeDecodeError):
        Config(str(path))


def test_from_dict_sets_attributes_without_checking() -> None:
    """from_dict copies the values as they are, without validating them."""
    config = Config.from_dict({
        "WIDTH": 3, "HEIGHT": 2, "ENTRY": (0, 0), "EXIT": (0, 0),
        "OUTPUT_FILE": "out", "PERFECT": False, "SEED": None,
    })
    assert isinstance(config, Config)
    assert (config.width, config.height) == (3, 2)
    assert config.entry == config.exit == (0, 0)  # not rejected
    assert config.output_file == "out"
    assert config.perfect is False
    assert config.seed is None
