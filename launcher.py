# -*- coding: utf-8 -*-
"""
MINI O'YINLAR — LAUNCHER (bosh menyu)
=====================================
Bitta dastur ichida bir nechta o'yin. Ishga tushiring → o'yinlar ro'yxati chiqadi →
birини tanlang va o'ynang. Istalgan paytda o'yindan chiqsangiz (o'yin menyusida ESC)
yana shu ro'yxatga qaytasiz va boshqa o'yin tanlay olasiz.

Ishga tushirish:   python launcher.py
Kerak:             pip install pygame numpy   (numpy — faqat ovoz uchun)

Boshqaruv (ro'yxatda):
    ↑ / ↓  yoki  W / S    — tanlash
    ENTER / SPACE          — o'ynash
    Sichqoncha             — ustiga olib borib bosish
    ESC                    — chiqish

Yangi o'yin qo'shish:  pastdagi GAMES ro'yxatiga bitta element qo'shing — tamom.
"""

import sys
import os
import json
import math

try:
    import pygame
except ImportError:
    print("pygame kerak:  pip install pygame")
    sys.exit(1)

# O'yin modullari (har biri o'z main() funksiyasiga ega)
import platformer
import space_game


# ============================================================
#  SOZLAMALAR
# ============================================================
WIDTH, HEIGHT = 1000, 720
FPS = 60

# --- Ranglar ---
BG_TOP = (8, 10, 32)
BG_BOTTOM = (20, 8, 40)
WHITE = (240, 244, 255)
GREY = (150, 160, 185)
CARD = (28, 32, 60)
CARD_HOVER = (40, 46, 84)

# O'yinlar ro'yxati — YANGI O'YIN QO'SHISH UCHUN shu ro'yxatga element qo'shing.
# "title"/"subtitle" — ikki tilli: {"uz": ..., "ru": ...}.
# "run" — o'yinning main() funksiyasi (pygame oynasini o'zi ochib-yopadi).
GAMES = [
    {
        "title": {"uz": "KOSMIK JANG", "ru": "КОСМИЧЕСКИЙ БОЙ"},
        "subtitle": {
            "uz": "Kosmik kemada dushmanlarni otib tushiring",
            "ru": "Сбивайте врагов на космическом корабле",
        },
        "run": space_game.main,
        "accent": (90, 200, 255),
        "icon": "ship",
    },
    {
        "title": {"uz": "AG'DAR", "ru": "ПЕРЕВОРОТ"},
        "subtitle": {
            "uz": "Gravitatsiyani ag'darib o'ynaydigan platformer",
            "ru": "Платформер с переворотом гравитации",
        },
        "run": platformer.main,
        "accent": (255, 170, 70),
        "icon": "flip",
    },
]

# Interfeys matnlari (ikki tilda)
STR = {
    "uz": {
        "title": "MINI O'YINLAR",
        "pick": "o'yinni tanlang",
        "play": "▶ O'YNASH",
        "exit": "Chiqish",
        "hint": "↑ ↓ tanlash    ENTER o'ynash    L — til    sichqoncha bilan ham    ESC chiqish",
    },
    "ru": {
        "title": "МИНИ-ИГРЫ",
        "pick": "выберите игру",
        "play": "▶ ИГРАТЬ",
        "exit": "Выход",
        "hint": "↑ ↓ выбор    ENTER играть    L — язык    можно мышкой    ESC выход",
    },
}
LANGS = ["uz", "ru"]
# ============================================================


def _settings_file():
    base = os.path.join(os.path.expanduser("~"), ".mini_oyinlar")
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:
        pass
    return os.path.join(base, "launcher.json")


def load_lang():
    """Saqlangan tilni o'qiydi (yo'q bo'lsa — 'uz')."""
    try:
        with open(_settings_file(), "r", encoding="utf-8") as f:
            lang = json.load(f).get("lang")
            if lang in LANGS:
                return lang
    except Exception:
        pass
    return "uz"


def save_lang(lang):
    """Tanlangan tilni eslab qoladi (keyingi ishga tushirishda ham)."""
    try:
        with open(_settings_file(), "w", encoding="utf-8") as f:
            json.dump({"lang": lang}, f)
    except Exception:
        pass


def get_font(size, bold=False):
    """Tizim fonti (kirill + lotin uchun), bo'lmasa pygame default."""
    try:
        f = pygame.font.SysFont(
            "arialroundedmtbold,arialunicodems,arial,helvetica,dejavusans,sans",
            size, bold=bold)
        if f is not None:
            return f
    except Exception:
        pass
    return pygame.font.Font(None, size)


def draw_text(surf, text, font, color, center=None, topleft=None,
              midtop=None, shadow=True):
    if shadow:
        sh = font.render(text, True, (0, 0, 0))
        r = sh.get_rect()
        if center:
            r.center = (center[0] + 2, center[1] + 2)
        elif topleft:
            r.topleft = (topleft[0] + 2, topleft[1] + 2)
        elif midtop:
            r.midtop = (midtop[0] + 2, midtop[1] + 2)
        surf.blit(sh, r)
    img = font.render(text, True, color)
    r = img.get_rect()
    if center:
        r.center = center
    elif topleft:
        r.topleft = topleft
    elif midtop:
        r.midtop = midtop
    surf.blit(img, r)
    return r


