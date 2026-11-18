import os
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame
import main


class AutomationTests(unittest.TestCase):
    def setUp(self):
        # Создаёт новую игру перед каждым тестом.
        self.game = main.Game()

    def tearDown(self):
        # Завершает работу Pygame после каждого теста.
        pygame.quit()

    def click(self, button=1):
        # Имитирует нажатие указанной кнопки мыши на первую клетку поля.
        event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=button, pos=(50, 80)
        )
        self.game.handle_event(event)

    def test_select_and_plant(self):
        # Проверяет выбор цветка клавишами 1–3 и его посадку щелчком мыши.
        cases = [
            (pygame.K_1, main.RoseShooter, 50),
            (pygame.K_2, main.SunFlower, 75),
            (pygame.K_3, main.EmpoweredFlowerDecorator, 25),
        ]
        for key, flower_type, remaining_sun in cases:
            with self.subTest(key=key):
                self.game.reset_game()
                self.game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key))
                self.click()
                flower = self.game.grid[0][0]
                self.assertIsInstance(flower, flower_type)
                self.assertEqual(self.game.sun, remaining_sun)
                self.assertEqual(list(self.game.plant_group), [flower])

    def test_right_click_ignored(self):
        # Проверяет, что правая кнопка мыши не сажает цветок и не тратит ресурсы.
        self.click(button=3)
        self.assertIsNone(self.game.grid[0][0])
        self.assertEqual(self.game.sun, 100)
        self.assertEqual(list(self.game.plant_group), [])

    def test_repeated_click(self):
        # Проверяет, что повторный щелчок не заменяет цветок и не тратит ресурсы.
        self.click()
        flower = self.game.grid[0][0]
        self.click()
        self.assertIs(self.game.grid[0][0], flower)
        self.assertEqual(self.game.sun, 50)
        self.assertEqual(list(self.game.plant_group), [flower])

    def test_input_after_game_over(self):
        # Проверяет, что после завершения игры выбор и посадка цветка недоступны.
        self.game.game_over = True
        self.game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_2))
        self.click()
        self.assertEqual(self.game.selected_flower, "rose")
        self.assertIsNone(self.game.grid[0][0])
        self.assertEqual(self.game.sun, 100)
        self.assertEqual(list(self.game.plant_group), [])

    def test_reset_game(self):
        # Проверяет очистку поля и восстановление начального состояния игры.
        self.click()
        self.game.spawn_mushroom()
        self.game.projectiles.append(main.Projectile(100, 90, 0, 25))
        self.game.selected_flower = "sunflower"
        self.game.score = 30
        self.game.game_over = True
        self.game.reset_game()
        self.assertTrue(all(cell is None for row in self.game.grid for cell in row))
        self.assertEqual(list(self.game.entities), [])
        self.assertEqual(self.game.projectiles, [])
        self.assertEqual((self.game.sun, self.game.score), (100, 0))
        self.assertEqual(self.game.selected_flower, "rose")
        self.assertFalse(self.game.game_over)


if __name__ == "__main__":
    unittest.main(verbosity=2)
