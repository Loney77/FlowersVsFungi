import pygame
import random
import time
import copy
from pathlib import Path

# Константы
WIDTH, HEIGHT = 800, 600
FPS = 60
GRID_ROWS, GRID_COLS = 5, 9
CELL_SIZE = 60
GRID_OFFSET_X, GRID_OFFSET_Y = 50, 80

# Цвета
BCKGRND = (10, 70, 10)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (34, 150, 34)
BROWN = (139, 69, 19)
RED = (220, 20, 60)
YELLOW = (255, 215, 0)
GRAY = (169, 169, 169)

TEXTURES_DIR = Path(__file__).resolve().parent / "textures"


class TextureLoader:
    """Целевой интерфейс загрузки текстур для игровых объектов."""
    def load_texture(self, filename, size):
        raise NotImplementedError


class PygameTextureAdapter(TextureLoader):
    """Адаптирует API загрузки и масштабирования изображений Pygame."""
    def __init__(self, assets_dir):
        self.assets_dir = assets_dir

    def load_texture(self, filename, size):
        image = pygame.image.load(self.assets_dir / filename).convert_alpha()
        return pygame.transform.scale(image, size)


TEXTURE_LOADER = PygameTextureAdapter(TEXTURES_DIR)


class TextureFlyweightFactory:
    """Кэширует общие текстуры и переиспользует их между сущностями."""
    def __init__(self, loader):
        self.loader = loader
        self._textures = {}

    def get_texture(self, filename, size):
        key = (filename, tuple(size))
        if key not in self._textures:
            self._textures[key] = self.loader.load_texture(filename, size)
        return self._textures[key]


TEXTURE_FLYWEIGHTS = TextureFlyweightFactory(TEXTURE_LOADER)


class Renderer:
    """Реализация отрисовки, отделённая от игровых сущностей."""
    def draw_entity(self, screen, entity):
        raise NotImplementedError


class PygameRenderer(Renderer):
    """Рисует игровые сущности средствами Pygame."""
    def draw_entity(self, screen, entity):
        if entity.texture is not None:
            screen.blit(entity.texture, entity.get_rect())
        else:
            pygame.draw.rect(screen, entity.color, entity.get_rect())
            pygame.draw.rect(screen, BLACK, entity.get_rect(), 2)


# БАЗОВЫЕ СУЩНОСТИ

class EntityComponent:
    """Общий интерфейс для одиночных сущностей и групп сущностей."""
    def draw(self, screen):
        raise NotImplementedError


class Entity(EntityComponent):
    """Базовый класс для всех объектов в игре."""
    def __init__(self, x, y, width, height, color, health=100, renderer=None):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.color = color
        self.health = health
        self.is_alive = True
        self.texture = None
        self.renderer = renderer or PygameRenderer()

    def get_rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def take_damage(self, amount):
        self.health -= amount
        if self.health <= 0:
            self.is_alive = False

    def update(self):
        pass # Переопределяется в наследниках

    def draw(self, screen):
        self.renderer.draw_entity(screen, self)


class EntityGroup(EntityComponent):
    """Компоновщик: объединяет сущности и другие группы в одно дерево."""
    def __init__(self):
        self.children = []

    def add(self, component):
        self.children.append(component)

    def __iter__(self):
        for child in self.children:
            if isinstance(child, EntityGroup):
                yield from child
            else:
                yield child

    def draw(self, screen):
        for child in self.children:
            child.draw(screen)

    def remove_dead(self):
        remaining = []
        for child in self.children:
            if isinstance(child, EntityGroup):
                child.remove_dead()
                remaining.append(child)
            elif child.is_alive:
                remaining.append(child)
        self.children = remaining



# ЦВЕТЫ (Защитники)

class Flower(Entity):
    """Базовый класс для цветов."""
    def __init__(self, row, col, damage=20, shoot_cooldown=1.5, renderer=None):
        x = GRID_OFFSET_X + col * CELL_SIZE + 5
        y = GRID_OFFSET_Y + row * CELL_SIZE + 5
        super().__init__(x, y, CELL_SIZE - 10, CELL_SIZE - 10, GREEN, health=150, renderer=renderer)
        self.row = row
        self.col = col
        self.damage = damage
        self.shoot_cooldown = shoot_cooldown
        self.last_shot_time = 0

    def can_shoot(self, current_time):
        return current_time - self.last_shot_time >= self.shoot_cooldown

    def update(self, current_time, projectiles):
        # Логика стрельбы будет добавлена в Game, чтобы не связывать классы напрямую
        pass


