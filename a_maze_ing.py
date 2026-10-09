from lib import Maze, Direction

class MazeGenerationError(Exception):
    pass


if __name__ == "__main__":
    all_dir = Direction.NORTH | Direction.EAST | \
        Direction.SOUTH | Direction.WEST
    row_max = 8
    col_max = 8
    for row in range(6, row_max + 1):
        for col in range(8, col_max + 1):
            maze = Maze([[all_dir for _ in range(col)] for _ in range(row)])
            print(maze.render())
