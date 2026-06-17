# -*- coding: utf-8 -*-
"""
КОСМИЧЕСКИЙ БОЙ  /  KOSMIK JANG
Мини-игра для мастер-класса по Python (школьники).

Запуск:   python space_game.py
Нужно:    pip install pygame numpy      (numpy — только для звуков; без него игра тоже работает, но без звука)

Управление:
    ← → ↑ ↓  или  W A S D   — двигать корабль
    ПРОБЕЛ                   — стрелять
    P                       — пауза
    M                       — выйти в главное меню (из паузы / после проигрыша)
    R                       — рейтинг (в главном меню)
    F                       — на весь экран
    ESC                     — назад / выход
"""

import os
import sys
import math
import json
import random

try:
    import pygame
except ImportError:
    print("Нужно установить pygame:   pip install pygame")
    sys.exit(1)

try:
    import numpy as np
    HAS_NUMPY = True
except Exception:
    HAS_NUMPY = False


# ============================================================
#  НАСТРОЙКИ — можно спокойно менять под себя
#  (sozlamalar — o'zgartirish mumkin)
# ============================================================
WIDTH, HEIGHT = 1000, 720      # размер окна (для проектора)
FPS = 60
START_LIVES = 3                # сколько жизней в начале
PLAYER_SPEED = 6.0             # скорость корабля
DIFFICULTY_RAMP = 28.0         # за сколько секунд сложность растёт на +1 (больше число = легче)
MAX_LIVES = 5
TRIPLE_SECONDS = 9             # тройной выстрел
SHIELD_SECONDS = 7             # щит
SLOW_SECONDS = 5               # замедление времени
MAGNET_SECONDS = 7             # магнит для бонусов
DOUBLE_SECONDS = 8             # двойные очки (x2)
# ============================================================

SR = 44100  # частота звука


def _data_dir():
    # .exe / .app ichida yozib bo'ladigan doimiy papka kerak (vaqtinchalik emas)
    if getattr(sys, "frozen", False):
        base = os.path.join(os.path.expanduser("~"), ".mini_oyinlar")
        try:
            os.makedirs(base, exist_ok=True)
            return base
        except Exception:
            return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


HIGHSCORE_FILE = os.path.join(_data_dir(), "highscores.json")
SMOKE = os.environ.get("SMOKE") == "1"  # внутренний авто-тест, обычным игрокам не нужен

# --- Цвета ---
BG_TOP = (8, 10, 32)
BG_BOTTOM = (26, 12, 50)
WHITE = (240, 245, 255)
CYAN = (80, 220, 255)
YELLOW = (255, 224, 90)
ORANGE = (255, 150, 50)
RED = (255, 80, 80)
GREEN = (110, 240, 140)
PINK = (255, 120, 180)
PURPLE = (185, 105, 235)
GREY = (155, 160, 175)
GOLD = (255, 210, 70)
ICE_BLUE = (150, 210, 255)
MAGNET_RED = (255, 90, 90)
BOMB_ORANGE = (255, 120, 60)
EXPLOSION_COLORS = [(255, 230, 120), (255, 160, 60), (255, 90, 60), (255, 255, 255)]

POWERUP_COLORS = {
    "triple": GREEN, "shield": CYAN, "life": PINK,
    "bomb": BOMB_ORANGE, "slow": ICE_BLUE, "magnet": MAGNET_RED, "double": GOLD,
}


# ============================================================
#  Шрифты + вспомогательные функции рисования
# ============================================================
def get_font(size, bold=False):
    try:
        f = pygame.font.SysFont(
            "dejavusans,arial,verdana,tahoma,liberationsans,notosans,segoeui",
            size, bold=bold)
        if f is None:
            raise RuntimeError("no sysfont")
        return f
    except Exception:
        return pygame.font.Font(None, size)


def draw_text(surf, text, font, color, center=None, topleft=None,
              midtop=None, shadow=True):
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center:
        rect.center = center
    elif topleft:
        rect.topleft = topleft
    elif midtop:
        rect.midtop = midtop
    if shadow:
        sh = font.render(text, True, (0, 0, 0))
        surf.blit(sh, (rect.x + 2, rect.y + 2))
    surf.blit(img, rect)
    return rect


def draw_mini_ship(surf, cx, cy):
    body = [(cx, cy - 11), (cx - 9, cy + 8), (cx, cy + 3), (cx + 9, cy + 8)]
    pygame.draw.polygon(surf, CYAN, body)
    pygame.draw.polygon(surf, WHITE, body, 1)


def star_points(cx, cy, outer, inner, n=5, rot=-math.pi / 2):
    pts = []
    for i in range(n * 2):
        r = outer if i % 2 == 0 else inner
        a = rot + i * math.pi / n
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return pts


# ============================================================
#  Звуки (генерируются кодом; если что-то не так — игра молчит, но работает)
# ============================================================
class DummySound:
    def play(self, *a, **k):
        return None


def _to_sound(mono):
    mono = np.clip(mono, -1.0, 1.0)
    samples = (mono * 32767).astype(np.int16)
    stereo = np.ascontiguousarray(np.column_stack([samples, samples]))
    return pygame.sndarray.make_sound(stereo)


def _tone(freq, dur, vol=0.4, kind="sine", sweep=None, attack=0.005, release=0.06):
    n = max(1, int(SR * dur))
    if sweep is None:
        t = np.arange(n) / SR
        phase = 2 * np.pi * freq * t
    else:
        f = np.linspace(freq, sweep, n)
        phase = 2 * np.pi * np.cumsum(f) / SR
    if kind == "square":
        w = np.sign(np.sin(phase))
    elif kind == "noise":
        w = np.random.uniform(-1, 1, n)
    else:
        w = np.sin(phase)
    env = np.ones(n)
    a = max(1, int(SR * attack))
    r = max(1, int(SR * release))
    env[:a] = np.linspace(0, 1, a)
    env[-r:] = np.linspace(1, 0, r)
    return w * env * vol


def _decay_noise(dur, vol=0.4, power=2.0):
    n = max(1, int(SR * dur))
    w = np.random.uniform(-1, 1, n)
    env = (1 - np.arange(n) / n) ** power
    return w * env * vol


def _seq(parts):
    return np.concatenate(parts) if parts else np.zeros(1)


