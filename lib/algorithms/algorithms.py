from abc import ABC, abstractmethod
import lib


class GeneratorError(Exception):
    pass


class Generator(ABC):
    @abstractmethod
    def generate(self, maze: lib.Maze) -> None:
        pass
