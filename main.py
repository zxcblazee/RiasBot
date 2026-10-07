# -*- coding: utf-8 -*-
"""
main.py — точка входа бота-администратора.

Что делает:
1. Валидирует конфигурацию (.env) — падает рано и с понятным текстом.
2. Создаёт commands.Bot с discord.Intents.all().
3. В setup_hook загружает коги (moderation, utility, info) и синхронизирует
   дерево слэш-команд в тестовую гильдию GUILD_ID (мгновенная регистрация —
   глобальная синхронизация может занимать до часа, для админ-бота на одном
   сервере скоуп на гильдию — разумный выбор senior'а).
4. on_error для команд: вежливый ephemeral-ответ + полный traceback в bot.log.
5. Запуск через bot.start(TOKEN) — токен только из окружения.
"""

from __future__ import annotations

import traceback
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

import config
from store import StoreRegistry
from utils import error_embed, log

# Список когов. Расширение функционала = новый файл + строка здесь.
INITIAL_COGS = ("cogs.moderation", "cogs.utility", "cogs.info")
# DxD-надстройка: игры, экономика, RPG, аниме-контент, сервер и утилиты.
DXD_COGS = ("cogs.games", "cogs.economy", "cogs.rpg", "cogs.anime",
            "cogs.server", "cogs.utilities")


class AdminBot(commands.Bot):
    """Бот-администратор. Наследуемся от commands.Bot, чтобы переопределить
    setup_hook — каноничный способ инициализации в discord.py 2.x."""

    def __init__(self) -> None:
        super().__init__(
            # Префикс не используется (все команды — слэш), но commands.Bot
            # требует его обязательным аргументом; пустое сообщение-заглушка.
            command_prefix=commands.when_mentioned,
            intents=discord.Intents.all(),
            help_command=None,  # своя /help в коге info, стандартную отключаем
            case_insensitive=True,
        )

    async def setup_hook(self) -> None:
        """Вызывается один раз перед подключением к Gateway."""
        # --- Реестр JSON-хранилищ DxD (экономика/XP/настройки...) ----------
        base_dir = getattr(config, "DATA_DIR", Path(__file__).resolve().parent)
        self.dx_stores = StoreRegistry(base_dir)
        await self.dx_stores.warm_up()

        # --- Загрузка когов -------------------------------------------------
        for cog in (*INITIAL_COGS, *DXD_COGS):
            try:
                await self.load_extension(cog)
                log.info("Ког загружен: %s", cog)
            except Exception:
                # Критично: без одного кога бот всё равно полезен, но логируем
                # traceback полностью и НЕ глушим ошибку.
                log.exception("НЕ УДАЛОСЬ загрузить ког %s", cog)

        # --- Синхронизация слэш-команд -------------------------------------
        # Регистрируем команды в конкретную гильдию -> появляются мгновенно.
        guild = discord.Object(id=config.GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        try:
            synced = await self.tree.sync(guild=guild)
            log.info("Слэш-команды синхронизированы: %d шт. в гильдии %s", len(synced), config.GUILD_ID)
        except Exception:
            log.exception("Не удалось синхронизировать слэш-команды")

    async def on_ready(self) -> None:
        """Бот подключился и готов работать."""
        log.info("Бот онлайн: %s (id=%s), на серверах: %s",
                 self.user, self.user.id, len(self.guilds))
        try:
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name="Рейтинговые игры | High School DxD | /help_dxd",
                )
            )
        except Exception:
            log.exception("Не удалось установить presence (не критично)")

    async def on_error(self, event_method: str, *args, **kwargs) -> None:
        """Последняя линия обороны для событий (кроме команд — у них свой
        обработчик ниже). Не глушим молча: полный traceback в лог."""
        log.error("Необработанная ошибка в %s:\n%s", event_method, traceback.format_exc())


bot = AdminBot()


# ---------------------------------------------------------------------------
# ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ОШИБОК СЛЭШ-КОМАНД
# ---------------------------------------------------------------------------

@bot.tree.error
async def on_app_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    """Превращает любые ошибки команд в понятный ephemeral-ответ.

    Порядок важен: сначала специфичные проверки, затем Catch-All с traceback.
    """
    if isinstance(error, app_commands.MissingPermissions):
        # п.1 требований: вежливый отказ, какие права нужны — из самого error.
        needed = ", ".join(f"`{p.replace('_', ' ')}`" for p in error.missing_permissions)
        embed = error_embed(
            f"У вас недостаточно прав для этой команды. Требуется: {needed}.",
            title="🔒 Нет прав доступа",
        )
    elif isinstance(error, app_commands.BotMissingPermissions):
        needed = ", ".join(f"`{p.replace('_', ' ')}`" for p in error.missing_permissions)
        embed = error_embed(
            f"У **бота** не хватает прав: {needed}. Обратитесь к администратору сервера.",
            title="🤖 Боту нет прав",
        )
    elif isinstance(error, app_commands.CheckFailure):
        # Прочие проверки (например, команда только на сервере).
        embed = error_embed("Эта проверка не пройдена. Возможно, команду можно использовать только на сервере.",
                            title="🔒 Доступ запрещён")
    elif isinstance(error, app_commands.CommandOnCooldown):
        embed = error_embed(f"Слишком часто! Повторите через {error.retry_after:.1f} сек.")
    else:
        # Неизвестная ошибка: пользователю — нейтрально, в лог — весь traceback.
        log.error("Необработанная ошибка команды %s (user=%s):\n%s",
                  getattr(error, "command", "?"), interaction.user,
                  "".join(traceback.format_exception(error)))
        embed = error_embed(
            "Произошла внутренняя ошибка. Модераторы уже видят её в логах. Попробуйте позже.",
            title="💥 Внутренняя ошибка",
        )

    # Команды внутри уже отвечают сами; сюда долетают только падения проверок
    # и необработанные исключения ДО ответа. Отвечаем корректно в зависимости
    # от состояния interaction.
    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    except discord.HTTPException:
        # Interaction мог истечь (поздний ответ >15 мин) — остаётся только лог.
        log.warning("Не удалось отправить ответ об ошибке: interaction истёк/недоступен")


# ---------------------------------------------------------------------------
# ЗАПУСК
# ---------------------------------------------------------------------------

def run() -> None:
    """Точка входа: валидация конфига и запуск по token из .env."""
    try:
        config.validate_config()
    except RuntimeError as e:
        # Понятное сообщение вместо стектрейса для оператора запуска.
        log.critical("Конфигурация некорректна: %s", e)
        raise SystemExit(1) from e

    try:
        # bot.start == login + connect_forever; блокирует до Ctrl+C.
        bot.run(config.DISCORD_TOKEN, log_handler=None)  # log_handler=None: логирование уже настроено в utils
    except discord.LoginFailure:
        log.critical("Неверный DISCORD_TOKEN. Проверьте значение в .env (нужен Bot token, не Public/Secret).")
        raise SystemExit(1)
    except discord.PrivilegedIntentsRequired:
        log.critical(
            "Для intents=all нужны привилегированные интенты. Включите их в "
            "Developer Portal → Bot → Privileged Gateway Intents "
            "(Server Members Intent, Message Content Intent, Presence Intent)."
        )
        raise SystemExit(1)
    except KeyboardInterrupt:
        log.info("Остановка по Ctrl+C")
    finally:
        # bot.run() сам корректно закрывает сессию aiohttp и останавливает
        # цикл — дополнительной очистки не требуется; пишем итог в лог
        # для оператора запуска.
        log.info("Бот остановлен")


if __name__ == "__main__":
    run()