def make_sounds():
    keys = ["shoot", "explosion", "big_explosion", "powerup",
            "hit", "enemy_shoot", "gameover", "bomb"]
    sounds = {k: DummySound() for k in keys}
    if not HAS_NUMPY:
        return sounds

    def safe(key, fn):
        try:
            sounds[key] = _to_sound(fn())
        except Exception:
            sounds[key] = DummySound()

    safe("shoot", lambda: _tone(820, 0.12, 0.16, "square", sweep=360))
    safe("explosion", lambda: _decay_noise(0.28, 0.30, power=2.2))
    safe("big_explosion", lambda: _decay_noise(0.55, 0.42, power=1.7))
    safe("bomb", lambda: _seq([_decay_noise(0.7, 0.5, power=1.4),
                               _tone(90, 0.4, 0.35, "sine", sweep=40)]))
    safe("powerup", lambda: _seq([_tone(600, 0.08, 0.20),
                                  _tone(820, 0.08, 0.20),
                                  _tone(1100, 0.13, 0.20)]))
    safe("hit", lambda: _tone(320, 0.32, 0.38, "square", sweep=110))
    safe("enemy_shoot", lambda: _tone(440, 0.13, 0.10, "square", sweep=240))
    safe("gameover", lambda: _seq([_tone(440, 0.18, 0.28, "square"),
                                   _tone(360, 0.18, 0.28, "square"),
                                   _tone(300, 0.20, 0.28, "square"),
                                   _tone(200, 0.40, 0.28, "square")]))
    return sounds


# ============================================================
#  Файл рекордов (сохраняется и читается при перезапуске)
# ============================================================
def load_high_scores():
    try:
        with open(HIGHSCORE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        out = []
        for h in data:
            if isinstance(h, dict) and "name" in h and "score" in h:
                out.append({"name": str(h["name"])[:12], "score": int(h["score"])})
        out.sort(key=lambda h: h["score"], reverse=True)
        return out[:10]
    except Exception:
        return []


def save_high_scores(scores):
    try:
        with open(HIGHSCORE_FILE, "w", encoding="utf-8") as f:
            json.dump(scores, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ============================================================
#  Фон (градиент + лёгкие туманности)
# ============================================================
def make_background():
    surf = pygame.Surface((WIDTH, HEIGHT))
    for y in range(HEIGHT):
        t = y / max(1, HEIGHT - 1)
        col = (int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t),
               int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t),
               int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t))
        pygame.draw.line(surf, col, (0, y), (WIDTH, y))
    for _ in range(3):
        blob = pygame.Surface((420, 420), pygame.SRCALPHA)
        col = random.choice([(60, 30, 95, 16), (30, 45, 95, 16), (95, 30, 65, 14)])
        pygame.draw.circle(blob, col, (210, 210), 210)
        surf.blit(blob, (random.randint(-120, WIDTH - 200),
                         random.randint(-120, HEIGHT - 200)))
    return surf


# ============================================================
#  Игровые объекты
# ============================================================
class Star:
    def __init__(self, layer):
        self.layer = layer
        self.reset(random.uniform(0, HEIGHT))

    def reset(self, y=None):
        self.x = random.uniform(0, WIDTH)
        self.y = y if y is not None else -2
        if self.layer == 0:
            self.speed, self.size, self.color = random.uniform(0.4, 0.8), 1, (90, 95, 125)
        elif self.layer == 1:
            self.speed, self.size, self.color = random.uniform(1.0, 1.6), 2, (150, 160, 200)
        else:
            self.speed, self.size, self.color = random.uniform(2.1, 3.1), 2, (225, 235, 255)

    def update(self, dt):
        self.y += self.speed * dt
        if self.y > HEIGHT + 2:
            self.reset(-2)

    def draw(self, surf):
        if self.y < 0 or self.y >= HEIGHT:
            return
        if self.size <= 1:
            surf.set_at((int(self.x) % WIDTH, int(self.y)), self.color)
        else:
            pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), self.size)


class Bullet:
    def __init__(self, x, y, vx, vy, color, radius=4, friendly=True):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.color = color
        self.radius = radius
        self.friendly = friendly
        self.dead = False

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt

    def offscreen(self):
        return self.y < -25 or self.y > HEIGHT + 25 or self.x < -25 or self.x > WIDTH + 25

    def draw(self, surf):
        if self.friendly:
            pygame.draw.line(surf, self.color, (self.x, self.y - 9), (self.x, self.y + 6), 5)
            pygame.draw.line(surf, WHITE, (self.x, self.y - 6), (self.x, self.y + 4), 2)
        else:
            pygame.draw.circle(surf, ORANGE, (int(self.x), int(self.y)), self.radius + 2)
            pygame.draw.circle(surf, RED, (int(self.x), int(self.y)), self.radius)


class Particle:
    def __init__(self, x, y, vx, vy, life, radius, color):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.life = self.max_life = life
        self.radius = radius
        self.color = color

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vx *= 0.96
        self.vy *= 0.96
        self.life -= dt

    def alive(self):
        return self.life > 0

    def draw(self, surf):
        f = max(0.0, self.life / self.max_life)
        r = max(1, int(self.radius * f))
        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), r)


