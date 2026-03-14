import pygame
import random
from tetromino import Tetromino, TETROMINO_SHAPES

CELL_SIZE = 30
COLS = 10
ROWS = 20
WIDTH = COLS * CELL_SIZE
HEIGHT = ROWS * CELL_SIZE

class TetrisGame:
    def __init__(self, screen):
        self.screen = screen
        self.board = [[0 for _ in range(COLS)] for _ in range(ROWS)]
        self.score = 0
        self.current = Tetromino(COLS // 2 - 1, 0)
        self.game_over = False
        self.last_drop_time = pygame.time.get_ticks()
        self.drop_speed = 500  # ms (0.5 second)

    def handle_event(self, event):
        if self.game_over:
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT:
                self.current.move(-1, 0, self.board)
            elif event.key == pygame.K_RIGHT:
                self.current.move(1, 0, self.board)
            elif event.key == pygame.K_DOWN:
                self.current.move(0, 1, self.board)
            elif event.key == pygame.K_UP:
                self.current.rotate(self.board)
            elif event.key == pygame.K_SPACE:
                while self.current.move(0, 1, self.board):
                    pass
                self.lock_tetromino()

    def update(self):
        if self.game_over:
            return
        now = pygame.time.get_ticks()
        if now - self.last_drop_time >= self.drop_speed:
            if not self.current.move(0, 1, self.board):
                self.lock_tetromino()
            self.last_drop_time = now

    def lock_tetromino(self):
        for x, y in self.current.get_blocks():
            if y < 0:
                self.game_over = True
                return
            self.board[y][x] = self.current.color
        self.clear_lines()
        self.current = Tetromino(COLS // 2 - 1, 0)
        if not self.current.valid(self.board):
            self.game_over = True

    def clear_lines(self):
        new_board = [row for row in self.board if any(cell == 0 for cell in row)]
        lines_cleared = ROWS - len(new_board)
        self.score += lines_cleared * 100
        for _ in range(lines_cleared):
            new_board.insert(0, [0 for _ in range(COLS)])
        self.board = new_board

    def draw(self):
        self.screen.fill((0, 0, 0))
        # Draw board
        for y in range(ROWS):
            for x in range(COLS):
                color = self.board[y][x]
                if color:
                    pygame.draw.rect(self.screen, color, (x*CELL_SIZE, y*CELL_SIZE, CELL_SIZE, CELL_SIZE))
        # Draw current tetromino
        for x, y in self.current.get_blocks():
            if y >= 0:
                pygame.draw.rect(self.screen, self.current.color, (x*CELL_SIZE, y*CELL_SIZE, CELL_SIZE, CELL_SIZE))
        # Draw grid
        for x in range(COLS):
            pygame.draw.line(self.screen, (40, 40, 40), (x*CELL_SIZE, 0), (x*CELL_SIZE, HEIGHT))
        for y in range(ROWS):
            pygame.draw.line(self.screen, (40, 40, 40), (0, y*CELL_SIZE), (WIDTH, y*CELL_SIZE))
        # Draw score
        font = pygame.font.SysFont('Arial', 24)
        score_surf = font.render(f'Score: {self.score}', True, (255,255,255))
        self.screen.blit(score_surf, (10, 10))
        if self.game_over:
            over_surf = font.render('GAME OVER', True, (255,0,0))
            self.screen.blit(over_surf, (60, HEIGHT//2))
