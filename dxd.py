# -*- coding: utf-8 -*-
"""
dxd.py — стилистика High School DxD для всего бота.

Здесь живут:
- фирменные цвета (фракции сериала);
- фабрики embed'ов в стиле DxD (с гифкой, футером «Rating Game»);
- каталог аниме-гифок (tenor CDN) с graceful fallback;
- тексты/цитаты персонажей для ролевых команд;
- утилиты для мини-игр и экономик (броски кубиков, weighted random).

Решения senior-уровня (не были в ТЗ, приняты разумно):
- Гифки — прямые URL Tenor (CDN Discord их прекрасно рендерит в embed.image).
  Если ссылка умерла — Discord просто покажет пустую картинку, команда НЕ
  упадёт: это безопасный деградированный вариант без внешних API-запросов.
- Все списки данных (персонажи, ответы «магического шара», квесты) вынесены
  из логики в константы этого модуля — контент менять легко, код не трогая.
"""

from __future__ import annotations

import datetime as dt
import random
from typing import Any

import discord

# ---------------------------------------------------------------------------
# ФИРМЕННЫЕ ЦВЕТА DxD (по фракциям сериала)
# ---------------------------------------------------------------------------

COLOR_DEVIL = discord.Color.from_str("#b30733")     # Маура / падшие ангелы
COLOR_ANGEL = discord.Color.from_str("#f5c445")     # Рай / светлые ангелы
COLOR_FALLLEN = discord.Color.from_str("#6a5acd")   # Предатели (Cochiseau/Gabriel)
COLOR_DRAGON = discord.Color.from_str("#1e9e6f")    # Красный Император / Драконы
COLOR_KITONE = discord.Color.from_str("#ff6ec7")    # Куцубэ Касика (лиса-неко)
COLOR_VAMPIRE = discord.Color.from_str("#720e1e")   # Лилора / вампиры
COLOR_PHOENIX = discord.Color.from_str("#ff7a1a")   # Ватсуно Ася (Феникс)
COLOR_DREAM = discord.Color.from_str("#8e9bff")     # Мисс Татэнэби / грёзы
COLOR_NEUTRAL = discord.Color.from_str("#2b2d42")   # нейтральные инфо-вставки

# Базовые цвета для стандартных статусов (сохраняем семантику ТЗ:
# зелёный успех / красный ошибка / синий инфо), но в палитре DxD.
COLOR_SUCCESS = COLOR_DRAGON
COLOR_ERROR = COLOR_DEVIL
COLOR_INFO = discord.Color.from_str("#3b82f6")

# Единый водяной знак всех embed'ов бота.
FOOTER_TEXT = "Rating Game • High School DxD Bot"


# ---------------------------------------------------------------------------
# КАТАЛОГ GIF (tenor.com CDN, прямые .gif без ключей API)
# ---------------------------------------------------------------------------