class Asteroid:
    SIZES = {3: 46, 2: 30, 1: 18}
    BASE_SCORE = {3: 25, 2: 50, 1: 75}
    TYPE_MULT = {"normal": 1.0, "metal": 2.0, "explosive": 1.5, "ice": 2.5}

    def __init__(self, x, y, tier, difficulty=1.0, atype="normal"):
        self.tier = tier
        self.atype = atype
        self.radius = self.SIZES[tier]
        self.x, self.y = x, y
        spd = random.uniform(1.3, 2.2) + difficulty * 0.35
        if atype == "ice":
            spd *= 1.15            # лёд быстрее
        elif atype == "metal":
            spd *= 0.85            # металл тяжёлый, медленнее
        self.vx = random.uniform(-1.1, 1.1)
        self.vy = spd
        self.rot = random.uniform(0, 360)
        self.rot_speed = random.uniform(-2.6, 2.6)
        self.hp = tier if atype == "metal" else 1   # металл: 2-3 попадания
        self.max_hp = self.hp
        self.hit_flash = 0
        self.pulse = random.uniform(0, math.tau)
        # форма
        if atype == "ice":
            n, lo, hi = random.randint(6, 8), 0.6, 1.3
        elif atype == "metal":
            n, lo, hi = random.randint(9, 12), 0.9, 1.08
        else:
            n, lo, hi = random.randint(8, 11), 0.78, 1.18
        self.shape = [((i / n) * math.tau, self.radius * random.uniform(lo, hi)) for i in range(n)]
        # цвета
        if atype == "metal":
            self.color, self.outline = (150, 160, 178), (70, 80, 95)
        elif atype == "explosive":
            self.color, self.outline = (170, 60, 50), (90, 25, 20)
        elif atype == "ice":
            self.color, self.outline = ICE_BLUE, (215, 240, 255)
        else:
            base = random.randint(95, 140)
            self.color = (base, max(0, base - 15), max(0, base - 30))
            self.outline = (max(0, base - 45), max(0, base - 55), max(0, base - 65))
        self.craters = ([(random.uniform(-0.4, 0.4) * self.radius,
                          random.uniform(-0.4, 0.4) * self.radius,
                          random.uniform(0.12, 0.22) * self.radius)
                         for _ in range(random.randint(1, 3))]
                        if atype in ("normal", "metal") else [])
        self.rivets = ([(random.uniform(-0.62, 0.62) * self.radius,
                         random.uniform(-0.62, 0.62) * self.radius)
                        for _ in range(random.randint(3, 5))]
                       if atype == "metal" else [])

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.rot += self.rot_speed * dt
        self.pulse += dt
        if self.hit_flash > 0:
            self.hit_flash -= dt
        if self.x < self.radius:
            self.x = self.radius
            self.vx = abs(self.vx)
        elif self.x > WIDTH - self.radius:
            self.x = WIDTH - self.radius
            self.vx = -abs(self.vx)

    def offscreen(self):
        return self.y > HEIGHT + self.radius + 12

    def points(self):
        rad = math.radians(self.rot)
        return [(self.x + math.cos(ang + rad) * rr, self.y + math.sin(ang + rad) * rr)
                for ang, rr in self.shape]

    def draw(self, surf):
        pts = self.points()
        col = self.color
        if self.hit_flash > 0:
            col = (min(255, col[0] + 90), min(255, col[1] + 90), min(255, col[2] + 90))
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, self.outline, pts, 3)
        if self.atype == "metal":
            for cx, cy, cr in self.craters:
                pygame.draw.circle(surf, self.outline, (int(self.x + cx), int(self.y + cy)), int(cr))
            for rx, ry in self.rivets:
                pygame.draw.circle(surf, (210, 220, 235), (int(self.x + rx), int(self.y + ry)), 2)
        elif self.atype == "explosive":
            pr = int(self.radius * 0.4 + 3 * math.sin(self.pulse * 0.25))
            pygame.draw.circle(surf, (255, 160, 40), (int(self.x), int(self.y)), max(3, pr))
            pygame.draw.circle(surf, (255, 240, 120), (int(self.x), int(self.y)), max(1, pr - 4))
        elif self.atype == "ice":
            rad = math.radians(self.rot)
            for ang, rr in self.shape[::2]:
                a = rad + ang
                pygame.draw.line(surf, (225, 245, 255),
                                 (self.x, self.y),
                                 (self.x + math.cos(a) * rr, self.y + math.sin(a) * rr), 1)
        else:
            for cx, cy, cr in self.craters:
                pygame.draw.circle(surf, self.outline, (int(self.x + cx), int(self.y + cy)), int(cr))

    def split(self):
        if self.tier <= 1:
            return []
        kids = []
        for _ in range(2):
            k = Asteroid(self.x, self.y, self.tier - 1, atype=self.atype)
            k.vx = self.vx + random.uniform(-1.6, 1.6)
            k.vy = abs(self.vy) + random.uniform(0.2, 1.0)
            kids.append(k)
        return kids

    def score(self):
        return int(self.BASE_SCORE[self.tier] * self.TYPE_MULT[self.atype])


class Enemy:
    def __init__(self, difficulty=1.0):
        self.radius = 26
        self.base_x = random.uniform(90, WIDTH - 90)
        self.x = self.base_x
        self.y = -40
        self.vy = random.uniform(0.6, 1.0) + difficulty * 0.08
        self.amp = random.uniform(45, 120)
        self.freq = random.uniform(0.01, 0.022)
        self.t = random.uniform(0, 100)
        self.hp = 3
        self.fire_cd = random.uniform(45, 90)
        self.flash = 0
        self.light_t = 0

    def update(self, dt):
        self.t += dt
        self.y += self.vy * dt
        self.x = self.base_x + math.sin(self.t * self.freq * math.tau) * self.amp
        self.x = max(self.radius, min(WIDTH - self.radius, self.x))
        self.fire_cd -= dt
        if self.flash > 0:
            self.flash -= dt
        self.light_t += dt

    def want_fire(self):
        if self.fire_cd <= 0 and 0 < self.y < HEIGHT * 0.6:
            self.fire_cd = random.uniform(55, 110)
            return True
        return False

    def offscreen(self):
        return self.y > HEIGHT + self.radius + 20

    def draw(self, surf):
        cx, cy = int(self.x), int(self.y)
        body_col = WHITE if self.flash > 0 else PURPLE
        dome_col = WHITE if self.flash > 0 else CYAN
        pygame.draw.ellipse(surf, body_col, (cx - self.radius, cy - 6, self.radius * 2, 22))
        pygame.draw.ellipse(surf, (95, 50, 135), (cx - self.radius, cy - 6, self.radius * 2, 22), 3)
        pygame.draw.circle(surf, dome_col, (cx, cy - 6), 12)
        pygame.draw.circle(surf, (30, 120, 170), (cx, cy - 6), 12, 2)
        for i, dx in enumerate((-16, -6, 4, 14)):
            on = (int(self.light_t * 0.2) + i) % 2 == 0
            pygame.draw.circle(surf, YELLOW if on else (120, 90, 40), (cx + dx, cy + 10), 3)

    def hit(self, x, y, r):
        return (x - self.x) ** 2 + (y - self.y) ** 2 <= (self.radius * 0.9 + r) ** 2

    def score(self):
        return 250