def make_stars(n=130):
    """Fon uchun yulduzlar: [x, y, radius, miltillash_fazasi, tezlik]."""
    import random
    stars = []
    for _ in range(n):
        stars.append([
            random.randint(0, WIDTH),
            random.randint(0, HEIGHT),
            random.choice([1, 1, 1, 2, 2, 3]),
            random.uniform(0, math.tau),
            random.uniform(0.4, 1.4),
        ])
    return stars


def draw_background(surf, stars, t):
    # Vertikal gradient
    for y in range(0, HEIGHT, 2):
        k = y / HEIGHT
        c = (
            int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * k),
            int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * k),
            int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * k),
        )
        pygame.draw.line(surf, c, (0, y), (WIDTH, y), 2)
    # Yulduzlar (miltillaydi)
    for s in stars:
        x, y, r, ph, sp = s
        glow = 0.55 + 0.45 * math.sin(t * sp + ph)
        v = int(120 + 135 * glow)
        col = (v, v, min(255, v + 20))
        if r >= 3:
            pygame.draw.circle(surf, col, (int(x), int(y)), r)
        else:
            surf.set_at((int(x), int(y)), col)
            if r == 2:
                surf.set_at((int(x) + 1, int(y)), col)


def draw_icon(surf, kind, cx, cy, color, scale=1.0):
    """Kichik dekorativ ikona (har bir o'yin uchun)."""
    s = scale
    if kind == "ship":
        pts = [(cx, cy - 18 * s), (cx - 14 * s, cy + 14 * s),
               (cx, cy + 7 * s), (cx + 14 * s, cy + 14 * s)]
        pygame.draw.polygon(surf, color, pts)
        pygame.draw.circle(surf, WHITE, (int(cx), int(cy - 2 * s)), int(4 * s))
    elif kind == "flip":
        # gravitatsiya ag'darish: ikki strelka (yuqori/past)
        pygame.draw.polygon(surf, color, [
            (cx, cy - 16 * s), (cx - 10 * s, cy - 2 * s), (cx + 10 * s, cy - 2 * s)])
        pygame.draw.polygon(surf, color, [
            (cx, cy + 16 * s), (cx - 10 * s, cy + 2 * s), (cx + 10 * s, cy + 2 * s)])
    else:
        pygame.draw.circle(surf, color, (int(cx), int(cy)), int(14 * s), 3)