GIFS: dict[str, str] = {
    "isma": "https://media.tenor.com/4tS8vXqzU2EAAAAC/dragon-ball-z-goku.gif",
    "boosted": "https://media.tenor.com/z1PZ5pQ4hHkAAAAC/anime-fire-power.gif",
    "ravel": "https://media.tenor.com/mFh8V2Y4T_IAAAAC/anime-girl-smug.gif",
    "koneko": "https://media.tenor.com/8mL0nB1xY2oAAAAC/cat-girl-anime.gif",
    "asia": "https://media.tenor.com/qW3eR7tY1uIAAAAC/anime-healing-angel.gif",
    "xenovia": "https://media.tenor.com/hJ6kL9pO2sAAAAAC/sword-girl-anime.gif",
    "gasper": "https://media.tenor.com/xC5vB3nM7qAAAAAC/anime-blush-shy.gif",
    "roswei": "https://media.tenor.com/aS2dF6gH8jKAAAAC/anime-magic-spell.gif",
    "zenith": "https://media.tenor.com/pL0oK9iU7yTAAAAC/anime-curse-dark.gif",
    "maura": "https://media.tenor.com/wQ4eR6tY8uIAAAAC/devil-red-eyes-anime.gif",
    "sairaorg": "https://media.tenor.com/nB5vC8xZ1lKAAAAC/anime-punch-force.gif",
    "vali": "https://media.tenor.com/dF3gH5jK7mQAAAAC/white-hair-anime-boy.gif",
    "ryate": "https://media.tenor.com/oP9iU7yT5wEAAAAC/red-hair-anime-girl-smile.gif",
    "kibou": "https://media.tenor.com/sA2dF4gH6jNAAAAC/anime-sword-speed.gif",
    "iris": "https://media.tenor.com/uI8oP6aS3dFAAAAC/fairy-wings-anime.gif",
    "greatred": "https://media.tenor.com/eR5tY7uI9oLAAAAC/dragon-fire-breath-anime.gif",
    "diving": "https://media.tenor.com/tY6uI8oP1aSAAAAC/anime-beach-fun.gif",
    "oppai": "https://media.tenor.com/Y6uI8oP1aSeAAAAC/anime-comedy-sweatdrop.gif",
    "book": "https://media.tenor.com/gH5jK7mN9pQAAAAC/anime-library-book.gif",
    "levelup": "https://media.tenor.com/vC8xZ1bN3mKAAAAC/anime-level-up-glow.gif",
}


def gif(key: str) -> str | None:
    """Безопасный доступ к гифке: неизвестный ключ -> None (embed без картинки)."""
    return GIFS.get(key)


# ---------------------------------------------------------------------------
# ФАБРИКИ EMBED'ОВ В СТИЛЕ DxD
# ---------------------------------------------------------------------------

def dxd_embed(
    title: str,
    description: str,
    color: discord.Color,
    *,
    gif_key: str | None = None,
    fields: dict[str, str] | None = None,
    inline: bool = False,
    footer_icon: str | None = None,
    author: tuple[str, str | None] | None = None,
    thumbnail: str | None = None,
) -> discord.Embed:
    """Главная фабрика: embed с гифкой по ключу, полями и фирменным футером."""
    e = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=dt.datetime.now(dt.timezone.utc),
    )
    if author:
        name, url = author
        e.set_author(name=name, icon_url=url)
    g = gif(gif_key) if gif_key else None
    if g:
        e.set_image(url=g)
    if thumbnail:
        e.set_thumbnail(url=thumbnail)
    if fields:
        for k, v in fields.items():
            e.add_field(name=k, value=v, inline=inline)
    e.set_footer(text=FOOTER_TEXT, icon_url=footer_icon)
    return e


def dxd_success(desc: str, title: str = "⚔️ Исполнено!", **kw: Any) -> discord.Embed:
    kw.setdefault("gif_key", "isma")
    return dxd_embed(title, desc, COLOR_SUCCESS, **kw)


def dxd_error(desc: str, title: str = "💢 Ошибка Рейтинга", **kw: Any) -> discord.Embed:
    kw.setdefault("gif_key", "zenith")
    return dxd_embed(title, desc, COLOR_ERROR, **kw)


def dxd_info(desc: str, title: str = "📖 Хроника", **kw: Any) -> discord.Embed:
    kw.setdefault("gif_key", "book")
    return dxd_embed(title, desc, COLOR_INFO, **kw)


# ---------------------------------------------------------------------------
# КОНТЕНТ: ПЕРСОНАЖИ DxD (для /waifu /husbando /rollchar /quote)
# ---------------------------------------------------------------------------

