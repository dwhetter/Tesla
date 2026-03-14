import random

TETROMINO_SHAPES = [
    [[1, 1, 1, 1]],  # I
    [[1, 1], [1, 1]],  # O
    [[0, 1, 0], [1, 1, 1]],  # T
    [[1, 1, 0], [0, 1, 1]],  # S
    [[0, 1, 1], [1, 1, 0]],  # Z
    [[1, 0, 0], [1, 1, 1]],  # J
    [[0, 0, 1], [1, 1, 1]],  # L
]
TETROMINO_COLORS = [
    (0, 255, 255),  # I
    (255, 255, 0),  # O
    (128, 0, 128),  # T
    (0, 255, 0),    # S
    (255, 0, 0),    # Z
    (0, 0, 255),    # J
    (255, 165, 0),  # L
]

class Tetromino:
    def __init__(self, x, y):
        self.shape_id = random.randint(0, len(TETROMINO_SHAPES)-1)
        self.shape = TETROMINO_SHAPES[self.shape_id]
        self.color = TETROMINO_COLORS[self.shape_id]
        self.x = x
        self.y = y
        self.rotation = 0

    def get_blocks(self):
        blocks = []
        for dy, row in enumerate(self.shape):
            for dx, cell in enumerate(row):
                if cell:
                    blocks.append((self.x + dx, self.y + dy))
        return blocks

    def move(self, dx, dy, board):
        self.x += dx
        self.y += dy
        if not self.valid(board):
            self.x -= dx
            self.y -= dy
            return False
        return True

    def rotate(self, board):
        old_shape = self.shape
        self.shape = [list(row) for row in zip(*self.shape[::-1])]
        if not self.valid(board):
            self.shape = old_shape
            return False
        return True

    def valid(self, board):
        for x, y in self.get_blocks():
            if x < 0 or x >= 10 or y >= 20:
                return False
            if y >= 0 and board[y][x]:
                return False
        return True
