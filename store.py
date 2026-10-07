# -*- coding: utf-8 -*-
"""
store.py — асинхронное JSON-хранилище игровых/серверных данных.

Одно семейство классов GenericStore покрывает все персистентные данные
DxD-бота: экономику (монеты), XP, квесты, достижения, inventory, репутацию,
настройки сервера, уровень-роль, автоответы, приветствия и статистику команд.

Почему так (решения senior-уровня):
- Один движок с атомарной записью (temp + os.replace) вместо 10 копипаст —
  меньше кода, единая обработка битых файлов (бэкап .corrupt.bak).
- Каждый файл защищён собственным asyncio.Lock: конкурентные вызовы
  (например, /daily одновременно у двух юзеров) не повредят данные.
- Все значения plain-dict — легко читать руками и мигрировать на SQLite,
  если сервер вырастет (при 50 командах это разумный путь развития).

Структура каждого профиля: {str(user_id): {...поля...}} внутри одного файла.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from utils import log


class JsonStore:
    """Асинхронное JSON-хранилище вида dict[str, dict].

    API:
      await store.load()                - ленивая загрузка (вызывается сам)
      store.raw                         - прямой доступ (только под локом!)
      async with store.lock: ...        - для составных операций read-modify-write
      await store.save()                - атомарная запись (должна вызываться под локом)
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = asyncio.Lock()
        self._data: dict[str, dict[str, Any]] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    # ЗАГРУЗКА / СОХРАНЕНИЕ
    # ------------------------------------------------------------------

    async def load(self) -> None:
        """Ленивая загрузка файла в память (идемпотентна)."""
        if self._loaded:
            return
        try:
            if self._path.exists():
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
                if not isinstance(self._data, dict):
                    raise ValueError("Ожидался JSON-объект верхнего уровня")
            else:
                self._data = {}
        except (json.JSONDecodeError, OSError, ValueError):
            # Повреждённый файл не роняет бота: бэкапим и стартуем с чистого.
            log.exception("Файл %s повреждён — создаю резервную копию", self._path.name)
            try:
                if self._path.exists():
                    backup = self._path.with_suffix(".corrupt.bak")
                    self._path.rename(backup)
            except OSError:
                log.exception("Не удалось забэкапить %s", self._path.name)
            self._data = {}
        self._loaded = True

    def _save_sync(self) -> None:
        """Атомарная запись: temp-файл + os.replace в том же томе.
        Вызывать ТОЛЬКО внутри self._lock."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self._path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock

    @property
    def data(self) -> dict[str, dict[str, Any]]:
        """Прямой доступ к данным. Использовать только под `async with store.lock`."""
        return self._data

    async def save(self) -> None:
        async with self._lock:
            await self.load()
            self._save_sync()

    # ------------------------------------------------------------------
    # УДОБНЫЕ ОПЕРАЦИИ
    # ------------------------------------------------------------------

    async def get_profile(self, key: str | int, defaults: dict[str, Any]) -> dict[str, Any]:
        """Возвращает профиль, заполняя отсутствующие поля дефолтами.
        НЕ сохраняет — вызывающий код сам решает, когда нужен save()."""
        async with self._lock:
            await self.load()
            k = str(key)
            prof = self._data.setdefault(k, {})
            for field, value in defaults.items():
                prof.setdefault(field, value)
            return prof

    async def set_field(self, key: str | int, field: str, value: Any) -> None:
        """Разовая установка поля с сохранением (для настроечных команд)."""
        async with self._lock:
            await self.load()
            self._data.setdefault(str(key), {})[field] = value
            self._save_sync()

    async def get_field(self, key: str | int, field: str, default: Any = None) -> Any:
        async with self._lock:
            await self.load()
            return self._data.get(str(key), {}).get(field, default)

    async def drop(self, key: str | int) -> bool:
        """Удаляет профиль целиком. True, если что-то было удалено."""
        async with self._lock:
            await self.load()
            existed = self._data.pop(str(key), None) is not None
            if existed:
                self._save_sync()
            return existed


# --- Дефолтные схемы профилей ------------------------------------------------

def economy_defaults() -> dict[str, Any]:
    return {
        "coins": 100,           # стартовый капитал от клана Гремори
        "last_daily": None,     # ISO-дата последнего /daily
        "streak_days": 0,       # серия дней с /daily (бонус к выплате)
        "bets": 0,              # счётчик ставок (достижение gambling_addict)
        "wins": 0,              # выигрыши в играх
        "losses": 0,            # проигрыши
        "win_streak": 0,        # текущая серия побед в дуэлях
        "best_streak": 0,
        "inventory": {},        # {item_id: количество}
        "buff_boost": 0,        # активный бустер ×8 из магазина
        "buff_lucky": 0,        # монета феникса (кол-во использований)
        "buff_xp": 0,           # эликсир опыта (оставшиеся сообщения)
        "shield": 0,            # щит Аegis (блокирует один штраф)
        "cloak": 0,             # плащ Газанады (приватный профиль)
        "fed_today": None,      # ISO-дата последнего /feed (ежедневная кормёжка)
    }


def xp_defaults() -> dict[str, Any]:
    return {"xp": 0, "messages": 0, "last_msg": None, "commands_used": []}


def rep_defaults() -> dict[str, Any]:
    return {"given": 0, "received": 0}


def guild_settings_defaults() -> dict[str, Any]:
    return {
        "welcome_channel": None,   # ID канала приветствий
        "welcome_message": None,   # текст (пусто = стандартный DxD-текст)
        "leave_message": None,
        "levelup_channel": None,   # куда писать о повышениях ранга
        "level_role_id": None,     # выдаваемая роль «Рыцарь» и т.п.
        "autorole_enabled": False,
        "autorole_ids": [],        # до 3 ролей по умолчанию при входе
        "announcements_channel": None,
        "suggest_channel": None,
        "mod_mail_channel": None,
        "starboard_channel": None,
        "raid_mode": False,
        "muted_role_id": None,
        "log_channel": None,       # локальный дубль LOG_CHANNEL_ID из .env
    }


def counter_defaults() -> dict[str, Any]:
    return {"count": 0, "paused": False}


def ticket_defaults() -> dict[str, Any]:
    return {"tickets": [], "next_id": 1}


def poll_stats_defaults() -> dict[str, Any]:
    return {"created": 0}


class StoreRegistry:
    """Единая точка доступа ко всем хранилищам бота.

    Создаётся один раз в main.py и передаётся в коги через bot.dx_stores.
    """

    def __init__(self, base_dir: Path) -> None:
        d = base_dir / "data"
        self.economy = JsonStore(d / "economy.json")
        self.xp = JsonStore(d / "xp.json")
        self.rep = JsonStore(d / "rep.json")
        self.settings = JsonStore(d / "guild_settings.json")
        self.counters = JsonStore(d / "counters.json")
        self.tickets = JsonStore(d / "tickets.json")
        self.autoreplies = JsonStore(d / "autoreplies.json")
        self.starboard = JsonStore(d / "starboard.json")
        self.achievements = JsonStore(d / "achievements.json")
        self.stats = JsonStore(d / "stats.json")          # статистика команд
        self.notes = JsonStore(d / "notes.json")          # личные заметки модераторов
        self.polls = JsonStore(d / "poll_stats.json")     # кол-во опросов (достижение)
        self.reminders = JsonStore(d / "reminders.json")  # отложенные напоминания
        self.giveaways = JsonStore(d / "giveaways.json")  # активные розыгрыши

    async def warm_up(self) -> None:
        """Прогревает все хранилища при старте — чтобы первая команда не ждала диск."""
        stores = [
            self.economy, self.xp, self.rep, self.settings, self.counters,
            self.tickets, self.autoreplies, self.starboard, self.achievements, self.stats,
            self.notes, self.polls, self.reminders, self.giveaways,
        ]
        await asyncio.gather(*(s.load() for s in stores))
        log.info("Хранилища DxD прогреты: %d файлов", len(stores))


__all__ = ["JsonStore", "StoreRegistry", "economy_defaults", "xp_defaults",
           "rep_defaults", "guild_settings_defaults", "counter_defaults",
           "ticket_defaults", "poll_stats_defaults"]