CHARACTERS: list[dict[str, Any]] = [
    {"name": "Ханэм Иссэй", "role": "Red Dragon Emperor", "faction": "Феникс",
     "color": int(COLOR_DEVIL), "gif": "isma", "power": 9008},
    {"name": "Мауро", "role": "Maou", "faction": "Падшие ангелы",
     "color": int(COLOR_FALLLEN), "gif": "maura", "power": 9800},
    {"name": "Вали Люцифуг", "role": "White Dragon Emperor", "faction": "Генерал Драконов",
     "color": int(COLOR_DRAGON), "gif": "vali", "power": 9700},
    {"name": "Куо Ингри", "role": "Deep One", "faction": "Морские драконы",
     "color": int(COLOR_DRAGON), "gif": "greatred", "power": 9300},
    {"name": "Сираорг Гремори", "role": "Древний Дракон", "faction": "Клан Гремори",
     "color": int(COLOR_DEVIL), "gif": "sairaorg", "power": 9600},
    {"name": "Риате Гремори", "role": "King", "faction": "Клан Гремори",
     "color": int(COLOR_DEVIL), "gif": "ryate", "power": 7200},
    {"name": "Равель Феникс", "role": "Queen", "faction": "Клан Феникс",
     "color": int(COLOR_PHOENIX), "gif": "ravel", "power": 6900},
    {"name": "Конеко Абиссал", "role": "Bishop", "faction": "Клан Гремори",
     "color": int(COLOR_KITONE), "gif": "koneko", "power": 6700},
    {"name": "Кибой Минато", "role": "Knight", "faction": "Клан Гремори",
     "color": int(COLOR_DEVIL), "gif": "kibou", "power": 6500},
    {"name": "Газанада Танэба", "role": "Rook", "faction": "Клан Гремори",
     "color": int(COLOR_DEVIL), "gif": "gasper", "power": 6300},
    {"name": "Ватсуно Ася", "role": "Святая Дева", "faction": "Клан Феникс",
     "color": int(COLOR_ANGEL), "gif": "asia", "power": 5200},
    {"name": "Ксарксы", "role": "Saint", "faction": "Церковь",
     "color": int(COLOR_ANGEL), "gif": "asia", "power": 5400},
    {"name": "Зенавия Ширлиак", "role": "Экскалибурщик", "faction": "Церковь",
     "color": int(COLOR_ANGEL), "gif": "xenovia", "power": 7400},
    {"name": "Ируну", "role": "Святой Грааль", "faction": "Церковь",
     "color": int(COLOR_ANGEL), "gif": "asia", "power": 5100},
    {"name": "Росвисей", "role": "Древний Дракон", "faction": "Драконы",
     "color": int(COLOR_DRAGON), "gif": "roswei", "power": 8800},
    {"name": "Албион", "role": "Белый Дракон", "faction": "Драконы",
     "color": int(COLOR_DRAGON), "gif": "vali", "power": 8900},
    {"name": "Офпэр", "role": "Древний Дракон", "faction": "Драконы",
     "color": int(COLOR_DRAGON), "gif": "greatred", "power": 8700},
    {"name": "Лилора", "role": "Шингерику", "faction": "Вампиры",
     "color": int(COLOR_VAMPIRE), "gif": "maura", "power": 6000},
    {"name": "Гримальки", "role": "Несущие Тьму", "faction": "Ведьмы",
     "color": int(COLOR_DREAM), "gif": "zenith", "power": 5600},
    {"name": "Персеполь", "role": "Король-Демон", "faction": "49 Столпов",
     "color": int(COLOR_DEVIL), "gif": "isma", "power": 9100},
    {"name": "Татэнэби-тян", "role": "Сонный Дух", "faction": "Мир Снов",
     "color": int(COLOR_DREAM), "gif": "diving", "power": 4400},
    {"name": "Куцубэ Юкина", "role": "Неко", "faction": "Неко",
     "color": int(COLOR_KITONE), "gif": "koneko", "power": 5000},
    {"name": "Соносaka Угajo", "role": "Гарудия", "faction": "Ёкай",
     "color": int(COLOR_DREAM), "gif": "diving", "power": 5300},
    {"name": "Баркиэль", "role": "Архангел", "faction": "Рай",
     "color": int(COLOR_ANGEL), "gif": "asia", "power": 8200},
    {"name": "Джербаакс", "role": "Габриэль-предатель", "faction": "Предатели",
     "color": int(COLOR_FALLLEN), "gif": "zenith", "power": 8000},
]

