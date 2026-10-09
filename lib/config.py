from pathlib import Path
from typing import Callable, Any
import re


class Config:
    width: int
    height: int
    entry: tuple[int, int]
    exit: tuple[int, int]
    output: str
    perfect: bool
    seed: int

    def __init__(self, config_path: str):
        path = Path(config_path)

        if not path.is_file():
            raise FileNotFoundError(f"Config file not found at {config_path}!")

        kv = self.__read_file_dict(config_path)

        check_dict: dict[str, str] = {
            "WIDTH": "^[0-9]+$",
            "HEIGHT": "^[0-9]+$",
            "ENTRY": "^[0-9]+,[0-9]+$",
            "EXIT": "^[0-9]+,[0-9]+$",
            "OUTPUT_FILE": "^(?!:\\0)$",
            "PERFECT": "^(True|False)$",
            "SEED": "^[0-9]+$"
        }

        parse_dict: dict[str, Callable[[str], Any]] = {
            "WIDTH": lambda w: int(w),
            "HEIGHT": lambda h: int(h),
            "ENTRY": lambda e: tuple(map(int, e.split(","))),
            "EXIT": lambda e: tuple(map(int, e.split(","))),
            "OUTPUT_FILE": lambda o: o,
            "PERFECT": lambda p: p == "True",
            "SEED": lambda s: int(s)
        }

        mandatory = {
            "WIDTH",
            "HEIGHT",
            "ENTRY",
            "EXIT",
            "OUTPUT_FILE",
            "PERFECT"
        }

        if not mandatory.issubset(kv.keys()):
            raise IndexError(f"Missing the following keys: {mandatory.difference(kv.keys())}")

        for key in kv.keys():
            if key not in check_dict:
                continue
            if key not in parse_dict:
                continue
            if not re.match(check_dict[key], kv[key]):
                raise ValueError(f"Invalid value `{kv[key]}` at key \
                                 `{key}`: in config file")
            setattr(self, key.lower(), parse_dict[key](kv[key]))

    def __read_file_dict(self, filename: str) -> dict[str, str]:
        with open(filename) as file:
            lines_read = file.readlines()

        # Removes comments
        lines = filter(lambda s: not s.startswith("#"), lines_read)
        # Splits into [[key, value], ...]
        keys_values = map(lambda line: line.split("=", 1), lines)

        return dict(keys_values)
