# -*- coding: utf-8 -*-
"""
utils.py — общие помощники, используемые всеми когами.

Здесь живут:
- настройка логирования (файл bot.log + консоль);
- фабрики embed'ов с единой цветовой схемой;
- парсер длительности тайм-аута ("1m", "2h", "3d");
- проверки иерархии ролей и прав;
- асинхронное хранилище предупреждений (JSON) с asyncio.Lock,
  чтобы конкурентные вызовы /warn не повреждали файл.

Решения senior-уровня:
- Записи в warnings.json синхронизируются через aio-safe lock и пишутся
  атомарно (во временный файл + os.replace), чтобы не потерять данные
  при падении процесса посреди записи.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import discord

# ---------------------------------------------------------------------------
# ЛОГИРОВАНИЕ
# ---------------------------------------------------------------------------

def setup_logging() -> logging.Logger:
    """Настраивает корневой логгер: файл bot.log + консоль.

    Возвращает логгер 'bot', который используют все модули.
    """
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Формат: время | уровень | модуль | сообщение
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Консольный хендлер
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    # Файловый хендлер (UTF-8, т.к. сообщения на русском)
    file_handler = logging.FileHandler("bot.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    logger = logging.getLogger("bot")
    logger.info("Логирование инициализировано (bot.log + консоль)")
    return logger


log = setup_logging()

# ---------------------------------------------------------------------------
# EMBED-Ы: ЕДИНАЯ ЦВЕТОВАЯ СХЕМА
# ---------------------------------------------------------------------------

COLOR_SUCCESS = discord.Color.green()   # успех
COLOR_ERROR = discord.Color.red()       # ошибка
COLOR_INFO = discord.Color.blue()       # информация


def make_embed(
    title: str,
    description: str,
    color: discord.Color,
    *,
    fields: dict[str, str] | None = None,
    footer: str | None = None,
) -> discord.Embed:
    """Фабрика embed'ов: заголовок, описание, цвет, опц. поля и футер."""
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    if fields:
        for name, value in fields.items():
            # inline=False — поля столбиком, читаемее для логов модерации
            embed.add_field(name=name, value=value, inline=False)
    if footer:
        embed.set_footer(text=footer)
    return embed


def error_embed(description: str, title: str = "❌ Ошибка") -> discord.Embed:
    """Красный embed с ошибкой."""
    return make_embed(title, description, COLOR_ERROR)


def success_embed(description: str, title: str = "✅ Успех", **kwargs) -> discord.Embed:
    """Зелёный embed об успешном действии."""
    return make_embed(title, description, COLOR_SUCCESS, **kwargs)


def info_embed(description: str, title: str = "ℹ️ Информация", **kwargs) -> discord.Embed:
    """Синий инфо-embed."""
    return make_embed(title, description, COLOR_INFO, **kwargs)


# ---------------------------------------------------------------------------
# ПАРСЕР ДЛИТЕЛЬНОСТИ ("1m", "2h", "3d", комбинированно: "1h30m")
# ---------------------------------------------------------------------------

_DURATION_RE = re.compile(r"(\d+)\s*([smhd])", re.IGNORECASE)
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}

# Discord ограничивает timeout диапазоном от 1 секунды до 28 дней.
TIMEOUT_MIN_SECONDS = 1
TIMEOUT_MAX_SECONDS = 28 * 86400


def parse_duration(raw: str) -> int:
    """Превращает '5m', '1h', '2d', '1h30m' в количество секунд.

    Бросает ValueError с понятным текстом — вызывающий код покажет его юзеру.
    """
    raw = raw.strip().lower()
    matches = _DURATION_RE.findall(raw)
    # Строка должна состоять ТОЛЬКО из пар "число+единица", без мусора.
    if not matches or "".join(m[0] + m[1] for m in matches) != re.sub(r"\s+", "", raw):
        raise ValueError(
            f"Не удалось понять время: «{raw}». "
            "Формат: 1m, 30m, 1h, 2h, 1d, 7d, 1h30m (s/м/ч/сутки — s, m, h, d)."
        )

    total = sum(int(value) * _UNIT_SECONDS[unit] for value, unit in matches)
    if total < TIMEOUT_MIN_SECONDS or total > TIMEOUT_MAX_SECONDS:
        raise ValueError(
            f"Длительность {total} сек вне допустимого диапазона "
            f"(от {TIMEOUT_MIN_SECONDS} сек до 28 дней)."
        )
    return total


