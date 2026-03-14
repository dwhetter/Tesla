import pygame
import sys
from game import TetrisGame

# Initialize Pygame
def main():
    pygame.init()
    screen = pygame.display.set_mode((300, 600))
    pygame.display.set_caption('Tetris')
    clock = pygame.time.Clock()
    game = TetrisGame(screen)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            game.handle_event(event)

        game.update()
        game.draw()
        pygame.display.flip()
        clock.tick(60)

if __name__ == '__main__':
    main()
