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


class EntityIterator:
    """Обходит дерево групп в глубину и возвращает отдельные сущности."""
    def __init__(self, group):
        self._stack = [iter(group.children)]

    def __iter__(self):
        return self

    def __next__(self):
        while self._stack:
            try:
                child = next(self._stack[-1])
            except StopIteration:
                self._stack.pop()
                continue

            if isinstance(child, EntityGroup):
                self._stack.append(iter(child.children))
            else:
                return child
        raise StopIteration


class EntityGroup(EntityComponent):
    """Компоновщик: объединяет сущности и другие группы в одно дерево."""
    def __init__(self):
        self.children = []

    def add(self, component):
        self.children.append(component)

    def __iter__(self):
        return EntityIterator(self)

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


class PlantingService:
    """Общий интерфейс для выполнения посадки растения."""
    def place(self, pos, plant_type):
        raise NotImplementedError


class GardenPlantingService(PlantingService):
    """Создаёт растение и размещает его на игровом поле."""
    def __init__(self, game):
        self.game = game

    def place(self, pos, plant_type):
        mx, my = pos
        col = (mx - GRID_OFFSET_X) // CELL_SIZE
        row = (my - GRID_OFFSET_Y) // CELL_SIZE
        if plant_type == "rose":
            plant = self.game.plant_factory.create_attacker(row, col)
        elif plant_type == "sunflower":
            plant = self.game.plant_factory.create_resource_generator(row, col)
        elif plant_type == "empowered_rose":
            rose = self.game.plant_factory.create_attacker(row, col)
            plant = EmpoweredFlowerDecorator(rose)
        else:
            return False

        self.game.grid[row][col] = plant
        self.game.plant_group.add(plant)
        return True


class PlantingRequest:
    """Данные одной попытки посадки, передаваемые по цепочке проверок."""
    def __init__(self, pos, plant_type):
        self.pos = tuple(pos)
        self.plant_type = plant_type
        self.col = (self.pos[0] - GRID_OFFSET_X) // CELL_SIZE
        self.row = (self.pos[1] - GRID_OFFSET_Y) // CELL_SIZE
        self.cost = 0


class PlantingHandler:
    """Проверяет своё условие и передаёт допустимый запрос дальше."""
    def __init__(self, game):
        self.game = game
        self._next = None

    def set_next(self, handler):
        self._next = handler
        return handler

    def handle(self, request):
        if not self.check(request):
            return False
        if self._next is not None:
            return self._next.handle(request)
        return True

    def check(self, request):
        raise NotImplementedError


class GameStateHandler(PlantingHandler):
    def check(self, request):
        return not self.game.game_over


class BoundsHandler(PlantingHandler):
    def check(self, request):
        return (0 <= request.row < GRID_ROWS
                and 0 <= request.col < GRID_COLS)


class EmptyCellHandler(PlantingHandler):
    def check(self, request):
        return self.game.grid[request.row][request.col] is None


class SunBalanceHandler(PlantingHandler):
    def __init__(self, game, costs):
        super().__init__(game)
        self.costs = costs

    def check(self, request):
        cost = self.costs.get(request.plant_type)
        if cost is None or self.game.sun < cost:
            return False
        request.cost = cost
        return True


class PlantingProxy(PlantingService):
    """Контролирует доступ к посадке через цепочку игровых проверок."""
    COSTS = {"rose": 50, "sunflower": 25, "empowered_rose": 75}

    def __init__(self, game, service):
        self.game = game
        self.service = service
        self.validation_chain = GameStateHandler(game)
        self.validation_chain.set_next(BoundsHandler(game)).set_next(
            EmptyCellHandler(game)
        ).set_next(SunBalanceHandler(game, self.COSTS))

    def place(self, pos, plant_type):
        request = PlantingRequest(pos, plant_type)
        if not self.validation_chain.handle(request):
            return False
        if not self.service.place(request.pos, request.plant_type):
            return False
        self.game.sun -= request.cost
        return True


class Command:
    """Общий интерфейс игровых команд."""
    def execute(self):
        raise NotImplementedError