class RoseShooter(Flower):
    """Базовый атакующий цветок."""
    def __init__(self, row, col, renderer=None):
        super().__init__(row, col, damage=25, shoot_cooldown=1.2, renderer=renderer)
        self.color = (255, 105, 180) # Розовый
        self.texture = TEXTURE_FLYWEIGHTS.get_texture("rose.png", (self.width, self.height))


class SunFlower(Flower):
    """Цветок для генерации ресурсов (очков/солнца)."""
    def __init__(self, row, col, renderer=None):
        super().__init__(row, col, damage=0, shoot_cooldown=5.0, renderer=renderer)
        self.color = YELLOW
        self.resource_gen_time = 0
        self.texture = TEXTURE_FLYWEIGHTS.get_texture("sunflower.png", (self.width, self.height))



# ГРИБЫ (Атакующие)

class Mushroom(Entity):
    """Базовый класс для грибов."""
    def __init__(self, row, speed=1.0, health=100, renderer=None):
        x = WIDTH
        y = GRID_OFFSET_Y + row * CELL_SIZE + 5
        super().__init__(x, y, CELL_SIZE - 10, CELL_SIZE - 10, BROWN, health, renderer=renderer)
        self.row = row
        self.speed = speed
        self.damage = 10
        self.is_eating = False
        self.texture = TEXTURE_FLYWEIGHTS.get_texture("shroom.png", (self.width, self.height))

    def update(self):
        self.x -= self.speed

    def clone(self, row):
        """Создаёт нового гриба на основе настроенного экземпляра-прототипа."""
        mushroom = copy.copy(self)
        mushroom.row = row
        mushroom.x = WIDTH
        mushroom.y = GRID_OFFSET_Y + row * CELL_SIZE + 5
        mushroom.health = self.health
        mushroom.is_alive = True
        mushroom.is_eating = False
        return mushroom

class BasicMushroom(Mushroom):
    def __init__(self, row):
        super().__init__(row, speed=0.8, health=100)

class FastMushroom(Mushroom):
    def __init__(self, row):
        super().__init__(row, speed=1.8, health=60)
        self.color = (100, 50, 20)


class MushroomBuilder:
    """Строитель, который пошагово настраивает характеристики гриба."""
    def __init__(self, row, renderer=None):
        self.row = row
        self.speed = 0.8
        self.health = 100
        self.color = BROWN
        self.renderer = renderer

    def fast(self):
        self.speed = 1.8
        self.health = 60
        self.color = (100, 50, 20)
        return self

    def build(self):
        mushroom = Mushroom(
            self.row,
            speed=self.speed,
            health=self.health,
            renderer=self.renderer,
        )
        mushroom.color = self.color
        return mushroom


class PlantFactory:
    """Абстрактная фабрика для создания семейства игровых растений."""
    def create_attacker(self, row, col):
        raise NotImplementedError

    def create_resource_generator(self, row, col):
        raise NotImplementedError


class GardenPlantFactory(PlantFactory):
    """Конкретная фабрика стандартных растений сада."""
    def __init__(self, renderer):
        self.renderer = renderer

    def create_attacker(self, row, col):
        return RoseShooter(row, col, renderer=self.renderer)

    def create_resource_generator(self, row, col):
        return SunFlower(row, col, renderer=self.renderer)


class FlowerDecorator(Flower):
    """Базовая обёртка, сохраняющая интерфейс цветка."""
    def __init__(self, flower):
        object.__setattr__(self, "_flower", flower)

    def __getattr__(self, name):
        return getattr(self._flower, name)

    def __setattr__(self, name, value):
        if name == "_flower":
            object.__setattr__(self, name, value)
        else:
            setattr(self._flower, name, value)

    def draw(self, screen):
        self._flower.draw(screen)

    def update(self, current_time, projectiles):
        self._flower.update(current_time, projectiles)