def run_menu():
    """Bosh menyuni ko'rsatadi. Tanlangan o'yin indeksini (int) yoki
    chiqish uchun None ni qaytaradi. selected — boshlang'ich kursor."""
    pygame.init()
    try:
        screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.SCALED | pygame.RESIZABLE)
    except Exception:
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Mini O'yinlar / Мини-игры")
    clock = pygame.time.Clock()

    fonts = {
        "title": get_font(74, bold=True),
        "card": get_font(40, bold=True),
        "sub": get_font(24),
        "hint": get_font(22),
        "tag": get_font(20, bold=True),
        "lang": get_font(22, bold=True),
    }
    stars = make_stars()
    lang = load_lang()          # joriy til ("uz" / "ru"), o'tgan tanlovdan

    # Ro'yxat elementlari: o'yinlar + "Chiqish"
    n_games = len(GAMES)
    n_items = n_games + 1            # oxirgisi = Chiqish
    selected = run_menu.last_selected if hasattr(run_menu, "last_selected") else 0
    selected = max(0, min(selected, n_items - 1))

    # Kartalar joylashuvi
    card_w = 720
    card_h = 116
    gap = 26
    top = 250
    card_x = (WIDTH - card_w) // 2

    def item_rect(i):
        if i < n_games:
            return pygame.Rect(card_x, top + i * (card_h + gap), card_w, card_h)
        # Chiqish tugmasi (kichikroq)
        y = top + n_games * (card_h + gap) + 10
        bw = 240
        return pygame.Rect((WIDTH - bw) // 2, y, bw, 60)

    # Til tugmalari (yuqori o'ng burchak): UZ | RU
    lang_w, lang_h = 54, 40
    lang_rects = {
        "uz": pygame.Rect(WIDTH - 24 - lang_w * 2 - 8, 26, lang_w, lang_h),
        "ru": pygame.Rect(WIDTH - 24 - lang_w, 26, lang_w, lang_h),
    }

    def set_lang(new):
        nonlocal lang
        if new in LANGS and new != lang:
            lang = new
            save_lang(lang)

    t = 0.0
    while True:
        dt = clock.tick(FPS) / 1000.0
        t += dt
        mouse = pygame.mouse.get_pos()

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return None
            elif e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_DOWN, pygame.K_s):
                    selected = (selected + 1) % n_items
                elif e.key in (pygame.K_UP, pygame.K_w):
                    selected = (selected - 1) % n_items
                elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    run_menu.last_selected = selected
                    return None if selected >= n_games else selected
                elif e.key == pygame.K_ESCAPE:
                    return None
                elif e.key == pygame.K_l:        # tilni almashtirish (uz <-> ru)
                    set_lang(LANGS[(LANGS.index(lang) + 1) % len(LANGS)])
                elif e.key == pygame.K_f:
                    try:
                        pygame.display.toggle_fullscreen()
                    except Exception:
                        pass
                # Raqam bilan tez tanlash (1, 2, ...)
                elif pygame.K_1 <= e.key <= pygame.K_9:
                    idx = e.key - pygame.K_1
                    if idx < n_games:
                        run_menu.last_selected = idx
                        return idx
            elif e.type == pygame.MOUSEMOTION:
                for i in range(n_items):
                    if item_rect(i).collidepoint(mouse):
                        selected = i
                        break
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                # Avval til tugmalari bosildimi tekshiramiz
                hit_lang = False
                for code, rect in lang_rects.items():
                    if rect.collidepoint(mouse):
                        set_lang(code)
                        hit_lang = True
                        break
                if not hit_lang:
                    for i in range(n_items):
                        if item_rect(i).collidepoint(mouse):
                            run_menu.last_selected = i
                            return None if i >= n_games else i

        tr = STR[lang]

        # --- Chizish ---
        draw_background(screen, stars, t)

        # Sarlavha
        bob = math.sin(t * 1.6) * 4
        draw_text(screen, tr["title"], fonts["title"], WHITE,
                  center=(WIDTH // 2, 110 + bob))
        draw_text(screen, tr["pick"], fonts["sub"], GREY,
                  center=(WIDTH // 2, 168))

        # Til tugmalari (UZ | RU) — faol til yashil chegarali
        for code, rect in lang_rects.items():
            active = (code == lang)
            pygame.draw.rect(screen, CARD_HOVER if active else CARD, rect, border_radius=10)
            bc = (120, 220, 140) if active else (70, 76, 110)
            pygame.draw.rect(screen, bc, rect, width=2, border_radius=10)
            draw_text(screen, code.upper(), fonts["lang"],
                      WHITE if active else GREY, center=rect.center, shadow=False)

        # O'yin kartalari
        for i, g in enumerate(GAMES):
            r = item_rect(i)
            hovered = (i == selected)
            base = CARD_HOVER if hovered else CARD
            # Tanlangan kartani biroz kattalashtirish hissi: yorqin chegara
            panel = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
            pygame.draw.rect(panel, (*base, 235), panel.get_rect(), border_radius=18)
            screen.blit(panel, r.topleft)
            border_c = g["accent"] if hovered else (60, 66, 100)
            pygame.draw.rect(screen, border_c, r, width=3 if hovered else 2,
                             border_radius=18)

            # Tartib raqami
            num_c = g["accent"]
            draw_text(screen, str(i + 1), fonts["card"], num_c,
                      center=(r.x + 46, r.centery))
            # Ikona
            draw_icon(screen, g["icon"], r.x + 110, r.centery, g["accent"],
                      scale=1.15 if hovered else 1.0)
            # Matn (joriy tilda)
            draw_text(screen, g["title"][lang], fonts["card"], WHITE,
                      topleft=(r.x + 150, r.y + 26))
            draw_text(screen, g["subtitle"][lang], fonts["sub"], GREY,
                      topleft=(r.x + 152, r.y + 72), shadow=False)
            # "O'YNASH / ИГРАТЬ" yorlig'i (hover bo'lganda)
            if hovered:
                draw_text(screen, tr["play"], fonts["tag"], g["accent"],
                          midtop=(r.right - 80, r.y + 14))

        # Chiqish tugmasi
        er = item_rect(n_games)
        ex_hover = (selected == n_games)
        ec = (255, 110, 110) if ex_hover else (90, 96, 130)
        pygame.draw.rect(screen, CARD_HOVER if ex_hover else CARD, er, border_radius=14)
        pygame.draw.rect(screen, ec, er, width=2, border_radius=14)
        draw_text(screen, tr["exit"], fonts["card"], ec if ex_hover else GREY,
                  center=er.center)

        # Pastki ko'rsatma
        draw_text(screen, tr["hint"], fonts["hint"], GREY,
                  center=(WIDTH // 2, HEIGHT - 28), shadow=False)

        pygame.display.flip()


def main():
    """Asosiy halqa: menyu → o'yin → menyu → ...
    O'yin tugaganda (uning menyusida ESC bosilsa yoki oyna yopilsa) bu yerga
    qaytadi va ro'yxat yana ko'rsatiladi."""
    while True:
        choice = run_menu()
        if choice is None:
            break
        try:
            # O'yin o'z pygame oynasini ochadi va chiqishda pygame.quit() qiladi.
            GAMES[choice]["run"]()
        except SystemExit:
            # O'yin sys.exit() chaqirsa — butun dasturni yopmaymiz, menyuga qaytamiz.
            pass
        except Exception as ex:
            # Bitta o'yin xato bersa ham launcher yiqilmasin.
            print("O'yin xatosi:", repr(ex))
    pygame.quit()


if __name__ == "__main__":
    main()
