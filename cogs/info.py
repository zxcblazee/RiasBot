# -*- coding: utf-8 -*-
"""
cogs/info.py — cog справочных команд.

Команды: /serverinfo /ping /help

/help собирается динамически из tree.get_commands(): список всегда актуален,
новые команды/коги подхватываются автоматически — без ручного дублирования
описаний (senior-решение: единый источник истины — сама команда).
"""

from __future__ import annotations

import time

import discord
from discord import app_commands
from discord.ext import commands

from utils import error_embed, info_embed, log


class Info(commands.Cog):
    """Справочные команды о сервере, пинге и списке команд."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ------------------------------------------------------------------
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ------------------------------------------------------------------

    @staticmethod
    async def _reply_failure(interaction: discord.Interaction, text: str) -> None:
        """Ephemeral-ошибка с учётом состояния interaction.

        Если команда уже успела ответить/сделать defer — идём через
        followup.send; иначе через response.send_message. Это защищает от
        «Interaction already responded», из-за которого настоящая ошибка
        терялась, а пользователь не видел ничего (/ping «не работал»).
        """
        embed = error_embed(text)
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.HTTPException:
            log.warning("Не удалось отправить сообщение об ошибке: interaction недоступен")

    # ------------------------------------------------------------------
    # /serverinfo
    # ------------------------------------------------------------------

    @app_commands.command(name="serverinfo", description="Статистика сервера: участники, каналы, владелец")
    async def serverinfo(self, interaction: discord.Interaction) -> None:
        try:
            guild = interaction.guild
            if guild is None:
                raise ValueError("Команда доступна только на сервере.")

            # Подсчёт участников: people vs bots (из кэша гильдии).
            members = guild.members
            humans = sum(1 for m in members if not m.bot)
            bots = len(members) - humans

            text_channels = len(guild.text_channels)
            voice_channels = len(guild.voice_channels)
            categories = len(guild.categories)

            boosts = getattr(guild, "premium_subscription_count", 0) or 0

            embed = info_embed(
                "",
                title=f"🏰 {guild.name}",
                fields={
                    "ID сервера": f"`{guild.id}`",
                    "Создан": f"<t:{int(guild.created_at.timestamp())}:F> (<t:{int(guild.created_at.timestamp())}:R>)",
                    "Владелец": f"{guild.owner.mention if guild.owner else f'`{guild.owner_id}`'}",
                    "Участники": f"Всего: **{len(members)}** • людей: {humans} • ботов: {bots}",
                    "Каналы": f"Текстовых: {text_channels} • голосовых: {voice_channels} • категорий: {categories}",
                    "Роли": str(len(guild.roles)),
                    "Бусты": f"Lv.{guild.premium_tier} • {boosts} бустов",
                    "Сообщество": "Да ✅" if getattr(guild, "community", False) else "Нет",
                },
            )
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
            await interaction.response.send_message(embed=embed)
        except ValueError as e:
            await interaction.response.send_message(embed=error_embed(str(e)), ephemeral=True)
        except Exception:
            log.exception("Ошибка в /serverinfo")
            await interaction.response.send_message(
                embed=error_embed("Произошла непредвиденная ошибка. Подробности в логах."),
                ephemeral=True,
            )

    # ------------------------------------------------------------------
    # /ping
    # ------------------------------------------------------------------

    @app_commands.command(name="ping", description="Задержка бота (WebSocket + оценка REST)")
    async def ping(self, interaction: discord.Interaction) -> None:
        try:
            # ФИКС «/ping не работает»: send_message возвращает НЕ Message, а
            # InteractionResponse — у него нет .edit(), прошлый код падал с
            # AttributeError. Правильный способ: defer() + followup.send/edit.
            await interaction.response.defer()  # «Thinking…» до 3 сек гарантированно

            ws_ms = round(self.bot.latency * 1000)

            msg = await interaction.followup.send(
                embed=info_embed("⏳ Измеряю REST-задержку…", title="🏓 Пинг"),
                wait=True,  # ждём объект сообщения, чтобы измерить честный round-trip
            )

            # Честный REST round-trip: время редактирования уже отправленного
            # сообщения (запрос к Discord API туда и обратно).
            start = time.perf_counter()
            await msg.edit(embed=info_embed("", title="🏓 Пинг"))
            rest_ms = round((time.perf_counter() - start) * 1000)

            await msg.edit(
                embed=info_embed(
                    "",
                    title="🏓 Пон!",
                    fields={
                        "WebSocket (шлюз)": f"**{ws_ms} мс**",
                        "REST API (round-trip)": f"**{rest_ms} мс**",
                    },
                    footer="WebSocket — скорость событий; REST — скорость ответов команде Discord",
                ),
            )
        except Exception:
            log.exception("Ошибка в /ping")
            # defer уже мог быть выполнен — отвечаем через followup (см. _reply_failure).
            await self._reply_failure(interaction, "Не удалось измерить задержку. Подробности в логах.")

    # ------------------------------------------------------------------
    # /help
    # ------------------------------------------------------------------

    @app_commands.command(name="help", description="Показать список всех команд бота")
    async def help_cmd(self, interaction: discord.Interaction) -> None:
        try:
            # Единый источник истины — дерево команд. Группируем по когам.
            groups: dict[str, list[tuple[str, str]]] = {}
            for cmd in self.bot.tree.get_commands():
                cog_name = getattr(cmd, "__module__", "").split(".")[-1] or "other"
                title_map = {"moderation": "🛡️ Модерация", "utility": "🧰 Утилиты", "info": "ℹ️ Информация"}
                group_title = title_map.get(cog_name, f"📦 {cog_name}")
                desc = cmd.description if isinstance(cmd.description, str) else \
                    (next(iter(cmd.description.values()), "") if isinstance(cmd.description, dict) else "")
                groups.setdefault(group_title, []).append((f"/{cmd.name}", desc))

            lines = []
            for group_title in ("🛡️ Модерация", "🧰 Утилиты", "ℹ️ Информация"):
                cmds = groups.pop(group_title, None)
                if not cmds:
                    continue
                lines.append(f"**{group_title}**")
                for name, desc in sorted(cmds):
                    lines.append(f"`{name}` — {desc}")
            # Неизвестные группы (если появятся новые коги) — тоже показываем.
            for group_title, cmds in groups.items():
                lines.append(f"**{group_title}**")
                for name, desc in sorted(cmds):
                    lines.append(f"`{name}` — {desc}")

            await interaction.response.send_message(
                embed=info_embed("\n".join(lines), title="📖 Справка по командам",
                                 footer=f"Бот: {self.bot.user.display_name} • discord.py v2"),
            )
        except Exception:
            log.exception("Ошибка в /help")
            await interaction.response.send_message(
                embed=error_embed("Произошла непредвиденная ошибка. Подробности в логах."),
                ephemeral=True,
            )


async def setup(bot: commands.Bot) -> None:
    """Загрузка кога discord.py-механикой setup_hook/load_extension."""
    await bot.add_cog(Info(bot))