class PlantFlowerCommand(Command):
    """Хранит получателя и параметры одного запроса посадки."""
    def __init__(self, planting_service, pos, plant_type):
        self.planting_service = planting_service
        self.pos = tuple(pos)
        self.plant_type = plant_type

    def execute(self):
        return self.planting_service.place(self.pos, self.plant_type)


class CommandInvoker:
    """Запускает игровые действия через общий интерфейс команд."""
    def execute(self, command):
        return command.execute()


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


class CombatMediator:
    """Интерфейс координации взаимодействий участников боя."""
    def update(self, current_time):
        raise NotImplementedError


class GardenCombatMediator(CombatMediator):
    """Согласует стрельбу, генерацию солнца, поедание и попадания."""
    def __init__(self, game):
        self.game = game

    def update(self, current_time):
        # Обновление сущностей
        for entity in self.game.entities:
            if isinstance(entity, Flower):
                entity.update(current_time, self.game.projectiles)
                if isinstance(entity, SunFlower) and current_time - entity.resource_gen_time >= 6:
                    self.game.sun += 25
                    entity.resource_gen_time = current_time
            elif not isinstance(entity, Mushroom):
                entity.update()
            
            # Стрельба цветов
            if isinstance(entity, Flower) and entity.damage > 0 and entity.can_shoot(current_time):
                # Проверяем, есть ли гриб на этой линии
                has_target = any(isinstance(e, Mushroom) and e.row == entity.row and e.x > entity.x for e in self.game.entities)
                if has_target:
                    proj = Projectile(
                        entity.x + entity.width,
                        entity.y + entity.height // 2,
                        entity.row,
                        entity.damage,
                        renderer=self.game.renderer,
                    )
                    self.game.projectiles.append(proj)
                    entity.last_shot_time = current_time

            # Движение и поедание грибов
            if isinstance(entity, Mushroom):
                # Проверка столкновения с цветком
                current_col = int((entity.x - GRID_OFFSET_X) // CELL_SIZE)
                flower_in_cell = self.game.grid[entity.row][current_col] if 0 <= current_col < GRID_COLS else None
                if flower_in_cell and entity.get_rect().colliderect(flower_in_cell.get_rect()):
                    entity.is_eating = True
                    flower_in_cell.take_damage(0.5) # Гриб ест цветок
                    if not flower_in_cell.is_alive:
                        self.game.grid[entity.row][current_col] = None
                else:
                    entity.is_eating = False
                    entity.update()

                # Проверка проигрыша
                if entity.x < GRID_OFFSET_X:
                    self.game.set_state(GameOverState())

        # Обновление снарядов
        for proj in self.game.projectiles:
            proj.update()

        # Коллизии снарядов и грибов
        for proj in self.game.projectiles:
            if not proj.is_alive: continue
            for entity in self.game.entities:
                if isinstance(entity, Mushroom) and entity.row == proj.row:
                    if proj.get_rect().colliderect(entity.get_rect()):
                        entity.take_damage(proj.damage)
                        proj.is_alive = False
                        if not entity.is_alive:
                            self.game.score += 10
                        break


class GameSnapshot:
    """Хранит независимую копию игрового состояния в памяти."""
    def __init__(self, state):
        self.__state = self._copy_state(state)

    @staticmethod
    def _copy_entity(entity):
        if isinstance(entity, FlowerDecorator):
            return type(entity)(GameSnapshot._copy_entity(entity._flower))
        # Координаты и характеристики копируются, текстура и renderer общие.
        return copy.copy(entity)

    @classmethod
    def _copy_state(cls, state):
        result = dict(state)
        for key in ("plants", "mushrooms", "projectiles", "prototypes"):
            result[key] = [cls._copy_entity(e) for e in state[key]]
        return result

    def get_state(self):
        # Каждое восстановление получает новые экземпляры сущностей.
        return self._copy_state(self.__state)


class GameHistory:
    """Хранитель одного снимка; не разбирает его содержимое."""
    def __init__(self, game):
        self.game = game
        self._snapshot = None

    def save(self):
        self._snapshot = self.game.create_snapshot()

    def restore(self):
        if self._snapshot is None:
            return False
        self.game.restore_snapshot(self._snapshot)
        return True


class StatisticsObserver:
    """Интерфейс подписчика на изменения игровых показателей."""
    def update(self, score, sun):
        raise NotImplementedError


class GameStatistics:
    """Издатель: хранит показатели и уведомляет подписчиков об изменениях."""
    def __init__(self):
        self.score = 0
        self.sun = 100
        self._observers = []

    def attach(self, observer):
        if observer not in self._observers:
            self._observers.append(observer)
            observer.update(self.score, self.sun)

    def detach(self, observer):
        if observer in self._observers:
            self._observers.remove(observer)

    def notify(self):
        for observer in tuple(self._observers):
            observer.update(self.score, self.sun)

    def set_score(self, value):
        if self.score != value:
            self.score = value
            self.notify()

    def set_sun(self, value):
        if self.sun != value:
            self.sun = value
            self.notify()

    def reset(self, score=0, sun=100):
        self.score = score
        self.sun = sun
        self.notify()


class StatisticsPanel(StatisticsObserver):
    """Обновляет изображения надписей после уведомления издателя."""
    def __init__(self, font):
        self.font = font
        self.score_text = None
        self.sun_text = None

    def update(self, score, sun):
        self.score_text = self.font.render(f"Очки: {score}", True, BLACK)
        self.sun_text = self.font.render(f"Солнце: {sun}", True, BLACK)

    def draw(self, screen):
        screen.blit(self.score_text, (10, 10))
        screen.blit(self.sun_text, (150, 10))


class GameState:
    """Интерфейс поведения игры в текущем состоянии."""
    is_game_over = False

    def handle_event(self, game, event):
        raise NotImplementedError

    def update(self, game):
        raise NotImplementedError

    def draw_overlay(self, game):
        pass


class PlayingState(GameState):
    def handle_event(self, game, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            game.try_plant_flower(event.pos)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_1:
                game.selected_flower = "rose"
            elif event.key == pygame.K_2:
                game.selected_flower = "sunflower"
            elif event.key == pygame.K_3:
                game.selected_flower = "empowered_rose"

    def update(self, game):
        game.update_playing()


class GameOverState(GameState):
    is_game_over = True

    def handle_event(self, game, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
            game.reset_game()

    def update(self, game):
        pass

    def draw_overlay(self, game):
        text = game.font.render(
            "GAME OVER! Грибы прорвались. Нажмите R для рестарта.", True, RED
        )
        game.screen.blit(text, (WIDTH // 2 - 250, HEIGHT // 2))


# ИГРОВОЙ МЕНЕДЖЕР 

class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Цветы против Грибов")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arial", 24)
        self.statistics = GameStatistics()
        self.statistics_panel = StatisticsPanel(self.font)
        self.statistics.attach(self.statistics_panel)
        self.renderer = PygameRenderer()
        self.plant_factory = GardenPlantFactory(self.renderer)
        self.planting_service = GardenPlantingService(self)
        self.planting_proxy = PlantingProxy(self, self.planting_service)
        self.command_invoker = CommandInvoker()
        self.combat_mediator = GardenCombatMediator(self)
        self.history = GameHistory(self)
        
        self.reset_game()

    @property
    def score(self):
        return self.statistics.score

    @score.setter
    def score(self, value):
        self.statistics.set_score(value)

    @property
    def sun(self):
        return self.statistics.sun

    @sun.setter
    def sun(self, value):
        self.statistics.set_sun(value)

    @property
    def game_over(self):
        return self.state.is_game_over

    @game_over.setter
    def game_over(self, value):
        self.set_state(GameOverState() if value else PlayingState())

    def set_state(self, state):
        self.state = state

    def reset_game(self):
        self.grid = [[None for _ in range(GRID_COLS)] for _ in range(GRID_ROWS)]
        self.entities = EntityGroup()
        self.plant_group = EntityGroup()
        self.mushroom_group = EntityGroup()
        self.entities.add(self.plant_group)
        self.entities.add(self.mushroom_group)
        self.projectiles = []
        self.statistics.reset()
        self.selected_flower = "rose"
        self.set_state(PlayingState())
        self.snapshot_message = ""
        self.last_spawn_time = time.time()
        self.spawn_interval = 3.0
        # Прототипы хранят настройки обычного и быстрого грибов.
        self.mushroom_prototypes = [
            MushroomBuilder(0, renderer=self.renderer).build(),
            MushroomBuilder(0, renderer=self.renderer).fast().build(),
        ]

    def create_snapshot(self):
        return GameSnapshot({
            "plants": list(self.plant_group),
            "mushrooms": list(self.mushroom_group),
            "projectiles": self.projectiles,
            "prototypes": self.mushroom_prototypes,
            "score": self.score,
            "sun": self.sun,
            "selected_flower": self.selected_flower,
            "game_over": self.game_over,
            "last_spawn_time": self.last_spawn_time,
            "spawn_interval": self.spawn_interval,
            "saved_at": time.time(),
            "random_state": random.getstate(),
        })

    def restore_snapshot(self, snapshot):
        state = snapshot.get_state()
        time_shift = time.time() - state["saved_at"]
        self.grid = [[None for _ in range(GRID_COLS)] for _ in range(GRID_ROWS)]
        self.entities = EntityGroup()
        self.plant_group = EntityGroup()
        self.mushroom_group = EntityGroup()
        self.entities.add(self.plant_group)
        self.entities.add(self.mushroom_group)
        for plant in state["plants"]:
            plant.last_shot_time += time_shift
            if isinstance(plant, SunFlower):
                plant.resource_gen_time += time_shift
            self.plant_group.add(plant)
            self.grid[plant.row][plant.col] = plant
        for mushroom in state["mushrooms"]:
            self.mushroom_group.add(mushroom)
        self.projectiles = state["projectiles"]
        self.mushroom_prototypes = state["prototypes"]
        self.statistics.reset(state["score"], state["sun"])
        self.selected_flower = state["selected_flower"]
        self.set_state(GameOverState() if state["game_over"] else PlayingState())
        self.last_spawn_time = state["last_spawn_time"] + time_shift
        self.spawn_interval = state["spawn_interval"]
        random.setstate(state["random_state"])

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F5:
                self.history.save()
                self.snapshot_message = "Снимок сохранён"
                return
            if event.key == pygame.K_F9:
                restored = self.history.restore()
                self.snapshot_message = (
                    "Снимок восстановлен" if restored else "Сначала сохраните снимок (F5)"
                )
                return

        self.state.handle_event(self, event)

    def try_plant_flower(self, pos):
        command = PlantFlowerCommand(
            self.planting_proxy, pos, self.selected_flower
        )
        return self.command_invoker.execute(command)

    def spawn_mushroom(self):
        row = random.randint(0, GRID_ROWS - 1)
        prototype = random.choice(self.mushroom_prototypes)
        self.mushroom_group.add(prototype.clone(row))

    def update(self):
        self.state.update(self)

    def update_playing(self):
        current_time = time.time()
        
        # Спавн грибов
        if current_time - self.last_spawn_time >= self.spawn_interval:
            self.spawn_mushroom()
            self.last_spawn_time = current_time
            self.spawn_interval = max(1.0, self.spawn_interval - 0.05) # Усложнение

        self.combat_mediator.update(current_time)

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
        self.statistics_panel.draw(self.screen)
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

        snapshot_hint = self.font.render("F5 — сохранить, F9 — восстановить", True, WHITE)
        self.screen.blit(snapshot_hint, (GRID_OFFSET_X, controls_y + 94))
        if self.snapshot_message:
            message = self.font.render(self.snapshot_message, True, YELLOW)
            self.screen.blit(message, (GRID_OFFSET_X, controls_y + 122))

        self.state.draw_overlay(self)

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

            self.game.update()
            self.game.draw()
            self.game.clock.tick(FPS)

        pygame.quit()


if __name__ == "__main__":
    GameFacade().run()