class EmpoweredFlowerDecorator(FlowerDecorator):
    """Увеличивает урон розы, не меняя класс исходного растения."""
    @property
    def damage(self):
        return self._flower.damage * 2

    def draw(self, screen):
        self._flower.draw(screen)
        rect = self._flower.get_rect()
        pygame.draw.rect(
            screen,
            (255, 215, 0),
            rect.inflate(8, 8),
            width=3,
            border_radius=9,
        )



# СНАРЯДЫ
class Projectile(Entity):
    def __init__(self, x, y, row, damage, speed=5, renderer=None):
        super().__init__(x, y, 15, 15, RED, health=1, renderer=renderer)
        self.row = row
        self.damage = damage
        self.speed = speed

    def update(self):
        self.x += self.speed
        if self.x > WIDTH:
            self.is_alive = False


# ИГРОВОЙ МЕНЕДЖЕР 

class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Цветы против Грибов")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arial", 24)
        self.renderer = PygameRenderer()
        self.plant_factory = GardenPlantFactory(self.renderer)
        
        self.reset_game()

    def reset_game(self):
        self.grid = [[None for _ in range(GRID_COLS)] for _ in range(GRID_ROWS)]
        self.entities = EntityGroup()
        self.plant_group = EntityGroup()
        self.mushroom_group = EntityGroup()
        self.entities.add(self.plant_group)
        self.entities.add(self.mushroom_group)
        self.projectiles = []
        self.score = 0
        self.sun = 100
        self.selected_flower = "rose"
        self.game_over = False
        self.last_spawn_time = time.time()
        self.spawn_interval = 3.0
        # Прототипы хранят настройки обычного и быстрого грибов.
        self.mushroom_prototypes = [
            MushroomBuilder(0, renderer=self.renderer).build(),
            MushroomBuilder(0, renderer=self.renderer).fast().build(),
        ]

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and not self.game_over:
            if event.button == 1:
                self.try_plant_flower(event.pos)

        if event.type == pygame.KEYDOWN and not self.game_over:
            if event.key == pygame.K_1:
                self.selected_flower = "rose"
            elif event.key == pygame.K_2:
                self.selected_flower = "sunflower"
            elif event.key == pygame.K_3:
                self.selected_flower = "empowered_rose"

    def try_plant_flower(self, pos):
        mx, my = pos
        col = (mx - GRID_OFFSET_X) // CELL_SIZE
        row = (my - GRID_OFFSET_Y) // CELL_SIZE
        
        if 0 <= row < GRID_ROWS and 0 <= col < GRID_COLS:
            if self.grid[row][col] is None:
                cost = {
                    "rose": 50,
                    "sunflower": 25,
                    "empowered_rose": 75,
                }[self.selected_flower]
                if self.sun < cost:
                    return

                if self.selected_flower == "rose":
                    new_flower = self.plant_factory.create_attacker(row, col)
                elif self.selected_flower == "sunflower":
                    new_flower = self.plant_factory.create_resource_generator(row, col)
                else:
                    rose = self.plant_factory.create_attacker(row, col)
                    new_flower = EmpoweredFlowerDecorator(rose)
                self.sun -= cost
                self.grid[row][col] = new_flower
                self.plant_group.add(new_flower)

    def spawn_mushroom(self):
        row = random.randint(0, GRID_ROWS - 1)
        prototype = random.choice(self.mushroom_prototypes)
        self.mushroom_group.add(prototype.clone(row))

    def update(self):
        if self.game_over:
            return

        current_time = time.time()
        
        # Спавн грибов
        if current_time - self.last_spawn_time >= self.spawn_interval:
            self.spawn_mushroom()
            self.last_spawn_time = current_time
            self.spawn_interval = max(1.0, self.spawn_interval - 0.05) # Усложнение

        # Обновление сущностей
        for entity in self.entities:
            if isinstance(entity, Flower):
                entity.update(current_time, self.projectiles)
                if isinstance(entity, SunFlower) and current_time - entity.resource_gen_time >= 6:
                    self.sun += 25
                    entity.resource_gen_time = current_time
            elif not isinstance(entity, Mushroom):
                entity.update()
            
            # Стрельба цветов
            if isinstance(entity, Flower) and entity.damage > 0 and entity.can_shoot(current_time):
                # Проверяем, есть ли гриб на этой линии
                has_target = any(isinstance(e, Mushroom) and e.row == entity.row and e.x > entity.x for e in self.entities)
                if has_target:
                    proj = Projectile(
                        entity.x + entity.width,
                        entity.y + entity.height // 2,
                        entity.row,
                        entity.damage,
                        renderer=self.renderer,
                    )
                    self.projectiles.append(proj)
                    entity.last_shot_time = current_time

            # Движение и поедание грибов
            if isinstance(entity, Mushroom):
                # Проверка столкновения с цветком
                current_col = int((entity.x - GRID_OFFSET_X) // CELL_SIZE)
                flower_in_cell = self.grid[entity.row][current_col] if 0 <= current_col < GRID_COLS else None
                if flower_in_cell and entity.get_rect().colliderect(flower_in_cell.get_rect()):
                    entity.is_eating = True
                    flower_in_cell.take_damage(0.5) # Гриб ест цветок
                    if not flower_in_cell.is_alive:
                        self.grid[entity.row][current_col] = None
                else:
                    entity.is_eating = False
                    entity.update()

                # Проверка проигрыша
                if entity.x < GRID_OFFSET_X:
                    self.game_over = True

        # Обновление снарядов
        for proj in self.projectiles:
            proj.update()

        # Коллизии снарядов и грибов
        for proj in self.projectiles:
            if not proj.is_alive: continue
            for entity in self.entities:
                if isinstance(entity, Mushroom) and entity.row == proj.row:
                    if proj.get_rect().colliderect(entity.get_rect()):
                        entity.take_damage(proj.damage)
                        proj.is_alive = False
                        if not entity.is_alive:
                            self.score += 10
                        break

        # Очистка мертвых
        self.entities.remove_dead()
        self.projectiles = [p for p in self.projectiles if p.is_alive]

    def draw(self):
        self.screen.fill(BCKGRND)
        
        # Сетка
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                rect = pygame.Rect(GRID_OFFSET_X + c * CELL_SIZE, GRID_OFFSET_Y + r * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                pygame.draw.rect(self.screen, GRAY, rect, 1)

        # Сущности
        self.entities.draw(self.screen)
        for proj in self.projectiles:
            proj.draw(self.screen)

        # UI
        score_text = self.font.render(f"Очки: {self.score}", True, BLACK)
        self.screen.blit(score_text, (10, 10))
        sun_text = self.font.render(f"Солнце: {self.sun}", True, BLACK)
        self.screen.blit(sun_text, (150, 10))
        controls_y = GRID_OFFSET_Y + GRID_ROWS * CELL_SIZE + 8
        rose_marker = "> " if self.selected_flower == "rose" else "  "
        sunflower_marker = "> " if self.selected_flower == "sunflower" else "  "
        empowered_marker = "> " if self.selected_flower == "empowered_rose" else "  "
        controls = [
            f"{rose_marker}1 — Роза (50 солнца)",
            f"{sunflower_marker}2 — Подсолнух (25 солнца)",
            f"{empowered_marker}3 — Усиленная роза (75 солнца)",
        ]
        for index, label in enumerate(controls):
            option_text = self.font.render(label, True, BLACK)
            self.screen.blit(option_text, (GRID_OFFSET_X, controls_y + index * 28))

        if self.game_over:
            go_text = self.font.render("GAME OVER! Грибы прорвались. Нажмите R для рестарта.", True, RED)
            self.screen.blit(go_text, (WIDTH//2 - 250, HEIGHT//2))

        pygame.display.flip()

class GameFacade:
    """Упрощённый интерфейс запуска игрового цикла."""
    def __init__(self, game=None):
        self.game = game or Game()

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    break
                self.game.handle_event(event)

            if not running:
                break

            keys = pygame.key.get_pressed()
            if keys[pygame.K_r] and self.game.game_over:
                self.game.reset_game()

            self.game.update()
            self.game.draw()
            self.game.clock.tick(FPS)

        pygame.quit()


if __name__ == "__main__":
    GameFacade().run()
