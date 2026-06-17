# -*- coding: utf-8 -*-
"""
ПЕРЕВОРОТ  /  AG'DAR  (платформер как Mario, но с переворотом гравитации)
Главная фишка: кнопкой меняешь гравитацию — падаешь на ПОТОЛОК и бежишь по нему.

Запуск:   python platformer.py
Нужно:    pip install pygame numpy      (numpy — только для звуков)

Управление:
    ← →  или  A D    — идти
    ПРОБЕЛ / ↑ / W    — прыжок (держи дольше — выше)
    SHIFT / ↓ / S     — ПЕРЕВОРОТ гравитации (пол <-> потолок)
    На врага прыгай сверху, шипов не касайся, дойди до флага.
    P — пауза,  F — весь экран,  M — меню,  R — рейтинг,  ESC — назад/выход
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
#  НАСТРОЙКИ — можно менять
# ============================================================
WIDTH, HEIGHT = 1000, 720
FPS = 60
START_LIVES = 3
TILE = 40
ROWS = 16
HUD_H = HEIGHT - ROWS * TILE          # полоса сверху под счёт
MOVE_SPEED = 4.7
ACCEL = 0.9
FRICTION = 0.80
GRAV = 0.80
MAX_FALL = 16.0
JUMP_V = 14.6
JUMP_CUT = 0.45
BOUNCE_V = 12.5
COYOTE = 6
JUMP_BUFFER = 7
FLIP_CD = 9
COIN_SCORE = 10
GOAL_SCORE = 500
MAX_LIVES = 5
# ============================================================

SR = 44100


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


HIGHSCORE_FILE = os.path.join(_data_dir(), "platformer_scores.json")
SMOKE = os.environ.get("SMOKE") == "1"

WHITE = (245, 248, 255)
CYAN = (90, 220, 255)
YELLOW = (255, 224, 90)
ORANGE = (255, 150, 50)
RED = (235, 80, 80)
GREEN = (110, 230, 140)
PINK = (255, 120, 190)
PURPLE = (185, 120, 255)
GREY = (150, 160, 180)
GOLD = (255, 205, 60)
SKY_TOP = (94, 170, 240)
SKY_BOT = (180, 225, 255)
DIRT = (150, 100, 60)
DIRT_DARK = (120, 80, 48)
GRASS = (110, 200, 95)
GRASS_DARK = (80, 165, 70)
SPIKE = (200, 205, 215)
HERO_BODY = (250, 150, 60)
HERO_CAP = (235, 70, 80)
HERO_PANTS = (50, 70, 130)
HERO_SKIN = (245, 205, 165)
ENEMY_C = (170, 95, 215)


def get_font(size, bold=False):
    try:
        f = pygame.font.SysFont(
            "dejavusans,arial,verdana,tahoma,liberationsans,notosans,segoeui", size, bold=bold)
        if f is None:
            raise RuntimeError("no sysfont")
        return f
    except Exception:
        return pygame.font.Font(None, size)


def draw_text(surf, text, font, color, center=None, topleft=None, midtop=None, shadow=True):
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center:
        rect.center = center
    elif topleft:
        rect.topleft = topleft
    elif midtop:
        rect.midtop = midtop
    if shadow:
        surf.blit(font.render(text, True, (0, 0, 0)), (rect.x + 2, rect.y + 2))
    surf.blit(img, rect)
    return rect


def star_points(cx, cy, outer, inner, n=5, rot=-math.pi / 2):
    pts = []
    for i in range(n * 2):
        r = outer if i % 2 == 0 else inner
        a = rot + i * math.pi / n
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return pts


def draw_heart(surf, cx, cy, c, s=7):
    pygame.draw.circle(surf, c, (cx - s // 2, cy - 1), s // 2 + 1)
    pygame.draw.circle(surf, c, (cx + s // 2, cy - 1), s // 2 + 1)
    pygame.draw.polygon(surf, c, [(cx - s - 1, cy), (cx + s + 1, cy), (cx, cy + s + 2)])


# ============================================================
#  Звуки
# ============================================================
class DummySound:
    def play(self, *a, **k):
        return None


def _to_sound(mono):
    mono = np.clip(mono, -1.0, 1.0)
    s = (mono * 32767).astype(np.int16)
    return pygame.sndarray.make_sound(np.ascontiguousarray(np.column_stack([s, s])))


def _tone(freq, dur, vol=0.4, kind="sine", sweep=None, attack=0.004, release=0.05):
    n = max(1, int(SR * dur))
    if sweep is None:
        phase = 2 * np.pi * freq * (np.arange(n) / SR)
    else:
        phase = 2 * np.pi * np.cumsum(np.linspace(freq, sweep, n)) / SR
    if kind == "square":
        w = np.sign(np.sin(phase))
    elif kind == "saw":
        w = 2 * (phase / (2 * np.pi) % 1) - 1
    elif kind == "noise":
        w = np.random.uniform(-1, 1, n)
    else:
        w = np.sin(phase)
    env = np.ones(n)
    a, r = max(1, int(SR * attack)), max(1, int(SR * release))
    env[:a] = np.linspace(0, 1, a)
    env[-r:] = np.linspace(1, 0, r)
    return w * env * vol


def _decay_noise(dur, vol=0.4, power=2.0):
    n = max(1, int(SR * dur))
    return np.random.uniform(-1, 1, n) * ((1 - np.arange(n) / n) ** power) * vol


def _seq(parts):
    return np.concatenate(parts) if parts else np.zeros(1)


def make_sounds():
    keys = ["jump", "flip", "coin", "stomp", "hurt", "goal", "gameover"]
    sounds = {k: DummySound() for k in keys}
    if not HAS_NUMPY:
        return sounds

    def safe(key, fn):
        try:
            sounds[key] = _to_sound(fn())
        except Exception:
            sounds[key] = DummySound()

    safe("jump", lambda: _tone(420, 0.12, 0.16, "square", sweep=780))
    safe("flip", lambda: _seq([_tone(300, 0.08, 0.18, "sine", sweep=700),
                               _tone(700, 0.08, 0.18, "sine", sweep=300)]))
    safe("coin", lambda: _seq([_tone(1000, 0.05, 0.13), _tone(1500, 0.07, 0.13)]))
    safe("stomp", lambda: _seq([_tone(500, 0.05, 0.2), _tone(250, 0.1, 0.22, "square")]))
    safe("hurt", lambda: _seq([_decay_noise(0.3, 0.34, 1.6), _tone(180, 0.18, 0.28, "saw", sweep=70)]))
    safe("goal", lambda: _seq([_tone(523, 0.1, 0.24), _tone(659, 0.1, 0.24), _tone(784, 0.1, 0.24),
                               _tone(1046, 0.22, 0.24)]))
    safe("gameover", lambda: _seq([_tone(392, 0.18, 0.28, "square"), _tone(330, 0.18, 0.28, "square"),
                                   _tone(262, 0.2, 0.28, "square"), _tone(196, 0.4, 0.28, "square")]))
    return sounds


# ============================================================
#  Рекорды
# ============================================================
def load_high_scores():
    try:
        with open(HIGHSCORE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        out = [{"name": str(h["name"])[:12], "score": int(h["score"])}
               for h in data if isinstance(h, dict) and "name" in h and "score" in h]
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


def make_sky():
    surf = pygame.Surface((WIDTH, HEIGHT))
    for y in range(HEIGHT):
        t = y / (HEIGHT - 1)
        surf.fill((int(SKY_TOP[0] + (SKY_BOT[0] - SKY_TOP[0]) * t),
                   int(SKY_TOP[1] + (SKY_BOT[1] - SKY_TOP[1]) * t),
                   int(SKY_TOP[2] + (SKY_BOT[2] - SKY_TOP[2]) * t)), (0, y, WIDTH, 1))
    return surf


# ============================================================
#  Уровни
# ============================================================
def make_level(cols, features, pits):
    grid = [[" "] * cols for _ in range(ROWS)]
    for c in range(cols):
        grid[0][c] = "#"
        grid[1][c] = "#"
        grid[ROWS - 2][c] = "#"
        grid[ROWS - 1][c] = "#"
    for (c0, c1) in pits:
        for c in range(c0, c1 + 1):
            grid[ROWS - 2][c] = " "
            grid[ROWS - 1][c] = " "
    data = {"coins": [], "spikes": [], "enemies": [], "checkpoints": [], "goal": None, "start": (2, ROWS - 3)}
    for ch, c, row in features:
        if ch == "#":
            grid[row][c] = "#"
        elif ch == "^":
            data["spikes"].append((c, row))
        elif ch == "o":
            data["coins"].append((c, row))
        elif ch == "E":
            data["enemies"].append((c, row, "floor"))
        elif ch == "U":
            data["enemies"].append((c, row, "ceil"))
        elif ch == "C":
            data["checkpoints"].append((c, row))
        elif ch == "G":
            data["goal"] = (c, row)
        elif ch == "P":
            data["start"] = (c, row)
    return grid, data


FLOOR_ROW = ROWS - 3      # ряд тела игрока, стоящего на полу (13)
CEIL_ROW = 2              # ряд тела на потолке

LEVEL1_F = [
    ("P", 2, FLOOR_ROW),
    ("o", 5, FLOOR_ROW), ("o", 6, FLOOR_ROW), ("o", 7, FLOOR_ROW),
    ("#", 10, 11), ("#", 11, 11), ("o", 10, 10), ("o", 11, 10),
    ("o", 14, 12),
    ("o", 16, 11), ("o", 17, 10), ("o", 18, 11),
    ("E", 22, FLOOR_ROW),
    ("^", 27, FLOOR_ROW), ("^", 28, FLOOR_ROW), ("^", 29, FLOOR_ROW), ("^", 30, FLOOR_ROW), ("^", 31, FLOOR_ROW),
    ("o", 27, CEIL_ROW), ("o", 28, CEIL_ROW), ("o", 29, CEIL_ROW), ("o", 30, CEIL_ROW), ("o", 31, CEIL_ROW),
    ("C", 34, FLOOR_ROW),
    ("E", 40, FLOOR_ROW),
    ("o", 44, FLOOR_ROW), ("o", 45, FLOOR_ROW),
    ("#", 47, 11), ("#", 48, 11), ("o", 47, 10),
    ("G", 53, FLOOR_ROW),
]
LEVEL1_HINTS = [(2, 10, "СТРЕЛКИ — идти,  ПРОБЕЛ — прыжок"),
                (23, 7, "SHIFT / \u2193 — ПЕРЕВОРОТ гравитации!"),
                (23, 9, "беги по потолку над шипами \u2192")]

LEVEL2_F = [
    ("P", 2, FLOOR_ROW),
    ("o", 5, FLOOR_ROW), ("o", 6, FLOOR_ROW),
    ("^", 9, FLOOR_ROW), ("^", 10, FLOOR_ROW), ("^", 11, FLOOR_ROW), ("^", 12, FLOOR_ROW),
    ("o", 9, CEIL_ROW), ("o", 10, CEIL_ROW), ("o", 11, CEIL_ROW), ("o", 12, CEIL_ROW),
    ("^", 16, CEIL_ROW), ("^", 17, CEIL_ROW), ("^", 18, CEIL_ROW), ("^", 19, CEIL_ROW),
    ("o", 16, FLOOR_ROW), ("o", 17, FLOOR_ROW), ("o", 18, FLOOR_ROW), ("o", 19, FLOOR_ROW),
    ("U", 24, CEIL_ROW),
    ("E", 28, FLOOR_ROW),
    ("C", 32, FLOOR_ROW),
    ("^", 36, FLOOR_ROW), ("^", 37, FLOOR_ROW), ("^", 38, FLOOR_ROW), ("^", 39, FLOOR_ROW), ("^", 40, FLOOR_ROW),
    ("o", 36, CEIL_ROW), ("o", 38, CEIL_ROW), ("o", 40, CEIL_ROW),
    ("o", 45, 11), ("o", 46, 11),
    ("E", 52, FLOOR_ROW),
    ("o", 55, FLOOR_ROW), ("o", 56, FLOOR_ROW),
    ("G", 61, FLOOR_ROW),
]
LEVEL2_HINTS = [(7, 7, "шипы на полу \u2192 переворот вверх"),
                (14, 7, "шипы на потолке \u2192 переворот вниз"),
                (42, 9, "широкая яма \u2192 перейди по потолку")]

LEVELS = [
    (make_level(56, LEVEL1_F, [(16, 18)]), LEVEL1_HINTS),
    (make_level(64, LEVEL2_F, [(44, 47)]), LEVEL2_HINTS),
]


# ============================================================
#  Объекты
# ============================================================
class Particle:
    def __init__(self, x, y, vx, vy, life, radius, color, grav=0.0):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = self.max_life = life
        self.radius, self.color, self.grav = radius, color, grav

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += self.grav * dt
        self.vx *= 0.97
        self.life -= dt

    def alive(self):
        return self.life > 0

    def draw(self, surf, camx):
        r = max(1, int(self.radius * max(0.0, self.life / self.max_life)))
        pygame.draw.circle(surf, self.color, (int(self.x - camx), int(self.y + HUD_H)), r)


class Enemy:
    W, H = 32, 28

    def __init__(self, col, row, kind):
        self.kind = kind
        self.dir = random.choice([-1, 1])
        self.alive = True
        self.x = col * TILE + (TILE - self.W) / 2
        if kind == "floor":
            self.y = (ROWS - 2) * TILE - self.H   # стоит на полу
        else:
            self.y = 2 * TILE                       # висит на потолке
        self.t = 0.0

    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.W, self.H)

    def update(self, game, dt):
        if not self.alive:
            return
        self.t += dt
        self.x += self.dir * 1.7 * dt
        # развернуться у стены или у края
        foot_row = int((self.y + self.H + 2) / TILE) if self.kind == "floor" else int((self.y - 2) / TILE)
        ahead_col = int((self.x + (self.W if self.dir > 0 else 0) + self.dir * 2) / TILE)
        body_row = int((self.y + self.H / 2) / TILE)
        if game.solid(ahead_col, body_row) or not game.solid(ahead_col, foot_row):
            self.dir *= -1
            self.x += self.dir * 2 * dt

    def draw(self, surf, camx):
        if not self.alive:
            return
        x = int(self.x - camx)
        y = int(self.y + HUD_H)
        flip = self.kind == "ceil"
        body = pygame.Rect(x, y, self.W, self.H)
        pygame.draw.ellipse(surf, ENEMY_C, body)
        pygame.draw.ellipse(surf, tuple(max(0, c - 40) for c in ENEMY_C), body, 2)
        # шипы-гребень
        for sx in range(x + 4, x + self.W - 2, 8):
            top = y if not flip else y + self.H
            tip = y - 6 if not flip else y + self.H + 6
            pygame.draw.polygon(surf, ENEMY_C, [(sx, top), (sx + 4, top), (sx + 2, tip)])
        ey = y + (10 if not flip else self.H - 10)
        wob = int(math.sin(self.t * 0.2) * 2)
        for ex in (x + 9, x + self.W - 9):
            pygame.draw.circle(surf, WHITE, (ex, ey), 5)
            pygame.draw.circle(surf, (30, 20, 40), (ex + wob, ey), 2)


# ============================================================
#  Игрок
# ============================================================
class Player:
    W, H = 26, 34

    def __init__(self):
        self.reset(2, FLOOR_ROW)

    def reset(self, col, row):
        self.x = col * TILE + (TILE - self.W) / 2
        self.y = (ROWS - 2) * TILE - self.H
        self.vx = 0.0
        self.vy = 0.0
        self.gdir = 1            # 1 — вниз, -1 — вверх
        self.on_ground = False
        self.coyote = 0
        self.jump_buffer = 0
        self.flip_cd = 0
        self.facing = 1
        self.phase = 0.0
        self.prev_y = self.y

    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.W, self.H)


# ============================================================
#  Игра
# ============================================================
class Game:
    def __init__(self, sounds, fonts):
        self.sounds = sounds
        self.fonts = fonts
        self.sky = make_sky()
        self.canvas = pygame.Surface((WIDTH, HEIGHT))
        self.high_scores = load_high_scores()
        self.state = "menu"
        self.name_input = ""
        self.last_rank = None
        self.shake = 0
        self.clouds = [[random.uniform(0, WIDTH), random.uniform(20, HUD_H + 160), random.uniform(40, 90)]
                       for _ in range(7)]
        self.player = Player()
        self.reset_run()

    def reset_run(self):
        self.lives = START_LIVES
        self.score = 0
        self.coins_got = 0
        self.level_index = 0
        self.won = False
        self.load_level(0)

    def load_level(self, idx):
        (grid, data), hints = LEVELS[idx]
        self.grid = grid
        self.cols = len(grid[0])
        self.level_w = self.cols * TILE
        self.solid_grid = [[c == "#" for c in row] for row in grid]
        self.coins = [[c, r, False] for (c, r) in data["coins"]]
        self.spikes = []
        for (c, r) in data["spikes"]:
            up = r >= ROWS / 2  # на полу — остриём вверх; на потолке — вниз
            if up:
                self.spikes.append(pygame.Rect(c * TILE + 5, r * TILE + 12, TILE - 10, TILE - 12))
            else:
                self.spikes.append(pygame.Rect(c * TILE + 5, r * TILE, TILE - 10, TILE - 12))
        self.spike_cells = list(data["spikes"])
        self.enemies = [Enemy(c, r, k) for (c, r, k) in data["enemies"]]
        self.checkpoints = [[c, r, False] for (c, r) in data["checkpoints"]]
        gc, gr = data["goal"]
        self.goal_cell = (gc, gr)
        self.goal_rect = pygame.Rect(gc * TILE, (gr - 2) * TILE, TILE, TILE * 3)
        self.hints = hints
        self.start_cell = data["start"]
        self.checkpoint = data["start"]
        self.player.reset(*data["start"])
        self.particles = []
        self.cam_x = 0.0
        self.ready_timer = 55

    def start(self):
        self.reset_run()
        self.state = "playing"

    def best(self):
        return self.high_scores[0] if self.high_scores else None

    def solid(self, col, row):
        if row < 0 or row >= ROWS or col < 0 or col >= self.cols:
            return row < 0 or row >= ROWS  # за пределами по вертикали — нет опоры (пусто), по бокам — стена? -> вне = не твердо сверху/снизу
        return self.solid_grid[row][col]

    def solid_wall(self, col, row):
        if col < 0 or col >= self.cols:
            return True
        if row < 0 or row >= ROWS:
            return False
        return self.solid_grid[row][col]

    # ---------- ввод ----------
    def do_jump(self):
        if self.state == "playing":
            self.player.jump_buffer = JUMP_BUFFER

    def jump_release(self):
        p = self.player
        if p.vy * p.gdir < 0:   # ещё летит вверх (против гравитации)
            p.vy *= JUMP_CUT

    def do_flip(self):
        if self.state != "playing":
            return
        p = self.player
        if p.flip_cd > 0:
            return
        p.gdir *= -1
        p.flip_cd = FLIP_CD
        p.vy = 0.0
        p.on_ground = False
        self.sounds["flip"].play()
        cx, cy = p.x + p.W / 2, p.y + p.H / 2
        for _ in range(14):
            a = random.uniform(0, math.tau)
            self.particles.append(Particle(cx, cy, math.cos(a) * 4, math.sin(a) * 4,
                                            16, random.uniform(2, 4), CYAN))

    # ---------- физика ----------
    def move_x(self, dt):
        p = self.player
        p.x += p.vx * dt
        r = p.rect()
        c0 = int(r.left // TILE)
        c1 = int((r.right - 1) // TILE)
        r0 = int(r.top // TILE)
        r1 = int((r.bottom - 1) // TILE)
        for row in range(r0, r1 + 1):
            for col in range(c0, c1 + 1):
                if self.solid_wall(col, row):
                    tile = pygame.Rect(col * TILE, row * TILE, TILE, TILE)
                    if r.colliderect(tile):
                        if p.vx > 0:
                            p.x = tile.left - p.W
                        elif p.vx < 0:
                            p.x = tile.right
                        p.vx = 0
                        r = p.rect()
        if p.x < 0:
            p.x = 0
        if p.x > self.level_w - p.W:
            p.x = self.level_w - p.W

    def move_y(self, dt):
        p = self.player
        p.prev_y = p.y
        p.vy += GRAV * p.gdir * dt
        if p.vy > MAX_FALL:
            p.vy = MAX_FALL
        if p.vy < -MAX_FALL:
            p.vy = -MAX_FALL
        p.y += p.vy * dt
        grounded = False
        r = p.rect()
        c0 = int(r.left // TILE)
        c1 = int((r.right - 1) // TILE)
        r0 = int(r.top // TILE)
        r1 = int((r.bottom - 1) // TILE)
        for row in range(r0, r1 + 1):
            for col in range(c0, c1 + 1):
                if self.solid_wall(col, row):
                    tile = pygame.Rect(col * TILE, row * TILE, TILE, TILE)
                    if r.colliderect(tile):
                        if p.vy > 0:
                            p.y = tile.top - p.H
                            if p.gdir > 0:
                                grounded = True
                        elif p.vy < 0:
                            p.y = tile.bottom
                            if p.gdir < 0:
                                grounded = True
                        p.vy = 0
                        r = p.rect()
        p.on_ground = grounded

    def update(self, dt, keys):
        if self.shake > 0:
            self.shake = max(0, self.shake - dt)
        for cl in self.clouds:
            cl[0] -= cl[2] * 0.0015 * dt * 16
            if cl[0] < -120:
                cl[0] = WIDTH + 60
                cl[1] = random.uniform(20, HUD_H + 160)
        if self.state == "playing":
            self.update_playing(dt, keys)
        if self.state != "paused":
            for pt in self.particles:
                pt.update(dt)
            self.particles = [pt for pt in self.particles if pt.alive()]

    def update_playing(self, dt, keys):
        p = self.player
        if self.ready_timer > 0:
            self.ready_timer -= dt
            return
        if p.flip_cd > 0:
            p.flip_cd -= dt

        # горизонталь
        ix = (1 if (keys[pygame.K_RIGHT] or keys[pygame.K_d]) else 0) - \
             (1 if (keys[pygame.K_LEFT] or keys[pygame.K_a]) else 0)
        if ix != 0:
            p.vx += ix * ACCEL * dt
            p.vx = max(-MOVE_SPEED, min(MOVE_SPEED, p.vx))
            p.facing = ix
        else:
            p.vx *= FRICTION ** dt if dt else FRICTION
            if abs(p.vx) < 0.05:
                p.vx = 0
        self.move_x(dt)

        # прыжок (буфер + койот)
        if p.jump_buffer > 0:
            p.jump_buffer -= dt
        if p.jump_buffer > 0 and (p.on_ground or p.coyote > 0):
            p.vy = -JUMP_V * p.gdir
            p.jump_buffer = 0
            p.coyote = 0
            p.on_ground = False
            self.sounds["jump"].play()

        was_ground = p.on_ground
        self.move_y(dt)
        if p.on_ground:
            p.coyote = COYOTE
        elif p.coyote > 0:
            p.coyote -= dt

        if p.on_ground and not was_ground and abs(p.vy) < 0.1:
            sy = p.y + (p.H if p.gdir > 0 else 0)
            for _ in range(5):
                self.particles.append(Particle(p.x + p.W / 2 + random.uniform(-8, 8), sy,
                                                random.uniform(-1.5, 1.5), -p.gdir * random.uniform(0, 1.5),
                                                12, random.uniform(2, 3), (210, 210, 215)))

        p.phase += (0.3 + abs(p.vx) * 0.12) * dt

        # упал за пределы (в любую сторону)
        if p.y > ROWS * TILE + 20 or p.y + p.H < -20:
            self.die()
            return

        # анимационный бег только когда на земле
        # враги
        for e in self.enemies:
            e.update(self, dt)
        pr = p.rect()
        for e in self.enemies:
            if not e.alive:
                continue
            if pr.colliderect(e.rect()):
                er = e.rect()
                stomped = False
                if p.gdir > 0 and p.vy >= 0 and p.prev_y + p.H <= er.top + 10:
                    stomped = True
                    p.vy = -BOUNCE_V
                elif p.gdir < 0 and p.vy <= 0 and p.prev_y >= er.bottom - 10:
                    stomped = True
                    p.vy = BOUNCE_V
                if stomped:
                    e.alive = False
                    self.score += 50
                    self.shake = 5
                    self.sounds["stomp"].play()
                    cx, cy = er.centerx, er.centery
                    for _ in range(12):
                        a = random.uniform(0, math.tau)
                        self.particles.append(Particle(cx, cy, math.cos(a) * 4, math.sin(a) * 4,
                                                        14, random.uniform(2, 4), ENEMY_C))
                else:
                    self.die()
                    return

        # шипы
        for sp in self.spikes:
            if pr.colliderect(sp):
                self.die()
                return

        # монеты
        for c in self.coins:
            if c[2]:
                continue
            cr = pygame.Rect(c[0] * TILE + TILE // 2 - 12, c[1] * TILE + TILE // 2 - 12, 24, 24)
            if pr.colliderect(cr):
                c[2] = True
                self.coins_got += 1
                self.score += COIN_SCORE
                self.sounds["coin"].play()
                cx, cy = cr.center
                for _ in range(6):
                    a = random.uniform(0, math.tau)
                    self.particles.append(Particle(cx, cy, math.cos(a) * 3, math.sin(a) * 3,
                                                    12, random.uniform(2, 3), GOLD))

        # чекпоинты
        for cp in self.checkpoints:
            if cp[2]:
                continue
            cr = pygame.Rect(cp[0] * TILE, (cp[1] - 2) * TILE, TILE, TILE * 3)
            if pr.colliderect(cr):
                cp[2] = True
                self.checkpoint = (cp[0], cp[1])
                self.sounds["coin"].play()

        # финиш
        if pr.colliderect(self.goal_rect):
            self.reach_goal()
            return

        # камера
        target = p.x + p.W / 2 - WIDTH * 0.42
        self.cam_x += (target - self.cam_x) * 0.12 * dt
        self.cam_x = max(0, min(self.level_w - WIDTH, self.cam_x))

    def die(self):
        self.lives -= 1
        self.sounds["hurt"].play()
        self.shake = 14
        p = self.player
        cx, cy = p.x + p.W / 2, p.y + p.H / 2
        for _ in range(26):
            a = random.uniform(0, math.tau)
            sp = random.uniform(1.5, 7)
            self.particles.append(Particle(cx, cy, math.cos(a) * sp, math.sin(a) * sp,
                                            random.uniform(16, 28), random.uniform(2, 5), ORANGE, 0.25))
        if self.lives <= 0:
            self.end_game()
        else:
            self.player.reset(*self.checkpoint)
            self.ready_timer = 45

    def reach_goal(self):
        self.sounds["goal"].play()
        self.score += GOAL_SCORE
        for _ in range(40):
            a = random.uniform(0, math.tau)
            sp = random.uniform(2, 9)
            self.particles.append(Particle(self.goal_rect.centerx, self.goal_rect.centery,
                                           math.cos(a) * sp, math.sin(a) * sp,
                                           random.uniform(18, 34), random.uniform(2, 5),
                                           random.choice([GOLD, CYAN, GREEN, PINK])))
        if self.level_index + 1 < len(LEVELS):
            self.level_index += 1
            self.load_level(self.level_index)
        else:
            self.won = True
            self.end_game()

    def end_game(self):
        self.sounds["goal" if self.won else "gameover"].play()
        if self.qualifies(self.score):
            self.state = "enter_name"
            self.name_input = ""
        else:
            self.state = "gameover"

    def qualifies(self, score):
        if score <= 0:
            return False
        if len(self.high_scores) < 10:
            return True
        return score > min(h["score"] for h in self.high_scores)

    def submit_name(self):
        entry = {"name": (self.name_input.strip() or "ANON")[:12], "score": self.score}
        self.high_scores.append(entry)
        self.high_scores.sort(key=lambda h: h["score"], reverse=True)
        self.high_scores = self.high_scores[:10]
        self.last_rank = next((i for i, h in enumerate(self.high_scores) if h is entry), None)
        save_high_scores(self.high_scores)
        self.state = "gameover"

    # ---------- отрисовка ----------
    def draw_bg(self, c):
        c.blit(self.sky, (0, 0))
        for cl in self.clouds:
            x, y, s = int(cl[0]), int(cl[1]), cl[2]
            pygame.draw.ellipse(c, (255, 255, 255), (x, y, int(s * 1.6), int(s)))
            pygame.draw.ellipse(c, (255, 255, 255), (x + int(s * 0.5), y - int(s * 0.3), int(s * 1.3), int(s * 0.9)))
        # дальние холмы (параллакс)
        for layer, col, spd in ((0, (120, 195, 120), 0.25), (1, (90, 175, 100), 0.45)):
            base = HUD_H + ROWS * TILE - 120 - layer * 30
            off = -(self.cam_x * spd) % 360
            for hx in range(-360, WIDTH + 360, 360):
                pygame.draw.circle(c, col, (int(hx + off + 180), base + 120), 180)

    def draw_tile(self, c, col, row, sx, sy):
        # трава сверху и снизу — в зависимости от того, пол это или потолок
        rect = pygame.Rect(sx, sy, TILE, TILE)
        pygame.draw.rect(c, DIRT, rect)
        pygame.draw.rect(c, DIRT_DARK, rect, 1)
        above_empty = not self.solid_wall(col, row - 1)
        below_empty = not self.solid_wall(col, row + 1)
        if above_empty:
            pygame.draw.rect(c, GRASS, (sx, sy, TILE, 8))
            pygame.draw.rect(c, GRASS_DARK, (sx, sy + 8, TILE, 3))
        if below_empty:
            pygame.draw.rect(c, GRASS, (sx, sy + TILE - 8, TILE, 8))
            pygame.draw.rect(c, GRASS_DARK, (sx, sy + TILE - 11, TILE, 3))

    def draw_world(self, c):
        camx = self.cam_x
        col0 = max(0, int(camx // TILE))
        col1 = min(self.cols - 1, int((camx + WIDTH) // TILE) + 1)
        # тайлы
        for row in range(ROWS):
            sy = row * TILE + HUD_H
            for col in range(col0, col1 + 1):
                if self.solid_grid[row][col]:
                    self.draw_tile(c, col, row, col * TILE - camx, sy)
        # шипы
        for (cc, rr) in self.spike_cells:
            sx = cc * TILE - camx
            if sx < -TILE or sx > WIDTH:
                continue
            up = rr >= ROWS / 2
            base_y = rr * TILE + HUD_H + (TILE if up else 0)
            tip_dir = -1 if up else 1
            for k in range(3):
                x0 = sx + 4 + k * 11
                pygame.draw.polygon(c, SPIKE, [(x0, base_y), (x0 + 11, base_y),
                                               (x0 + 5, base_y + tip_dir * 18)])
            pygame.draw.polygon(c, (160, 165, 180),
                                [(sx + 2, base_y), (sx + TILE - 2, base_y)], 2) if False else None
        # монеты
        for cc, rr, taken in self.coins:
            if taken:
                continue
            sx = cc * TILE + TILE // 2 - camx
            if sx < -20 or sx > WIDTH + 20:
                continue
            sy = rr * TILE + TILE // 2 + HUD_H
            wob = abs(math.sin(pygame.time.get_ticks() * 0.005 + cc))
            rw = max(3, int(11 * (0.35 + 0.65 * wob)))
            pygame.draw.ellipse(c, GOLD, (sx - rw, sy - 11, rw * 2, 22))
            pygame.draw.ellipse(c, (255, 240, 170), (sx - rw, sy - 11, rw * 2, 22), 2)
        # чекпоинты
        for cc, rr, on in self.checkpoints:
            sx = cc * TILE - camx + TILE // 2
            if sx < -20 or sx > WIDTH + 20:
                continue
            top = (rr - 2) * TILE + HUD_H
            bot = (rr + 1) * TILE + HUD_H
            pygame.draw.line(c, (200, 200, 210), (sx, top), (sx, bot), 4)
            col = GREEN if on else GREY
            pygame.draw.polygon(c, col, [(sx, top + 4), (sx + 26, top + 14), (sx, top + 24)])
        # финиш
        self.draw_goal(c, camx)
        # враги
        for e in self.enemies:
            e.draw(c, camx)
        # игрок
        self.draw_hero(c, camx)
        # частицы
        for pt in self.particles:
            pt.draw(c, camx)
        # подсказки
        for (cc, rr, text) in self.hints:
            sx = cc * TILE - camx
            if -300 < sx < WIDTH + 50:
                draw_text(c, text, self.fonts["small"], WHITE, topleft=(sx, rr * TILE + HUD_H))

    def draw_goal(self, c, camx):
        gx = self.goal_cell[0] * TILE - camx + TILE // 2
        if gx < -40 or gx > WIDTH + 40:
            return
        top = self.goal_rect.top + HUD_H
        t = pygame.time.get_ticks() * 0.005
        for i, col in enumerate(((255, 220, 90), (140, 220, 255), (180, 255, 170))):
            rr = int(40 + 8 * math.sin(t + i)) - i * 8
            surf = pygame.Surface((rr * 2 + 4, self.goal_rect.height), pygame.SRCALPHA)
            pygame.draw.ellipse(surf, (*col, 90), (0, 0, rr * 2, self.goal_rect.height))
            c.blit(surf, (gx - rr, top))
        pygame.draw.line(c, (230, 230, 240), (gx, top), (gx, top + self.goal_rect.height), 4)
        pygame.draw.polygon(c, YELLOW, [(gx, top + 6), (gx + 30, top + 18), (gx, top + 30)])

    def draw_hero(self, c, camx):
        p = self.player
        if self.ready_timer > 0 and int(self.ready_timer * 0.25) % 2 == 0:
            pass
        surf = pygame.Surface((p.W + 16, p.H + 12), pygame.SRCALPHA)
        ox, oy = 8, 2
        run = abs(p.vx) > 0.4 and p.on_ground
        swing = math.sin(p.phase * 3.0) if run else 0.4
        feet = p.H
        hipx = ox + p.W / 2
        hipy = oy + feet - 14
        # ноги
        for sw, col in ((swing, HERO_PANTS), (-swing, (40, 58, 110))):
            kx = hipx + sw * 6
            ky = hipy + 9
            fx = kx + sw * 5
            fy = oy + feet if run else oy + feet - 3
            pygame.draw.line(surf, col, (hipx, hipy), (kx, ky), 6)
            pygame.draw.line(surf, col, (kx, ky), (fx, fy), 5)
            pygame.draw.ellipse(surf, WHITE, (fx - 5, fy - 3, 11, 6))
        # тело
        pygame.draw.rect(surf, HERO_BODY, (ox + p.W / 2 - 10, hipy - 16, 20, 22), border_radius=6)
        # руки
        for sw in (-swing, swing):
            ax = ox + p.W / 2
            ay = hipy - 12
            ex = ax + sw * 7
            ey = ay + 12
            pygame.draw.line(surf, HERO_BODY, (ax, ay), (ex, ey), 5)
            pygame.draw.circle(surf, HERO_SKIN, (int(ex), int(ey)), 3)
        # голова
        hx = ox + p.W / 2
        hy = hipy - 16 - 9
        pygame.draw.circle(surf, HERO_SKIN, (int(hx), int(hy)), 9)
        pygame.draw.circle(surf, HERO_CAP, (int(hx), int(hy - 3)), 9)
        pygame.draw.rect(surf, HERO_CAP, (hx - 9 + (4 if p.facing > 0 else -8), hy - 5, 12, 4), border_radius=2)
        pygame.draw.circle(surf, (20, 30, 40), (int(hx + 4 * p.facing), int(hy)), 2)

        if p.gdir < 0:
            surf = pygame.transform.flip(surf, False, True)
        blink = False
        if self.ready_timer > 0:
            blink = int(self.ready_timer * 0.25) % 2 == 0
        if not blink:
            c.blit(surf, (int(p.x - camx - ox), int(p.y + HUD_H - oy)))

    def draw(self, screen):
        c = self.canvas
        if self.state in ("menu", "ratings"):
            self.draw_bg(c)
            ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 120))
            c.blit(ov, (0, 0))
            if self.state == "menu":
                self.draw_menu(c)
            else:
                self.draw_ratings(c)
        else:
            self.draw_bg(c)
            self.draw_world(c)
            self.draw_hud(c)
            if self.ready_timer > 0 and self.state == "playing":
                msg = "ПОЕХАЛИ!" if self.level_index == 0 else f"ЭТАП {self.level_index + 1}"
                draw_text(c, f"{msg}", self.fonts["title2"], YELLOW, center=(WIDTH // 2, HEIGHT // 2))
            if self.state == "paused":
                self.draw_overlay(c, "ПАУЗА  /  PAUZA", "Нажми P чтобы продолжить", "M — меню • bosh menyu")
            elif self.state == "gameover":
                self.draw_gameover(c)
            elif self.state == "enter_name":
                self.draw_enter_name(c)
        ox = oy = 0
        if self.shake > 0:
            m = min(self.shake, 14)
            ox, oy = random.uniform(-m, m), random.uniform(-m, m)
        screen.fill((0, 0, 0))
        screen.blit(c, (ox, oy))

    def draw_hud(self, c):
        pygame.draw.rect(c, (18, 22, 40), (0, 0, WIDTH, HUD_H))
        pygame.draw.line(c, (60, 70, 110), (0, HUD_H), (WIDTH, HUD_H), 2)
        draw_text(c, f"ОЧКИ: {self.score}", self.fonts["hud"], WHITE, topleft=(16, 12))
        draw_text(c, f"Монеты: {self.coins_got}", self.fonts["small"], GOLD, topleft=(250, 18))
        draw_text(c, f"Этап {self.level_index + 1}", self.fonts["small"], CYAN, midtop=(WIDTH // 2, 16))
        for i in range(self.lives):
            draw_heart(c, WIDTH - 28 - i * 32, HUD_H // 2, RED, 8)
        # индикатор гравитации
        gx = WIDTH - 200
        arrow = "\u2193" if self.player.gdir > 0 else "\u2191"
        draw_text(c, f"грав {arrow}", self.fonts["small"], CYAN, topleft=(gx, 18))

    def draw_menu(self, c):
        cx = WIDTH // 2
        draw_text(c, "ПЕРЕВОРОТ", self.fonts["title"], CYAN, center=(cx, 110))
        draw_text(c, "GRAVITY FLIP  •  AG'DAR", self.fonts["subtitle"], WHITE, center=(cx, 166))
        b = self.best()
        if b:
            draw_text(c, f"Рекорд / Rekord:  {b['score']} — {b['name']}", self.fonts["small"], YELLOW, center=(cx, 208))
        draw_text(c, "\u2190 \u2192 / A D — идти • yurish", self.fonts["hud"], WHITE, center=(cx, 278))
        draw_text(c, "ПРОБЕЛ / \u2191 — прыжок • sakrash", self.fonts["hud"], GREEN, center=(cx, 318))
        draw_text(c, "SHIFT / \u2193 — ПЕРЕВОРОТ (пол \u2194 потолок)", self.fonts["hud"], CYAN, center=(cx, 358))
        draw_text(c, "gravitatsiyani ag'dar — shiftda yugur!", self.fonts["small"], GREY, center=(cx, 384))
        draw_text(c, "Прыгай на врагов сверху, не касайся шипов, дойди до флага", self.fonts["small"], WHITE, center=(cx, 426))
        if int(pygame.time.get_ticks() / 450) % 2 == 0:
            draw_text(c, "Нажми ПРОБЕЛ, чтобы начать", self.fonts["hud"], GREEN, center=(cx, HEIGHT - 100))
            draw_text(c, "Boshlash uchun SPACE bosing", self.fonts["small"], GREEN, center=(cx, HEIGHT - 70))
        draw_text(c, "P — пауза   F — экран   R — рейтинг   ESC — выход",
                  self.fonts["small"], GREY, center=(cx, HEIGHT - 32))

    def draw_ratings(self, c):
        cx = WIDTH // 2
        draw_text(c, "РЕЙТИНГ  /  REYTING", self.fonts["title2"], CYAN, center=(cx, 78))
        if not self.high_scores:
            draw_text(c, "Пока нет рекордов  •  Hali rekord yo'q", self.fonts["hud"], GREY, center=(cx, HEIGHT // 2))
        else:
            rank_colors = {0: GOLD, 1: (200, 205, 215), 2: (205, 140, 80)}
            y = 165
            for i, h in enumerate(self.high_scores[:10]):
                col = rank_colors.get(i, WHITE)
                font = self.fonts["hud"] if i < 3 else self.fonts["small"]
                draw_text(c, f"{i + 1}.    {h['name']:<12}    {h['score']}", font, col, center=(cx, y))
                y += 46 if i < 3 else 38
        draw_text(c, "ESC / ПРОБЕЛ — назад  •  orqaga", self.fonts["small"], GREY, center=(cx, HEIGHT - 44))

    def draw_overlay(self, c, title, sub, extra):
        ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 150))
        c.blit(ov, (0, 0))
        cx, cy = WIDTH // 2, HEIGHT // 2
        draw_text(c, title, self.fonts["title2"], WHITE, center=(cx, cy - 30))
        draw_text(c, sub, self.fonts["small"], GREY, center=(cx, cy + 30))
        draw_text(c, extra, self.fonts["small"], CYAN, center=(cx, cy + 66))

    def draw_gameover(self, c):
        ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 175))
        c.blit(ov, (0, 0))
        cx = WIDTH // 2
        if self.won:
            draw_text(c, "ПОБЕДА!  /  G'ALABA!", self.fonts["title2"], GREEN, center=(cx, 74))
        else:
            draw_text(c, "ИГРА ОКОНЧЕНА", self.fonts["title2"], RED, center=(cx, 74))
            draw_text(c, "O'YIN TUGADI", self.fonts["subtitle"], WHITE, center=(cx, 116))
        draw_text(c, f"Очки / Hisob:  {self.score}   •   монет: {self.coins_got}",
                  self.fonts["hud"], YELLOW, center=(cx, 168))
        draw_text(c, "ЛУЧШИЕ  /  ENG YAXSHILAR", self.fonts["hud"], CYAN, center=(cx, 220))
        y = 260
        for i, h in enumerate(self.high_scores[:6]):
            col = YELLOW if i == self.last_rank else WHITE
            draw_text(c, f"{i + 1}.  {h['name']:<12}  {h['score']}", self.fonts["small"], col, center=(cx, y))
            y += 32
        if int(pygame.time.get_ticks() / 450) % 2 == 0:
            draw_text(c, "ПРОБЕЛ — снова  •  SPACE — qayta", self.fonts["small"], GREEN, center=(cx, HEIGHT - 52))
        draw_text(c, "M — меню  •  bosh menyu", self.fonts["small"], CYAN, center=(cx, HEIGHT - 24))

    def draw_enter_name(self, c):
        ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 185))
        c.blit(ov, (0, 0))
        cx = WIDTH // 2
        draw_text(c, "НОВЫЙ РЕКОРД!  /  YANGI REKORD!", self.fonts["title2"], YELLOW, center=(cx, 150))
        draw_text(c, f"Очки / Hisob:  {self.score}", self.fonts["hud"], WHITE, center=(cx, 214))
        draw_text(c, "Введи имя  •  Ismingizni kiriting:", self.fonts["hud"], CYAN, center=(cx, 288))
        cursor = "_" if int(pygame.time.get_ticks() / 350) % 2 == 0 else " "
        draw_text(c, self.name_input + cursor, self.fonts["title2"], GREEN, center=(cx, 352))
        draw_text(c, "ENTER — подтвердить  •  tasdiqlash", self.fonts["small"], GREY, center=(cx, HEIGHT - 56))


# ============================================================
#  Ввод и цикл
# ============================================================
class FakeKeys:
    def __init__(self, pressed):
        self.pressed = set(pressed)

    def __getitem__(self, k):
        return 1 if k in self.pressed else 0


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
        elif k in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
            game.do_jump()
        elif k in (pygame.K_LSHIFT, pygame.K_RSHIFT, pygame.K_DOWN, pygame.K_s):
            game.do_flip()
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
            if ch and ch.isprintable() and ch not in ("\r", "\n", "\t") and len(game.name_input) < 12:
                game.name_input += ch


def handle_keyup(game, e):
    if game.state == "playing" and e.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
        game.jump_release()


def main():
    pygame.mixer.pre_init(SR, -16, 2, 512)
    pygame.init()
    try:
        pygame.mixer.init(SR, -16, 2, 512)
        pygame.mixer.set_num_channels(16)
    except Exception:
        pass
    try:
        screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.SCALED | pygame.RESIZABLE)
    except Exception:
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Переворот / Gravity Flip")
    clock = pygame.time.Clock()
    sounds = make_sounds()
    fonts = {"title": get_font(64, bold=True), "title2": get_font(48, bold=True),
             "subtitle": get_font(30, bold=True), "hud": get_font(28, bold=True), "small": get_font(20)}
    game = Game(sounds, fonts)

    running, frame = True, 0
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
            if game.state == "playing" and frame % 30 == 0:
                events.append(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_SPACE}))
            if game.state == "playing" and frame % 50 == 0:
                events.append(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_LSHIFT}))
            if frame == 60 and game.state == "playing":
                game.coins.append([int(game.player.x // TILE), FLOOR_ROW, False])
            if frame == 80 and game.state == "playing":
                e = Enemy(int(game.player.x // TILE), FLOOR_ROW, "floor")
                e.x = game.player.x
                e.y = game.player.y + game.player.H - 4
                game.player.vy = 6
                game.player.prev_y = game.player.y
                game.enemies.append(e)
            if frame == 110 and game.state == "playing":
                game.die()
            if frame == 140 and game.state == "playing":
                game.ready_timer = 0
                game.reach_goal()         # -> этап 2
            if frame == 220 and game.state == "playing":
                game.ready_timer = 0
                game.reach_goal()         # -> победа
            if game.state == "enter_name":
                if len(game.name_input) < 3:
                    events.append(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_q, "unicode": "Q"}))
                else:
                    events.append(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN, "unicode": "\r"}))
            if game.state == "gameover":
                events.append(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_m}))

        for e in events:
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYUP:
                handle_keyup(game, e)
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

        if SMOKE:
            held = {pygame.K_RIGHT} if (frame // 40) % 4 != 3 else {pygame.K_LEFT}
            keys = FakeKeys(held)
        else:
            keys = pygame.key.get_pressed()
        game.update(dt, keys)
        game.draw(screen)
        pygame.display.flip()
        frame += 1
        if SMOKE and frame > 600:
            running = False

    pygame.quit()


if __name__ == "__main__":
    main()