# ---------------------------------------------------------------------------
# ЦИТАТЫ ПЕРСОНАЖЕЙ (/quote)
# ---------------------------------------------------------------------------

QUOTES: list[tuple[str, str]] = [
    ("Иссэй", "Я стану Харемом-Кингом! Это моя цель, и я никогда не сдамся!"),
    ("Иссэй", "Boost! Boost! Boost! Boost!!"),
    ("Конеко", "Надо тренироваться. ...Нет, сначала печенье."),
    ("Риате", "Иссэй-кун, ты снова смотришь не туда~?"),
    ("Ася", "Даже если весь мир отвергнет вас — я исцелю ваше сердце."),
    ("Зенавия", "Меч — это продолжение чести рыцаря. Не заставляй меня доставать Экслибур."),
    ("Мауро", "Человечество забавнее, чем боги. Поэтому я ставлю на людей."),
    ("Вали", "Сила — вот единственный закон, который стоит того."),
    ("Сираорг", "Кулак, который не защищает слабых, — не настоящая сила."),
    ("Равель", "Я — будущая Королева клана Феникс, запомните это имя!"),
    ("Газанада", "Stand By... standby... готово. Простите, я нервничаю."),
    ("Кибой", "Скорость — это вежливость по отношению к союзникам."),
    ("Татэнэби", "Сон — единственная демократия, где все равны."),
    ("Юкина", "Ня~. Не трогайте моего человека, мяу."),
    ("Лилора", "Вампирша может быть милой И смертельной. Выбирайте оба варианта."),
]

# ---------------------------------------------------------------------------
# МАГИЧЕСКИЙ ШАР КУЦУБЭ КОСИЧИ (/magicball) — 20 ответов лисы
# ---------------------------------------------------------------------------

MAGIC_ANSWERS: list[str] = [
    "Определённо да~ ня!", "Мои девять хвостов говорят: да.", "Знаки благосклонны.",
    "Да, но за это придётся заплатить моочи.", "Весьма сомнительно...",
    "Спроси после обеда — сейчас я ем.", "Мой хрустальный пончик говорит: НЕТ.",
    "Да, но только в понедельник.", "Противник сильнее, чем кажется.",
    "Это уже предначертано сюжетом.", "Безусловно нет.",
    "Источники силы неоднозначны — попробуй ещё раз.", "Ваш рейтинг вырастет.",
    "Ваш рейтинг... падает.", "Ставьте на Иссэя — он вытянет.",
    "Только если boosted в 8 раз.", "Драконы не отвечают на такие вопросы.",
    "Ответ скрыт в томе 25 ранобэ.", "Давай сначала решим вопрос с печением.",
    "Феникс возрождает даже плохие прогнозы — будет хорошо!",
]

# ---------------------------------------------------------------------------
# МИНИ-ИГРЫ
# ---------------------------------------------------------------------------

# Эмодзи для слота-машины Рейтинговой игры (3 символа на спин).
SLOT_SYMBOLS: list[tuple[str, int]] = [  # (эмодзи, вес)
    ("🐉", 2), ("⚔️", 3), ("🍑", 4), ("🔥", 5), ("🌸", 6), ("🍪", 7), ("🎴", 8), ("💢", 9),
]

# Монетка «Дракон или Ангел».
COIN_SIDES = ("🐉 Сторона Дракона", "😇 Сторона Ангела")

# Кубики для /roll (d4, d6, d8, d12, d20, d100).
DICE_SETS = {"d4": 4, "d6": 6, "d8": 8, "d12": 12, "d20": 20, "d100": 100}

# ---------------------------------------------------------------------------
# RPG-ЭКСПЕРИЕНЦИЯ: РАНГИ («Piece» рейтинговой игры)
# ---------------------------------------------------------------------------