class PowerUp:
    def __init__(self, x, y, kind):
        self.x, self.y = x, y
        self.kind = kind
        self.vy = 2.0
        self.t = random.uniform(0, 10)
        self.radius = 16

    def update(self, dt):
        self.t += dt
        self.y += self.vy * dt
        self.x += math.sin(self.t * 0.05) * 0.8 * dt

    def offscreen(self):
        return self.y > HEIGHT + 30

    def color(self):
        return POWERUP_COLORS[self.kind]

    def draw(self, surf):
        cx, cy = int(self.x), int(self.y)
        c = self.color()
        pulse = 2 + int(2 * math.sin(self.t * 0.15))
        pygame.draw.circle(surf, c, (cx, cy), self.radius + pulse)
        pygame.draw.circle(surf, WHITE, (cx, cy), self.radius + pulse, 2)
        pygame.draw.circle(surf, (15, 18, 35), (cx, cy), self.radius - 3)
        k = self.kind
        if k == "triple":
            for dx in (-5, 0, 5):
                pygame.draw.line(surf, c, (cx + dx, cy - 6), (cx + dx, cy + 6), 2)
        elif k == "shield":
            pygame.draw.circle(surf, c, (cx, cy), 7, 2)
            pygame.draw.line(surf, c, (cx, cy - 8), (cx, cy + 8), 2)
        elif k == "life":
            pygame.draw.line(surf, c, (cx - 6, cy), (cx + 6, cy), 3)
            pygame.draw.line(surf, c, (cx, cy - 6), (cx, cy + 6), 3)
        elif k == "double":
            pygame.draw.polygon(surf, c, star_points(cx, cy, 8, 3.5))
        elif k == "slow":  # часы
            pygame.draw.circle(surf, c, (cx, cy), 7, 2)
            pygame.draw.line(surf, c, (cx, cy), (cx, cy - 5), 2)
            pygame.draw.line(surf, c, (cx, cy), (cx + 4, cy + 2), 2)
        elif k == "magnet":  # магнит "U"
            pygame.draw.line(surf, c, (cx - 5, cy - 6), (cx - 5, cy + 3), 3)
            pygame.draw.line(surf, c, (cx + 5, cy - 6), (cx + 5, cy + 3), 3)
            pygame.draw.arc(surf, c, (cx - 6, cy - 2, 12, 11), math.pi, 2 * math.pi, 3)
            pygame.draw.line(surf, WHITE, (cx - 6, cy - 6), (cx - 4, cy - 6), 3)
            pygame.draw.line(surf, WHITE, (cx + 4, cy - 6), (cx + 6, cy - 6), 3)
        elif k == "bomb":
            pygame.draw.circle(surf, c, (cx, cy + 2), 6)
            pygame.draw.line(surf, c, (cx + 4, cy - 4), (cx + 8, cy - 8), 2)
            pygame.draw.circle(surf, YELLOW, (cx + 8, cy - 8), 2)


class Player:
    def __init__(self):
        self.x = WIDTH / 2
        self.y = HEIGHT * 0.8
        self.speed = PLAYER_SPEED
        self.radius = 16          # хитбокс (маленький = прощающий для детей)
        self.cooldown = 0
        self.base_cooldown = 10
        self.lives = START_LIVES
        self.invuln = 100         # защита сразу после старта/попадания
        self.shield = 0
        self.triple = 0
        self.flame = 0
        self.min_y = HEIGHT * 0.42

    def update(self, dt, keys):
        dx = dy = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            dx -= 1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            dx += 1
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            dy -= 1
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            dy += 1
        if dx and dy:
            dx *= 0.7071
            dy *= 0.7071
        self.x += dx * self.speed * dt
        self.y += dy * self.speed * dt
        self.x = max(self.radius + 6, min(WIDTH - self.radius - 6, self.x))
        self.y = max(self.min_y, min(HEIGHT - self.radius - 6, self.y))
        for attr in ("cooldown", "invuln", "shield", "triple"):
            v = getattr(self, attr)
            if v > 0:
                setattr(self, attr, v - dt)
        self.flame += dt

    def can_shoot(self):
        return self.cooldown <= 0

    def shoot(self):
        self.cooldown = self.base_cooldown
        ny = self.y - 24
        if self.triple > 0:
            return [Bullet(self.x, ny, 0, -11, YELLOW),
                    Bullet(self.x - 6, ny + 4, -3.2, -10.4, YELLOW),
                    Bullet(self.x + 6, ny + 4, 3.2, -10.4, YELLOW)]
        return [Bullet(self.x, ny, 0, -11, YELLOW)]

    def draw(self, surf):
        if self.lives <= 0:
            return
        cx, cy = self.x, self.y
        visible = not (self.invuln > 0 and int(self.invuln * 0.2) % 2 == 0)
        if visible:
            flame_len = 10 + (math.sin(self.flame * 0.6) + 1) * 5
            pygame.draw.polygon(surf, ORANGE,
                                [(cx - 7, cy + 10), (cx + 7, cy + 10), (cx, cy + 10 + flame_len)])
            pygame.draw.polygon(surf, YELLOW,
                                [(cx - 4, cy + 10), (cx + 4, cy + 10), (cx, cy + 10 + flame_len * 0.6)])
            body = [(cx, cy - 24), (cx - 9, cy - 4), (cx - 22, cy + 16), (cx - 8, cy + 10),
                    (cx + 8, cy + 10), (cx + 22, cy + 16), (cx + 9, cy - 4)]
            pygame.draw.polygon(surf, CYAN, body)
            pygame.draw.polygon(surf, WHITE, body, 2)
            pygame.draw.circle(surf, (200, 240, 255), (int(cx), int(cy - 6)), 5)
        if self.shield > 0:
            blink = self.shield < 60 and int(self.shield * 0.3) % 2 == 0
            if not blink:
                r = 33 + int(3 * math.sin(self.flame * 0.3))
                tmp = pygame.Surface((2 * r + 6, 2 * r + 6), pygame.SRCALPHA)
                pygame.draw.circle(tmp, (80, 220, 255, 70), (r + 3, r + 3), r)
                pygame.draw.circle(tmp, (170, 250, 255, 200), (r + 3, r + 3), r, 3)
                surf.blit(tmp, (int(cx) - r - 3, int(cy) - r - 3))


