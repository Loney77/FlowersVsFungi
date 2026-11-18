import os
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame
import main


class WhiteBoxTests(unittest.TestCase):
    def setUp(self):
        # Создаёт новую игру перед каждым тестом.
        self.game = main.Game()
    
    def tearDown(self):
        # Завершает работу Pygame после каждого теста.
        pygame.quit()

    def plant(self, kind="rose", row=0, col=0):
        # Сажает выбранный цветок в указанную клетку и возвращает его.
        self.game.selected_flower = kind
        self.game.try_plant_flower((50 + col * 60, 80 + row * 60))
        return self.game.grid[row][col]


    def test_W02_rose_exact_cost(self):
        # Проверяет посадку розы при точном количестве ресурсов.
        self.game.sun = 50
        flower = self.plant()
        self.assertIsInstance(flower, main.RoseShooter)
        self.assertEqual(self.game.sun, 0)
        self.assertEqual(list(self.game.plant_group), [flower])

    def test_W03_sunflower_exact_cost(self):
        # Проверяет посадку подсолнуха за 25 единиц солнца.
        self.game.sun = 25
        self.assertIsInstance(self.plant("sunflower"), main.SunFlower)
        self.assertEqual(self.game.sun, 0)

    def test_W04_empowered_exact_cost(self):
        # Проверяет стоимость посадки и урон усиленной розы.
        self.game.sun = 75
        flower = self.plant("empowered_rose")
        self.assertIsInstance(flower, main.EmpoweredFlowerDecorator)
        self.assertEqual(flower.damage, 50)
        self.assertEqual(self.game.sun, 0)

    def test_W05_insufficient_resources(self):
        # Проверяет отказ в посадке и сохранение ресурсов при их нехватке.
        for kind, cost in [("rose", 50), ("sunflower", 25), ("empowered_rose", 75)]:
            with self.subTest(kind=kind):
                self.game.sun = cost - 1
                self.assertIsNone(self.plant(kind))
                self.assertEqual(self.game.sun, cost - 1)
                self.assertEqual(list(self.game.plant_group), [])

    def test_W06_occupied_cell(self):
        # Проверяет, что занятую клетку нельзя засадить повторно.
        flower = self.plant()
        self.assertIs(self.plant("sunflower"), flower)
        self.assertEqual(self.game.sun, 50)
        self.assertEqual(list(self.game.plant_group), [flower])

    def test_W07_outside_grid(self):
        # Проверяет, что клики за границами поля не сажают цветы и не тратят ресурсы.
        for pos in [(49, 80), (590, 80), (50, 79), (50, 380)]:
            with self.subTest(pos=pos):
                self.game.try_plant_flower(pos)
                self.assertEqual(self.game.sun, 100)
                self.assertEqual(list(self.game.plant_group), [])

    def test_W08_last_pixel_inside_grid(self):
        # Проверяет посадку в последней допустимой точке поля.
        self.game.try_plant_flower((589, 379))
        self.assertIsInstance(self.game.grid[4][8], main.RoseShooter)
        self.assertEqual(self.game.sun, 50)


if __name__ == "__main__":
    unittest.main(verbosity=2)