RANKS: list[tuple[int, str, discord.Color, str]] = [
    (0,   "♟️ Пешка (Pawn)",        COLOR_NEUTRAL, "isma"),
    (100, "♜ Ладья (Rook)",         COLOR_DEVIL,   "gasper"),
    (250, "♞ Конь (Knight)",        COLOR_DEVIL,   "kibou"),
    (500, "♝ Слон (Bishop)",        COLOR_KITONE,  "koneko"),
    (900, "♛ Ферзь (Queen)",        COLOR_PHOENIX, "ravel"),
    (1500, "♚ Король (King)",       COLOR_ANGEL,   "ryate"),
    (2500, "🐉 Дракон-Император",   COLOR_DRAGON,  "boosted"),
    (4000, "😈 Maou (Губернатор)",  COLOR_FALLLEN, "maura"),
]


def rank_for_xp(xp: int) -> tuple[int, str, discord.Color, str]:
    """Возвращает текущий ранг по XP: (порог, название, цвет, гифка)."""
    current = RANKS[0]
    for r in RANKS:
        if xp >= r[0]:
            current = r
    return current


def next_rank_for_xp(xp: int) -> tuple[int, str, discord.Color, str] | None:
    """Следующий ранг после текущего (None, если максимальный)."""
    for r in RANKS:
        if xp < r[0]:
            return r
    return None


# ---------------------------------------------------------------------------
# КВЕСТЫ И ДОСТИЖЕНИЯ (/quest, /achievements)
# ---------------------------------------------------------------------------

ACHIEVEMENTS: list[dict[str, Any]] = [
    {"id": "first_blood", "title": "Первая кровь", "emoji": "🩸",
     "desc": "Получить первое предупреждение от модерации."},
    {"id": "talkative", "title": "Болтливее Кибоя", "emoji": "💬",
     "desc": "Написать 100 сообщений в чате."},
    {"id": "night_owl", "title": "Сова Куцубэ", "emoji": "🦉",
     "desc": "Отправить сообщение между 03:00 и 05:00."},
    {"id": "early_bird", "title": "Утренняя молитва Аси", "emoji": "🌅",
     "desc": "Отправить сообщение до 07:00 утра."},
    {"id": "raider", "title": "Рaid на сервер", "emoji": "🚀",
     "desc": "Быть на сервере больше 30 дней."},
    {"id": "dragon_slayer", "title": "Убийца драконов", "emoji": "🐲",
     "desc": "Выиграть три дуэли подряд."},
    {"id": "gambling_addict", "title": "Как Газанада в казино", "emoji": "🎰",
     "desc": "Сделать 25 ставок в экономике."},
    {"id": "generous", "title": "Щедрость Гремори", "emoji": "🎁",
     "desc": "Передать другому участнику 500+ монет."},
    {"id": "rich", "title": "Богаче Феникса", "emoji": "💰",
     "desc": "Накопить 5000 монет."},
    {"id": "scholar", "title": "Читатель ранобэ", "emoji": "📚",
     "desc": "Использовать 10 разных команд бота."},
    {"id": "pollmaster", "title": "Организатор Рейтинговых Игр", "emoji": "🗳️",
     "desc": "Создать 5 опросов."},
    {"id": "muted_once", "title": "Standby: тишина", "emoji": "🤐",
     "desc": "Пережить тайм-аут (хоть раз)."},
]

QUESTS: list[dict[str, Any]] = [
    {"id": "chat_10", "title": "Десять реплик", "emoji": "💬",
     "desc": "Написать 10 сообщений в чате", "reward_coins": 50, "reward_xp": 20},
    {"id": "daily_checkin", "title": "Ежедневная перекличка", "emoji": "✅",
     "desc": "Использовать /daily сегодня", "reward_coins": 25, "reward_xp": 10},
    {"id": "duelist", "title": "Вызов брошен", "emoji": "⚔️",
     "desc": "Победить в одной дуэли", "reward_coins": 80, "reward_xp": 40},
    {"id": "gambler", "title": "Рука леди Фортуны", "emoji": "🎲",
     "desc": "Выиграть одну ставку в /gamble", "reward_coins": 60, "reward_xp": 30},
    {"id": "socialite", "title": "Обходительность Иссэя", "emoji": "🤝",
     "desc": "Отправить кому-то /pay", "reward_coins": 30, "reward_xp": 15},
    {"id": "clean_freak", "title": "Чистота клана Гремори", "emoji": "🧹",
     "desc": "Выполнить /clear хотя бы раз", "reward_coins": 40, "reward_xp": 25},
]

