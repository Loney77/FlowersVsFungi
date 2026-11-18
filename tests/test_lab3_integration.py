import os
import unittest
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame
import main


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        # Фиксирует время и создаёт новую игру перед каждым тестом.
        self.time_patch = patch("main.time.time", return_value=1000.0)
        self.time_patch.start()
        self.addCleanup(self.time_patch.stop)
        self.addCleanup(pygame.quit)
        self.game = main.Game()

    def plant(self, kind="rose", col=0):
        # Сажает выбранный цветок в указанном столбце первой строки и возвращает его.
        self.game.selected_flower = kind
        self.game.try_plant_flower((50 + col * 60, 80))
        return self.game.grid[0][col]

    def test_rose_projectile_kills_mushroom(self):
        # Проверяет уничтожение гриба снарядом розы и начисление очков.
        flower = self.plant()
        mushroom = main.Mushroom(0, health=25)
        mushroom.x = 200
        self.game.mushroom_group.add(mushroom)
        self.game.update()
        self.assertEqual(len(self.game.projectiles), 1)
        self.assertEqual(self.game.projectiles[0].damage, flower.damage)
        for _ in range(40):
            self.game.update()
            if not mushroom.is_alive:
                break
        self.assertFalse(mushroom.is_alive)
        self.assertEqual(mushroom.health, 0)
        self.assertEqual(self.game.score, 10)
        self.assertEqual(list(self.game.mushroom_group), [])
        self.assertEqual(self.game.projectiles, [])

    def test_empowered_damage_reaches_projectile(self):
        # Проверяет, что снаряд усиленной розы наносит 50 урона и уничтожает гриб.
        flower = self.plant("empowered_rose")
        mushroom = main.Mushroom(0, health=50)
        mushroom.x = 120
        self.game.mushroom_group.add(mushroom)
        self.game.update()
        self.assertEqual(flower.damage, 50)
        self.assertEqual(mushroom.health, 0)
        self.assertFalse(mushroom.is_alive)
        self.assertEqual(self.game.score, 10)
        self.assertEqual(self.game.projectiles, [])
        self.assertEqual(list(self.game.mushroom_group), [])

    def test_other_row_does_not_trigger_shooting(self):
        # Проверяет, что гриб в другой строке не вызывает стрельбу розы.
        self.plant()
        mushroom = main.Mushroom(1)
        mushroom.x = 200
        self.game.mushroom_group.add(mushroom)
        self.game.update()
        self.assertEqual(self.game.projectiles, [])
        self.assertEqual(mushroom.health, 100)
        self.assertEqual(self.game.score, 0)

    def test_generated_sun_can_be_spent(self):
        # Проверяет, что солнце от подсолнуха можно потратить на новый цветок.
        sunflower = self.plant("sunflower")
        self.plant("empowered_rose", col=1)
        self.assertEqual(self.game.sun, 0)
        sunflower.resource_gen_time = 994.0
        self.game.update()
        self.assertEqual(self.game.sun, 25)
        new_flower = self.plant("sunflower", col=2)
        self.assertIsInstance(new_flower, main.SunFlower)
        self.assertEqual(self.game.sun, 0)
        self.assertEqual(len(list(self.game.plant_group)), 3)

    def test_eaten_flower_frees_cell_for_planting(self):
        # Проверяет, что после поедания цветка клетка освобождается для новой посадки.
        flower = self.plant()
        flower.health = 0.5
        mushroom = main.Mushroom(0)
        mushroom.x = flower.x
        self.game.mushroom_group.add(mushroom)
        self.game.update()
        self.assertTrue(mushroom.is_eating)
        self.assertFalse(flower.is_alive)
        self.assertIsNone(self.game.grid[0][0])
        self.assertEqual(list(self.game.plant_group), [])
        new_flower = self.plant()
        self.assertIsInstance(new_flower, main.RoseShooter)
        self.assertIsNot(new_flower, flower)
        self.assertEqual(list(self.game.plant_group), [new_flower])
        self.assertEqual(self.game.sun, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
