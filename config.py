# -*- coding: utf-8 -*-
"""
config.py — единая точка загрузки конфигурации из .env.

Никаких хардкод-токенов в коде! Все секреты читаются только из
переменных окружения (файл .env, python-dotenv).

Решения senior-уровня (приняты разумно, т.к. не были указаны в ТЗ):
- LOG_CHANNEL_ID и WARNINGS_FILE необязательны: если канал логов не задан,
  бот просто не пишет модерационные логи (п.7 требований к качеству).
- Файл предупреждений лежит в data/warnings.json — чтобы код и данные
  были разделены.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Загружаем .env из корня проекта. load_dotenv() безопасен: если файла нет,
# он ничего не делает, а дальнейшая валидация даст понятную ошибку.
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# --- Обязательные настройки -------------------------------------------------
DISCORD_TOKEN: str | None = os.getenv("DISCORD_TOKEN")
GUILD_ID: int | None = int(os.environ["GUILD_ID"]) if os.getenv("GUILD_ID", "").isdigit() else None

# --- Необязательные настройки -----------------------------------------------
# Канал для логов модерации. Если не задан или не число — логи не пишутся.
_raw_log_channel = os.getenv("LOG_CHANNEL_ID", "")
LOG_CHANNEL_ID: int | None = int(_raw_log_channel) if _raw_log_channel.isdigit() else None

# Файл хранения предупреждений.
WARNINGS_FILE: Path = BASE_DIR / "data" / "warnings.json"


def validate_config() -> None:
    """Проверяет обязательные переменные при старте.

    Падаем сразу с понятным сообщением, а не с cryptic KeyError в рантайме.
    """
    missing = []
    if not DISCORD_TOKEN:
        missing.append("DISCORD_TOKEN")
    if GUILD_ID is None:
        missing.append("GUILD_ID")

    if missing:
        raise RuntimeError(
            "Не заданы обязательные переменные окружения: "
            + ", ".join(missing)
            + ". Скопируйте .env.example в .env и заполните значения."
        )