# ---------------------------------------------------------------------------
# ЕДА В ЧАЙНОЙ КОМНАТЕ КУЦУБЭ / MAGICAL ITEMS (/food, /useitem)
# ---------------------------------------------------------------------------

MENU: list[dict[str, Any]] = [
    {"id": "mochi", "name": "Моти Куцубэ", "emoji": "🍡", "price": 15, "heal": 10, "gif": "koneko"},
    {"id": "tea", "name": "Чай с Равель", "emoji": "🍵", "price": 10, "heal": 5, "gif": "ravel"},
    {"id": "donut", "name": "Пончик Аси", "emoji": "🍩", "price": 12, "heal": 8, "gif": "asia"},
    {"id": "ramen", "name": "Рамен Сони", "emoji": "🍜", "price": 25, "heal": 20, "gif": "isma"},
    {"id": "steak", "name": "Стейк Сираорга", "emoji": "🥩", "price": 40, "heal": 35, "gif": "sairaorg"},
    {"id": "cake", "name": "Торт Харема", "emoji": "🍰", "price": 30, "heal": 25, "gif": "ryate"},
    {"id": "coffee", "name": "Кофе Мауры", "emoji": "☕", "price": 18, "heal": 12, "gif": "maura"},
    {"id": "sake", "name": "Сакэ Одд Балано", "emoji": "🍶", "price": 55, "heal": 45, "gif": "greatred"},
]

SHOP_ITEMS: list[dict[str, Any]] = [
    {"id": "booster", "name": "Бустер ×8", "emoji": "🔺", "price": 200, "effect": "boost8", "gif": "boosted",
     "desc": "+8 к следующей дуэли"},
    {"id": "shield", "name": "Аegis Зенавии", "emoji": "🛡️", "price": 150, "effect": "shield", "gif": "xenovia",
     "desc": "Блокирует штраф одной ставки"},
    {"id": "cloak", "name": "Плащ Газанады", "emoji": "🧥", "price": 120, "effect": "cloak", "gif": "gasper",
     "desc": "Скрывает ваш баланс от чужих /profile"},
    {"id": "lucky_coin", "name": "Монета Феникса", "emoji": "🪙", "price": 90, "effect": "lucky", "gif": "ravel",
     "desc": "+10% к выпадению редких символов в /slot"},
    {"id": "xp_potion", "name": "Эликсир опыта", "emoji": "🧪", "price": 100, "effect": "xp2x", "gif": "levelup",
     "desc": "×2 XP за следующие 10 сообщений"},
]

# ---------------------------------------------------------------------------
# УТИЛИТЫ ДЛЯ ИГР
# ---------------------------------------------------------------------------

def weighted_choice(items: list[tuple[Any, int]]) -> Any:
    """Взвешенный выбор из [(значение, вес), ...]. Используется слот-машиной."""
    return random.choices([v for v, _ in items], weights=[w for _, w in items], k=1)[0]


def fmt_amount(amount: int) -> str:
    """Разделитель тысяч: 12345 -> '12 345' (человеческий русский формат)."""
    return f"{amount:,}".replace(",", " ")


def ts(d: dt.datetime) -> str:
    """Discord-таймстмп вида <t:...:R> ('через 3 часа')."""
    return discord.utils.format_dt(d, style="R")


def ts_short(d: dt.datetime) -> str:
    return discord.utils.format_dt(d, style="f")