# ============================================================
#  Главный класс игры
# ============================================================
class Game:
    def __init__(self, sounds, fonts):
        self.sounds = sounds
        self.fonts = fonts
        self.bg = make_background()
        self.canvas = pygame.Surface((WIDTH, HEIGHT))
        self.stars = []
        for layer, count in enumerate((50, 35, 22)):
            self.stars += [Star(layer) for _ in range(count)]
        self.high_scores = load_high_scores()
        self.state = "menu"
        self.shake = 0
        self.name_input = ""
        self.last_rank = None
        self.reset()

    def reset(self):
        self.player = Player()
        self.bullets = []
        self.enemy_bullets = []
        self.asteroids = []
        self.enemies = []
        self.powerups = []
        self.particles = []
        self.score = 0
        self.combo = 1
        self.combo_timer = 0
        self.elapsed = 0.0
        self.ast_timer = 60
        self.enemy_timer = 60 * 12
        self.shake = 0
        self.difficulty = 1.0
        self.last_rank = None
        self.slow_timer = 0
        self.magnet_timer = 0
        self.double_timer = 0
        self.flash_timer = 0
        for _ in range(3):
            self.asteroids.append(Asteroid(random.uniform(60, WIDTH - 60),
                                           random.uniform(-200, -40),
                                           random.choice([3, 2, 2])))

    def start(self):
        self.reset()
        self.state = "playing"

    def best(self):
        return self.high_scores[0] if self.high_scores else None

    # ---------- помощники ----------
    def add_score(self, base):
        mult = self.combo * (2 if self.double_timer > 0 else 1)
        self.score += int(base * mult)
        self.combo = min(8, self.combo + 1)
        self.combo_timer = 120

    def add_explosion(self, x, y, n=16, speed=4.0, big=False):
        for _ in range(n):
            ang = random.uniform(0, math.tau)
            sp = random.uniform(0.5, speed)
            self.particles.append(Particle(
                x, y, math.cos(ang) * sp, math.sin(ang) * sp,
                random.uniform(18, 36), random.uniform(2, 5) + (2 if big else 0),
                random.choice(EXPLOSION_COLORS)))

    def bump_shake(self, amount):
        self.shake = max(self.shake, amount)

    def maybe_drop(self, x, y, chance):
        if random.random() < chance:
            kinds = ["triple", "shield", "double", "slow", "magnet", "bomb", "life"]
            weights = [22, 20, 16, 14, 12, 9, 7]
            self.powerups.append(PowerUp(x, y, random.choices(kinds, weights=weights)[0]))

    def apply_powerup(self, kind):
        if kind == "triple":
            self.player.triple = 60 * TRIPLE_SECONDS
        elif kind == "shield":
            self.player.shield = 60 * SHIELD_SECONDS
        elif kind == "life":
            self.player.lives = min(MAX_LIVES, self.player.lives + 1)
        elif kind == "slow":
            self.slow_timer = 60 * SLOW_SECONDS
        elif kind == "magnet":
            self.magnet_timer = 60 * MAGNET_SECONDS
        elif kind == "double":
            self.double_timer = 60 * DOUBLE_SECONDS
        elif kind == "bomb":
            self.detonate_bomb()

    def detonate_bomb(self):
        self.sounds["bomb"].play()
        self.flash_timer = 14
        self.bump_shake(12)
        for a in self.asteroids:
            self.add_explosion(a.x, a.y, 14, 4.5, big=a.tier >= 2)
            self.add_score(a.score())
        self.asteroids = []
        survivors = []
        for e in self.enemies:
            e.hp -= 3
            if e.hp <= 0:
                self.add_explosion(e.x, e.y, 24, 5.5, big=True)
                self.add_score(e.score())
                self.maybe_drop(e.x, e.y, 0.5)
            else:
                e.flash = 6
                survivors.append(e)
        self.enemies = survivors

    # ---------- обновление ----------
    def update(self, dt, keys):
        star_dt = dt * 0.25 if self.state == "paused" else dt
        for s in self.stars:
            s.update(star_dt)
        if self.shake > 0:
            self.shake = max(0, self.shake - dt)
        if self.state == "playing":
            self.update_playing(dt, keys)
        if self.state != "paused":
            for p in self.particles:
                p.update(dt)
            self.particles = [p for p in self.particles if p.alive()]

    def update_playing(self, dt, keys):
        self.elapsed += dt / 60.0
        self.difficulty = min(6.0, 1.0 + self.elapsed / DIFFICULTY_RAMP)
        self.player.update(dt, keys)

        # таймеры бонусов
        for attr in ("slow_timer", "magnet_timer", "double_timer"):
            v = getattr(self, attr)
            if v > 0:
                setattr(self, attr, max(0, v - dt))
        if self.flash_timer > 0:
            self.flash_timer = max(0, self.flash_timer - dt)

        hazard_dt = dt * (0.4 if self.slow_timer > 0 else 1.0)  # замедление времени

        if keys[pygame.K_SPACE] and self.player.can_shoot():
            self.bullets.extend(self.player.shoot())
            self.sounds["shoot"].play()

        if self.combo_timer > 0:
            self.combo_timer -= dt
            if self.combo_timer <= 0:
                self.combo = 1

        self.ast_timer -= dt
        if self.ast_timer <= 0:
            tier = random.choice([3, 3, 2, 2, 2, 1])
            atype = random.choices(["normal", "metal", "explosive", "ice"],
                                   weights=[58, 18, 12, 12])[0]
            self.asteroids.append(Asteroid(random.uniform(60, WIDTH - 60), -60,
                                           tier, self.difficulty, atype=atype))
            self.ast_timer = max(16, 52 - self.difficulty * 5) + random.uniform(-6, 6)

        self.enemy_timer -= dt
        if self.enemy_timer <= 0:
            self.enemies.append(Enemy(self.difficulty))
            self.enemy_timer = max(360, 780 - self.difficulty * 60) + random.uniform(-120, 120)

        for b in self.bullets:
            b.update(dt)
        for b in self.enemy_bullets:
            b.update(hazard_dt)
        for a in self.asteroids:
            a.update(hazard_dt)
        for e in self.enemies:
            e.update(hazard_dt)
            if e.want_fire():
                ang = math.atan2(self.player.y - e.y, self.player.x - e.x)
                self.enemy_bullets.append(Bullet(e.x, e.y + 10,
                                                 math.cos(ang) * 4.2, math.sin(ang) * 4.2,
                                                 RED, 5, friendly=False))
                self.sounds["enemy_shoot"].play()

        self.handle_collisions()

        for pu in self.powerups:
            pu.update(dt)
            if self.magnet_timer > 0:  # магнит притягивает бонусы
                dx, dy = self.player.x - pu.x, self.player.y - pu.y
                d = math.hypot(dx, dy) or 1
                pu.x += dx / d * 6.5 * dt
                pu.y += dy / d * 6.5 * dt
        self._collect_powerups()

        self.bullets = [b for b in self.bullets if not b.dead and not b.offscreen()]
        self.enemy_bullets = [b for b in self.enemy_bullets if not b.offscreen()]
        self.asteroids = [a for a in self.asteroids if not a.offscreen()]
        self.enemies = [e for e in self.enemies if not e.offscreen()]

    def _collect_powerups(self):
        keep = []
        for pu in self.powerups:
            if pu.offscreen():
                continue
            if (pu.x - self.player.x) ** 2 + (pu.y - self.player.y) ** 2 <= \
                    (pu.radius + self.player.radius + 6) ** 2:
                self.apply_powerup(pu.kind)
                self.sounds["powerup"].play()
                self.add_explosion(pu.x, pu.y, 10, 3.0)
            else:
                keep.append(pu)
        self.powerups = keep

    def on_asteroid_destroyed(self, a, surviving, blasts):
        self.add_score(a.score())
        self.sounds["explosion"].play()
        drop = 0.16 if a.atype == "ice" else (0.10 if a.tier == 1 else 0.07)
        self.maybe_drop(a.x, a.y, drop)
        if a.atype == "explosive":
            self.add_explosion(a.x, a.y, 28, 6.0, big=True)
            self.bump_shake(8)
            blasts.append((a.x, a.y))
        else:
            self.add_explosion(a.x, a.y, 14 if a.tier > 1 else 10, 4.0, big=a.tier >= 3)
            self.bump_shake(4 if a.tier >= 3 else 2)
            surviving.extend(a.split())

    def do_blast(self, x, y, radius=120):
        # взрывной астероид задевает всё рядом
        p = self.player
        if p.invuln <= 0 and p.shield <= 0 and (p.x - x) ** 2 + (p.y - y) ** 2 <= radius ** 2:
            self.player_hit(("blast", None))
        remaining, chain = [], []
        for a in self.asteroids:
            if (a.x - x) ** 2 + (a.y - y) ** 2 <= (radius + a.radius) ** 2:
                self.add_explosion(a.x, a.y, 12, 4.5)
                self.add_score(a.score())
                if a.atype == "explosive":
                    chain.append((a.x, a.y))
            else:
                remaining.append(a)
        self.asteroids = remaining
        for cx, cy in chain:
            self.do_blast(cx, cy, radius)

    def handle_collisions(self):
        # пули игрока × астероиды (с учётом прочности)
        surviving, blasts = [], []
        for a in self.asteroids:
            for b in self.bullets:
                if b.friendly and not b.dead and \
                        (b.x - a.x) ** 2 + (b.y - a.y) ** 2 <= (a.radius + b.radius) ** 2:
                    b.dead = True
                    a.hp -= 1
                    a.hit_flash = 5
                    if a.hp <= 0:
                        break
            if a.hp <= 0:
                self.on_asteroid_destroyed(a, surviving, blasts)
            else:
                surviving.append(a)
        self.asteroids = surviving
        for bx, by in blasts:
            self.do_blast(bx, by)
        self.bullets = [b for b in self.bullets if not b.dead]

        # пули игрока × враги
        for e in self.enemies:
            for b in self.bullets:
                if b.friendly and not b.dead and e.hit(b.x, b.y, b.radius):
                    b.dead = True
                    e.hp -= 1
                    e.flash = 6
                    self.add_explosion(b.x, b.y, 6, 3.0)
                    self.sounds["explosion"].play()
                    break
        self.bullets = [b for b in self.bullets if not b.dead]

        alive = []
        for e in self.enemies:
            if e.hp <= 0:
                self.add_score(e.score())
                self.add_explosion(e.x, e.y, 26, 5.5, big=True)
                self.sounds["big_explosion"].play()
                self.bump_shake(7)
                self.maybe_drop(e.x, e.y, 0.55)
            else:
                alive.append(e)
        self.enemies = alive

        # опасности × игрок
        p = self.player
        if p.invuln <= 0 and p.shield <= 0:
            hazard = None
            for a in self.asteroids:
                if (a.x - p.x) ** 2 + (a.y - p.y) ** 2 <= (a.radius + p.radius) ** 2:
                    hazard = ("ast", a)
                    break
            if not hazard:
                for e in self.enemies:
                    if e.hit(p.x, p.y, p.radius):
                        hazard = ("enemy", e)
                        break
            if not hazard:
                for b in self.enemy_bullets:
                    if (b.x - p.x) ** 2 + (b.y - p.y) ** 2 <= (b.radius + p.radius) ** 2:
                        hazard = ("bullet", b)
                        break
            if hazard:
                self.player_hit(hazard)
        elif p.shield > 0:
            for a in self.asteroids[:]:
                if (a.x - p.x) ** 2 + (a.y - p.y) ** 2 <= (a.radius + 34) ** 2:
                    self.add_explosion(a.x, a.y, 10, 3.5)
                    self.sounds["explosion"].play()
                    self.asteroids.remove(a)
                    self.asteroids.extend(a.split())
                    self.add_score(a.score() // 2)
            self.enemy_bullets = [b for b in self.enemy_bullets
                                  if (b.x - p.x) ** 2 + (b.y - p.y) ** 2 > (b.radius + 34) ** 2]

    def player_hit(self, hazard):
        p = self.player
        p.lives -= 1
        p.invuln = 100
        self.combo = 1
        self.add_explosion(p.x, p.y, 22, 5.0, big=True)
        self.bump_shake(9)
        self.sounds["hit"].play()
        kind, obj = hazard
        if kind == "ast" and obj in self.asteroids:
            self.asteroids.remove(obj)
        elif kind == "bullet" and obj in self.enemy_bullets:
            self.enemy_bullets.remove(obj)
        elif kind == "enemy" and obj in self.enemies:
            obj.hp -= 1
        if p.lives <= 0:
            self.end_game()

    def qualifies(self, score):
        if score <= 0:
            return False
        if len(self.high_scores) < 10:
            return True
        return score > min(h["score"] for h in self.high_scores)

    def end_game(self):
        self.sounds["gameover"].play()
        if self.qualifies(self.score):
            self.state = "enter_name"
            self.name_input = ""
        else:
            self.state = "gameover"

    def submit_name(self):
        name = (self.name_input.strip() or "ANON")[:12]
        entry = {"name": name, "score": self.score}
        self.high_scores.append(entry)
        self.high_scores.sort(key=lambda h: h["score"], reverse=True)
        self.high_scores = self.high_scores[:10]
        self.last_rank = next((i for i, h in enumerate(self.high_scores) if h is entry), None)
        save_high_scores(self.high_scores)
        self.state = "gameover"

    # ---------- отрисовка ----------
    def draw(self, screen):
        c = self.canvas
        c.blit(self.bg, (0, 0))
        for s in self.stars:
            s.draw(c)
        if self.state == "menu":
            self.draw_menu(c)
        elif self.state == "ratings":
            self.draw_ratings(c)
        else:
            self.draw_field(c)
            if self.state == "playing" and self.slow_timer > 0:
                ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                ov.fill((80, 140, 255, 28))
                c.blit(ov, (0, 0))
            if self.state == "paused":
                self.draw_pause(c)
            elif self.state == "gameover":
                self.draw_gameover(c)
            elif self.state == "enter_name":
                self.draw_enter_name(c)
        if self.flash_timer > 0:
            ov = pygame.Surface((WIDTH, HEIGHT))
            ov.fill((255, 255, 255))
            ov.set_alpha(int(180 * max(0, self.flash_timer / 14)))
            c.blit(ov, (0, 0))
        ox = oy = 0
        if self.shake > 0:
            mag = min(self.shake, 12)
            ox = random.uniform(-mag, mag)
            oy = random.uniform(-mag, mag)
        screen.fill((0, 0, 0))
        screen.blit(c, (ox, oy))

    def draw_field(self, c):
        for pu in self.powerups:
            pu.draw(c)
        for a in self.asteroids:
            a.draw(c)
        for e in self.enemies:
            e.draw(c)
        for b in self.enemy_bullets:
            b.draw(c)
        for b in self.bullets:
            b.draw(c)
        for p in self.particles:
            p.draw(c)
        self.player.draw(c)
        self.draw_hud(c)

    def draw_hud(self, c):
        draw_text(c, f"ОЧКИ: {self.score}", self.fonts["hud"], WHITE, topleft=(16, 12))
        b = self.best()
        if b:
            draw_text(c, f"РЕКОРД: {b['score']}", self.fonts["small"], YELLOW, midtop=(WIDTH // 2, 14))
        if self.combo > 1:
            draw_text(c, f"x{self.combo}", self.fonts["hud"], ORANGE, topleft=(16, 46))
        for i in range(self.player.lives):
            draw_mini_ship(c, WIDTH - 28 - i * 34, 28)
        timers = [
            (self.player.triple, "3X", GREEN),
            (self.player.shield, "ЩИТ", CYAN),
            (self.double_timer, "X2", GOLD),
            (self.slow_timer, "ЗАМЕДЛ", ICE_BLUE),
            (self.magnet_timer, "МАГНИТ", MAGNET_RED),
        ]
        y = 78
        for val, label, col in timers:
            if val > 0:
                draw_text(c, f"{label}  {int(val / 60) + 1}", self.fonts["small"], col, topleft=(16, y))
                y += 26

    def draw_menu(self, c):
        cx = WIDTH // 2
        draw_text(c, "КОСМИЧЕСКИЙ БОЙ", self.fonts["title"], CYAN, center=(cx, 120))
        draw_text(c, "KOSMIK JANG", self.fonts["subtitle"], WHITE, center=(cx, 172))
        b = self.best()
        if b:
            draw_text(c, f"Рекорд / Rekord:  {b['score']} — {b['name']}",
                      self.fonts["small"], YELLOW, center=(cx, 212))
        lines = [
            ("\u2190 \u2192 \u2191 \u2193   /   W A S D", "движение  •  harakat"),
            ("ПРОБЕЛ   /   SPACE", "стрелять  •  otish"),
            ("P", "пауза  •  pauza"),
            ("F", "весь экран  •  to'liq ekran"),
        ]
        y = 278
        for key, desc in lines:
            draw_text(c, key, self.fonts["hud"], YELLOW, center=(cx, y))
            draw_text(c, desc, self.fonts["small"], GREY, center=(cx, y + 24))
            y += 62
        if int(pygame.time.get_ticks() / 450) % 2 == 0:
            draw_text(c, "Нажми ПРОБЕЛ, чтобы начать", self.fonts["hud"], GREEN, center=(cx, HEIGHT - 96))
            draw_text(c, "Boshlash uchun SPACE bosing", self.fonts["small"], GREEN, center=(cx, HEIGHT - 66))
        draw_text(c, "R — рейтинг • reyting          ESC — выход • chiqish",
                  self.fonts["small"], GREY, center=(cx, HEIGHT - 28))

    def draw_ratings(self, c):
        cx = WIDTH // 2
        draw_text(c, "РЕЙТИНГ  /  REYTING", self.fonts["title2"], CYAN, center=(cx, 78))
        if not self.high_scores:
            draw_text(c, "Пока нет рекордов  •  Hali rekord yo'q",
                      self.fonts["hud"], GREY, center=(cx, HEIGHT // 2))
        else:
            rank_colors = {0: GOLD, 1: (200, 205, 215), 2: (205, 140, 80)}
            y = 165
            for i, h in enumerate(self.high_scores[:10]):
                col = rank_colors.get(i, WHITE)
                font = self.fonts["hud"] if i < 3 else self.fonts["small"]
                draw_text(c, f"{i + 1}.    {h['name']:<12}    {h['score']}", font, col, center=(cx, y))
                y += 46 if i < 3 else 38
        draw_text(c, "ESC / ПРОБЕЛ — назад  •  orqaga",
                  self.fonts["small"], GREY, center=(cx, HEIGHT - 44))

    def draw_pause(self, c):
        ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 150))
        c.blit(ov, (0, 0))
        cx, cy = WIDTH // 2, HEIGHT // 2
        draw_text(c, "ПАУЗА  /  PAUZA", self.fonts["title2"], WHITE, center=(cx, cy - 30))
        draw_text(c, "Нажми P чтобы продолжить  •  Davom etish uchun P",
                  self.fonts["small"], GREY, center=(cx, cy + 30))
        draw_text(c, "M — главное меню  •  bosh menyu",
                  self.fonts["small"], CYAN, center=(cx, cy + 66))

    def draw_gameover(self, c):
        ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 175))
        c.blit(ov, (0, 0))
        cx = WIDTH // 2
        draw_text(c, "ИГРА ОКОНЧЕНА", self.fonts["title2"], RED, center=(cx, 74))
        draw_text(c, "O'YIN TUGADI", self.fonts["subtitle"], WHITE, center=(cx, 118))
        draw_text(c, f"Твой счёт / Hisob:  {self.score}", self.fonts["hud"], YELLOW, center=(cx, 174))
        draw_text(c, "ЛУЧШИЕ  /  ENG YAXSHILAR", self.fonts["hud"], CYAN, center=(cx, 226))
        y = 266
        for i, h in enumerate(self.high_scores[:6]):
            col = YELLOW if i == self.last_rank else WHITE
            draw_text(c, f"{i + 1}.  {h['name']:<12}  {h['score']}", self.fonts["small"], col, center=(cx, y))
            y += 32
        if int(pygame.time.get_ticks() / 450) % 2 == 0:
            draw_text(c, "ПРОБЕЛ — играть снова  •  SPACE — qayta o'ynash",
                      self.fonts["small"], GREEN, center=(cx, HEIGHT - 52))
        draw_text(c, "M — главное меню  •  bosh menyu",
                  self.fonts["small"], CYAN, center=(cx, HEIGHT - 24))

    def draw_enter_name(self, c):
        ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 185))
        c.blit(ov, (0, 0))
        cx = WIDTH // 2
        draw_text(c, "НОВЫЙ РЕКОРД!  /  YANGI REKORD!", self.fonts["title2"], YELLOW, center=(cx, 150))
        draw_text(c, f"Счёт / Hisob:  {self.score}", self.fonts["hud"], WHITE, center=(cx, 214))
        draw_text(c, "Введи имя  •  Ismingizni kiriting:", self.fonts["hud"], CYAN, center=(cx, 288))
        cursor = "_" if int(pygame.time.get_ticks() / 350) % 2 == 0 else " "
        draw_text(c, self.name_input + cursor, self.fonts["title2"], GREEN, center=(cx, 352))
        draw_text(c, "ENTER — подтвердить  •  tasdiqlash", self.fonts["small"], GREY, center=(cx, HEIGHT - 56))