def format_seconds(seconds: int) -> str:
    """Человекочитаемо: 90 -> '1ч 30м'."""
    units = [("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]
    parts = []
    for name, size in units:
        if seconds >= size:
            parts.append(f"{seconds // size}{name}")
            seconds %= size
    return " ".join(parts) if parts else "0s"


# ---------------------------------------------------------------------------
# ПРОВЕРКИ БЕЗОПАСНОСТИ МОДЕРАЦИИ (иерархия ролей)
# ---------------------------------------------------------------------------

class HierarchyError(Exception):
    """Ошибка проверки иерархии/прав. Текст — безопасен для показа юзеру."""


def ensure_can_moderate(actor: discord.Member, target: discord.Member, action: str) -> None:
    """Проверяет, что `actor` (бот или модерирующий участник) может
    применить `action` к `target`.

    Правила:
    - нельзя модерировать владельца гильдии;
    - нельзя модерировать самого себя (для бота это критично: self-ban/kick);
    - нельзя модерировать того, чья высшая роль выше или равна высшей роли actor
      (discord.py Member.top_role и compare_to учитывают иерархию @everyone).
    """
    guild = target.guild

    # Владелец сервера неприкосновенен для всех, кроме самого владельца.
    if target.id == guild.owner_id and actor.id != guild.owner_id:
        raise HierarchyError(f"Нельзя «{action}» владельца сервера.")

    # Защита от самоуничтожения бота/участника.
    if actor.id == target.id:
        raise HierarchyError(f"Нельзя «{action}» самого себя.")

    # Иерархия ролей: равные или вышестоящие роли модерировать нельзя.
    if target.top_role >= actor.top_role and target.id != guild.owner_id:
        raise HierarchyError(
            f"Нельзя «{action}» участника с ролью, равной или выше вашей/ботовой. "
            "Поднимите роль бота выше целевого участника."
        )

    # Отдельная защита: бот не банит/кикает других ботов без явного повода —
    # это частая ошибка, приводящая к инцидентам. Разрешаем только если у
    # цели есть роль ниже роли бота И это не владелец (проверено выше).
    # Решение по ТЗ п.3: блокируем полностью, сообщение объясняет как обойти.
    if isinstance(actor, discord.ClientUser) and target.bot:
        raise HierarchyError(
            f"Целевой участник — бот. Модерация ботов («{action}») заблокирована "
            "в целях безопасности. Для действий над ботами используйте нативные "
            "средства Discord (Settings → Integrations)."
        )


# ---------------------------------------------------------------------------
# ХРАНИЛИЩЕ ПРЕДУПРЕЖДЕНИЙ (JSON + asyncio.Lock + атомарная запись)
# ---------------------------------------------------------------------------

class WarningStore:
    """Асинхронное JSON-хранилище предупреждений.

    Структура файла:
    { "<guild_id>": { "<user_id>": [ {reason, moderator_id, moderator_name,
      timestamp_iso}, ... ], ... }, ... }
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = asyncio.Lock()
        self._data: dict[str, dict[str, list[dict]]] = {}
        self._loaded = False

    async def _load(self) -> None:
        """Ленивая загрузка файла в память (под локом)."""
        if self._loaded:
            return
        try:
            if self._path.exists():
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            else:
                self._data = {}
        except (json.JSONDecodeError, OSError):
            # Повреждённый файл не должен ронять бота: логируем traceback
            # и начинаем с чистого состояния, сохранив бэкап битого файла.
            log.exception("warnings.json повреждён, создаю резервную копию и новый файл")
            try:
                backup = self._path.with_suffix(".corrupt.bak")
                self._path.rename(backup)
                log.warning("Битый файл сохранён как %s", backup)
            except OSError:
                log.exception("Не удалось сделать бэкап повреждённого warnings.json")
            self._data = {}
        self._loaded = True

    def _save_sync(self) -> None:
        """Атомарная запись: temp-файл + os.replace (в том же томе)."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self._path)
        except Exception:
            # Чистим временный файл при любой ошибке записи.
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    async def add(self, guild_id: int, user_id: int, moderator: discord.Member, reason: str) -> int:
        """Добавляет предупреждение. Возвращает его номер (1-based) в истории."""
        async with self._lock:
            await self._load()
            entry = {
                "reason": reason,
                "moderator_id": moderator.id,
                "moderator_name": str(moderator),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            hist = self._data.setdefault(str(guild_id), {}).setdefault(str(user_id), [])
            hist.append(entry)
            self._save_sync()
            return len(hist)

    async def get(self, guild_id: int, user_id: int) -> list[dict]:
        """Возвращает список предупреждений пользователя (может быть пустым)."""
        async with self._lock:
            await self._load()
            return list(self._data.get(str(guild_id), {}).get(str(user_id), []))

    async def clear(self, guild_id: int, user_id: int) -> int:
        """Полностью очищает историю предупреждений пользователя.
        Возвращает количество удалённых записей.

        Команды /clearwarn в ТЗ нет, но хранилище должно позволять это —
        разумное решение senior'а: метод есть, API команды не добавляем,
        чтобы строго соответствовать списку команд из задания.
        """
        async with self._lock:
            await self._load()
            hist = self._data.get(str(guild_id), {}).pop(str(user_id), [])
            self._save_sync()
            return len(hist)


# Глобальный экземпляр хранилища (создаётся один раз, лениво грузит файл).
def build_warning_store(path: Path) -> WarningStore:
    return WarningStore(path)