# ============================================================
#  Ввод и главный цикл
# ============================================================
class FakeKeys:
    def __init__(self, pressed):
        self.pressed = set(pressed)

    def __getitem__(self, k):
        return k in self.pressed


def handle_keydown(game, e):
    k = e.key
    if game.state == "menu":
        if k == pygame.K_SPACE:
            game.start()
        elif k == pygame.K_r:
            game.state = "ratings"
    elif game.state == "ratings":
        if k in (pygame.K_ESCAPE, pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
            game.state = "menu"
    elif game.state == "playing":
        if k == pygame.K_p:
            game.state = "paused"
    elif game.state == "paused":
        if k == pygame.K_p:
            game.state = "playing"
        elif k == pygame.K_m:
            game.state = "menu"
    elif game.state == "gameover":
        if k == pygame.K_SPACE:
            game.start()
        elif k == pygame.K_m:
            game.state = "menu"
    elif game.state == "enter_name":
        if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
            game.submit_name()
        elif k == pygame.K_BACKSPACE:
            game.name_input = game.name_input[:-1]
        else:
            ch = getattr(e, "unicode", "")
            if ch and ch.isprintable() and ch not in ("\r", "\n", "\t") \
                    and len(game.name_input) < 12:
                game.name_input += ch


def smoke_keys(frame):
    pressed = {pygame.K_SPACE}
    pressed.add(pygame.K_a if (frame // 30) % 2 == 0 else pygame.K_d)
    if (frame // 45) % 3 == 0:
        pressed.add(pygame.K_w)
    return pressed


def main():
    pygame.mixer.pre_init(SR, -16, 2, 512)
    pygame.init()
    try:
        pygame.mixer.init(SR, -16, 2, 512)
        pygame.mixer.set_num_channels(16)
    except Exception:
        pass

    flags = pygame.SCALED | pygame.RESIZABLE
    try:
        screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
    except Exception:
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Космический бой / Kosmik Jang")

    clock = pygame.time.Clock()
    sounds = make_sounds()
    fonts = {
        "title": get_font(62, bold=True),
        "title2": get_font(50, bold=True),
        "subtitle": get_font(32, bold=True),
        "hud": get_font(30, bold=True),
        "small": get_font(22),
    }
    game = Game(sounds, fonts)

    running = True
    frame = 0
    while running:
        dt = min(3.0, clock.tick(FPS) / (1000.0 / FPS))
        events = pygame.event.get()

        if SMOKE:
            if frame == 1:
                events.append(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_r}))
            if frame == 2:
                events.append(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_SPACE}))
            if frame == 4:
                events.append(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_SPACE}))
            if frame == 20 and game.state == "playing":
                for i, at in enumerate(["metal", "explosive", "ice", "normal"]):
                    a = Asteroid(180 + i * 160, 90, 3, atype=at)
                    a.vy = 0.5
                    game.asteroids.append(a)
            if frame == 60 and game.state == "playing":
                for kk in ["triple", "shield", "slow", "magnet", "double", "life"]:
                    game.apply_powerup(kk)
            if frame == 100 and game.state == "playing":
                game.detonate_bomb()
            if game.state == "playing" and frame == 430:
                game.player.lives = 1
                game.player.invuln = 0
                game.player.shield = 0
                a = Asteroid(game.player.x, game.player.y, 1)
                a.vy = 0
                game.asteroids.append(a)
            if game.state == "enter_name":
                if len(game.name_input) < 3:
                    events.append(pygame.event.Event(
                        pygame.KEYDOWN, {"key": pygame.K_q, "unicode": "Q"}))
                else:
                    events.append(pygame.event.Event(
                        pygame.KEYDOWN, {"key": pygame.K_RETURN, "unicode": "\r"}))
            if game.state == "gameover":
                events.append(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_m}))

        for e in events:
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                handle_keydown(game, e)
                if e.key == pygame.K_f:
                    try:
                        pygame.display.toggle_fullscreen()
                    except Exception:
                        pass
                elif e.key == pygame.K_ESCAPE:
                    if game.state == "menu":
                        running = False
                    elif game.state == "playing":
                        game.state = "paused"
                    elif game.state == "paused":
                        game.state = "playing"
                    elif game.state in ("gameover", "ratings"):
                        game.state = "menu"

        keys = FakeKeys(smoke_keys(frame)) if SMOKE else pygame.key.get_pressed()
        game.update(dt, keys)
        game.draw(screen)
        pygame.display.flip()

        frame += 1
        if SMOKE and frame > 620:
            running = False

    pygame.quit()


if __name__ == "__main__":
    main()
