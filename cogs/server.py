# -*- coding: utf-8 -*-
"""
cogs/server.py — полезные серверные утилиты в стиле DxD (13 команд).

Всё, что нужно администрации и жизни сервера, но в лоре академии Куо:
опросы Рейтинговой игры, объявления, предложения, автостатистика,
счётчики, звёздная доска сообщений, приветствия.

Команды:
/poll /announce /suggest /serverinfo /memberinfo /roles /emojis
/counter /starboard_set /pollresult /botstats /ping /uptime
"""

from __future__ import annotations

import datetime as dt

import discord
from discord import app_commands
from discord.ext import commands

import dxd
from store import JsonStore, counter_defaults
from utils import log


class Server(commands.Cog):
    """Серверные инструменты: опросы, объявления, статистика."""

    def __init__(self, bot: commands.Bot, counters: JsonStore) -> None:
        self.bot = bot
        self.counters = counters

    # ------------------------------------------------------------------
    # 1. /poll — опрос Рейтинговой игры (кнопки Да/Нет/Воздержусь)
    # ------------------------------------------------------------------
    @app_commands.command(name="poll", description="🗳️ Создать опрос в стиле Рейтинговой игры")
    @app_commands.describe(question="Вопрос", minutes="Длительность (5–1440 мин)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def poll(self, interaction: discord.Interaction, question: str,
                   minutes: app_commands.Range[int, 5, 1440] = 60) -> None:
        try:
            ends = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=minutes)
            e = dxd.dxd_embed(
                "🗳️ ОПРОС РЕЙТИНГОВОЙ ИГРЫ",
                f"**{question[:400]}**\n\nГолосуйте реакциями!\nЗакрытие: {dxd.ts(ends)}",
                dxd.COLOR_ANGEL, gif_key="ryate")
            msg = await interaction.channel.send(embed=e)
            for emoji in ("✅", "❌", "🤝"):
                await msg.add_reaction(emoji)
            # Инкремент счётчика для достижения pollmaster
            uid = str(interaction.user.id)
            created = int(await self.bot.dx_stores.polls.get_field(uid, "created", 0))
            await self.bot.dx_stores.polls.set_field(uid, "created", created + 1)
            await interaction.response.send_message(
                embed=dxd.dxd_success("Опрос опубликован! Совет клана ждёт голосов.",
                                      title="🗳️ Голосование открыто"), ephemeral=True)
        except Exception:
            log.exception("/poll ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Урна для голосований сломана."),
                                                    ephemeral=True)

    # ------------------------------------------------------------------
    # 2. /announce — объявление от лица Мауры
    # ------------------------------------------------------------------
    @app_commands.command(name="announce", description="📢 Официальное объявление от имени клана")
    @app_commands.describe(message="Текст объявления", channel="Канал (пусто = текущий)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def announce(self, interaction: discord.Interaction, message: str,
                       channel: discord.TextChannel | None = None) -> None:
        try:
            target = channel or interaction.channel
            e = dxd.dxd_embed(
                "📢 УКАЗ ПРАВИТЕЛЯ",
                f"{message[:1800]}\n\n— обьявлено по воле {interaction.user.display_name}",
                dxd.COLOR_DEVIL, gif_key="maura")
            await target.send(content="@everyone", embed=e)
            await interaction.response.send_message(
                embed=dxd.dxd_success("Объявление разослано по всем фракциям.", title="📢 Указ издан"),
                ephemeral=True)
        except Exception:
            log.exception("/announce ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Гонец потерян."), ephemeral=True)

    # ------------------------------------------------------------------
    # 3. /suggest — предложение в канал идей
    # ------------------------------------------------------------------
    _SUGGEST_EMOJIS = ("⬆️", "⬇️", "💡")

    @app_commands.command(name="suggest", description="💡 Внести предложение в Летопись идей сервера")
    @app_commands.describe(idea="Ваша идея по улучшению сервера")
    async def suggest(self, interaction: discord.Interaction, idea: str) -> None:
        try:
            chan_id = await self.bot.dx_stores.settings.get_field(
                str(interaction.guild.id), "suggest_channel")
            channel = interaction.guild.get_channel(chan_id) if chan_id else interaction.channel
            e = dxd.dxd_embed(
                "💡 Новая идея в Летописи",
                f"*«{idea[:1500]}»* \n\nАвтор: {interaction.user.mention}\n"
                "Совет клана проголосует ⬆️/⬇️.",
                dxd.COLOR_DREAM, gif_key="asia")
            msg = await channel.send(embed=e)
            for em in self._SUGGEST_EMOJIS:
                await msg.add_reaction(em)
            await interaction.response.send_message(
                embed=dxd.dxd_success("Идея записана пером Росвисей!", title="💡 Предложение принято"),
                ephemeral=True)
        except Exception:
            log.exception("/suggest ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Перьевая ручка кончилась."),
                                                    ephemeral=True)

    # ------------------------------------------------------------------
    # 4. /serverinfo — карточка сервера
    # ------------------------------------------------------------------
    @app_commands.command(name="serverinfo", description="🏛️ Информация о сервере (крепость Куо)")
    async def serverinfo(self, interaction: discord.Interaction) -> None:
        try:
            g = interaction.guild
            boosts = getattr(g, "premium_subscription_count", 0) or 0
            e = dxd.dxd_embed(
                f"🏛️ {g.name}",
                f"Основан {dxd.ts_short(g.created_at)} • Регион: {g.region or 'unknown'}",
                dxd.COLOR_DEVIL, thumbnail=str(g.icon.url) if g.icon else None,
                fields={
                    "👥 Участников": str(g.member_count),
                    "💬 Каналов": str(len(g.text_channels) + len(g.voice_channels)),
                    "🎭 Ролей": str(len(g.roles) - 1),
                    "🚀 Бустов": f"{boosts} (ур. {g.premium_tier})",
                    "😈 Ботов": str(sum(1 for m in g.members if m.bot)),
                    "🌐 Комьюнити": str(g.large and "Большой сервер" or "Камерный клан"),
                })
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/serverinfo ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Хроника сервера недоступна."),
                                                    ephemeral=True)

    # ------------------------------------------------------------------
    # 5. /memberinfo — досье на участника
    # ------------------------------------------------------------------
    @app_commands.command(name="memberinfo", description="🔍 Досье на участника академии")
    @app_commands.describe(member="Кого рассматриваем")
    async def memberinfo(self, interaction: discord.Interaction, member: discord.Member) -> None:
        try:
            roles = sorted([r.mention for r in member.roles[1:]], key=lambda x: 0)[:8]
            status = str(member.status)
            e = dxd.dxd_embed(
                f"🔍 Досье: {member.display_name}",
                f"Аккаунт создан {dxd.ts_short(member.created_at)}\n"
                f"На сервере с {dxd.ts_short(member.joined_at)} • Статус: {status}",
                dxd.COLOR_KITONE, thumbnail=str(member.display_avatar.url),
                fields={
                    "ID": str(member.id),
                    "Роли": ", ".join(roles) if roles else "*без ролей (гражданин)*",
                    "Пикник-имя": member.discriminator if hasattr(member, "discriminator") else "0",
                })
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/memberinfo ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Шпион не вернулся."), ephemeral=True)

    # ------------------------------------------------------------------
    # 6. /roles — список ролей сервера
    # ------------------------------------------------------------------
    @app_commands.command(name="roles", description="🎭 Все роли крепости (с цветами фракций)")
    async def roles(self, interaction: discord.Interaction) -> None:
        try:
            rs = sorted(interaction.guild.roles, key=lambda r: -r.position)[:25]
            lines = [f"{r.mention} — {len(r.members)} душ" for r in rs if r.name != "@everyone"]
            e = dxd.dxd_info("\n".join(lines) or "*ролей нет*",
                             title="🎭 Реестр ролей академии", gif_key="ryate")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/roles ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Реестр сожжён Фениксом."), ephemeral=True)

    # ------------------------------------------------------------------
    # 7. /emojis — сокровищница эмодзи
    # ------------------------------------------------------------------
    @app_commands.command(name="emojis", description="😀 Каталог кастомных эмодзи сервера")
    async def emojis(self, interaction: discord.Interaction) -> None:
        try:
            custom = list(interaction.guild.emojis)
            if not custom:
                await interaction.response.send_message(
                    embed=dxd.dxd_info("Своих эмодзи нет — только стандартные печати клана.",
                                       title="😀 Сокровищница пуста"), ephemeral=True)
                return
            sample = "".join(str(em) for em in custom[:80])
            e = dxd.dxd_info(f"Всего: **{len(custom)}**\n\n{sample}",
                             title="😀 Сокровищница эмодзи", gif_key="diving")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/emojis ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Шкатулка закрыта."), ephemeral=True)

    # ------------------------------------------------------------------
    # 8. /counter — счётчик событий сервера (например «сколько раз Иссэй...»)
    # ------------------------------------------------------------------
    @app_commands.command(name="counter", description="🔢 Пользовательский счётчик (создать/изменить/показать)")
    @app_commands.describe(name="Имя счётчика", action="show|inc|dec|set|create", value="Число для set")
    @app_commands.choices(action=[
        app_commands.Choice(name="Показать", value="show"),
        app_commands.Choice(name="+1 (inc)", value="inc"),
        app_commands.Choice(name="-1 (dec)", value="dec"),
        app_commands.Choice(name="Задать число (set)", value="set"),
        app_commands.Choice(name="Создать (create)", value="create"),
    ])
    async def counter(self, interaction: discord.Interaction, name: str,
                      action: app_commands.Choice[str], value: int | None = None) -> None:
        try:
            key = f"{interaction.guild.id}:{name.lower()}"
            prof = await self.counters.get_profile(key, counter_defaults())
            if action.value == "create":
                if key in self.counters.data:
                    await interaction.response.send_message(
                        embed=dxd.dxd_error(f"Счётчик «{name}» уже существует."), ephemeral=True)
                    return
                await self.counters.set_field(key, "count", 0)
                await interaction.response.send_message(
                    embed=dxd.dxd_success(f"Счётчик **«{name}»** создан со значением 0.",
                                          title="🔢 Новый отсчёт"), ephemeral=True)
                return
            if action.value == "show":
                await interaction.response.send_message(
                    embed=dxd.dxd_info(f"🔢 **{name}**: `{prof['count']}`", title="Отсчёт хроник"))
                return
            delta = {"inc": 1, "dec": -1}.get(action.value, 0)
            new_val = value if action.value == "set" else int(prof["count"]) + delta
            await self.counters.set_field(key, "count", int(new_val))
            await interaction.response.send_message(
                embed=dxd.dxd_success(f"🔢 **{name}** → `{new_val}`", title="Счётчик обновлён"),
                ephemeral=(action.value == "set"))
        except Exception:
            log.exception("/counter ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Абacus Мауро завис."), ephemeral=True)

    # ------------------------------------------------------------------
    # 9. /starboard_set — настроить канал Звёздной Доски
    # ------------------------------------------------------------------
    @app_commands.command(name="starboard_set", description="⭐ Настроить канал Звёздной Доски сервера")
    @app_commands.describe(channel="Канал для лучших сообщений (пусто = отключить)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def starboard_set(self, interaction: discord.Interaction,
                            channel: discord.TextChannel | None = None) -> None:
        try:
            val = channel.id if channel else None
            await self.bot.dx_stores.settings.set_field(str(interaction.guild.id),
                                                        "starboard_channel", val)
            msg = (f"Звёздная Доска теперь в {channel.mention} (сообщения с ⭐≥3 будут дублироваться)."
                   if channel else "Звёздная Доска отключена.")
            await interaction.response.send_message(
                embed=dxd.dxd_success(msg, title="⭐ Starboard"), ephemeral=True)
        except Exception:
            log.exception("/starboard_set ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Небо без звёзд."), ephemeral=True)

    # ------------------------------------------------------------------
    # 10. /pollresult — итоги последнего опроса в канале (по сообщениям бота)
    # ------------------------------------------------------------------
    @app_commands.command(name="pollresult", description="📊 Показать реакции ближайшего опроса бота")
    async def pollresult(self, interaction: discord.Interaction) -> None:
        try:
            msgs = [m async for m in interaction.channel.history(limit=50)]
            poll_msg = next((m for m in msgs
                             if m.author.id == self.bot.user.id and m.embeds
                             and "ОПРОС РЕЙТИНГОВОЙ ИГРЫ" in (m.embeds[0].title or "")), None)
            if not poll_msg:
                await interaction.response.send_message(
                    embed=dxd.dxd_error("Опросов бота в этом канале не найдено (последние 50 сообщений)."),
                    ephemeral=True)
                return
            lines = []
            total = 0
            for r in poll_msg.reactions:
                count = r.count
                total += count
                lines.append(f"{r.emoji}: **{count}**")
            bar = "\n".join(lines) or "*голосов пока нет*"
            e = dxd.dxd_info(f"{bar}\n\nВсего голосов: **{total}**",
                             title=f"📊 Итоги опроса: {poll_msg.embeds[0].description.splitlines()[0][:60]}"
                                   if poll_msg.embeds[0].description else "📊 Итоги опроса",
                             gif_key="ryate")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/pollresult ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Подсчёт голосов прерван магией."),
                                                    ephemeral=True)

    # ------------------------------------------------------------------
    # 11. /botstats — техническое состояние бота
    # ------------------------------------------------------------------
    @app_commands.command(name="botstats", description="🤖 Техсостояние слуги клана (латентность, RAM-подобное)")
    async def botstats(self, interaction: discord.Interaction) -> None:
        try:
            import os
            proc = os.getpid()
            mem_kb = 0
            try:
                with open(f"/proc/{proc}/status", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("VmRSS"):
                            mem_kb = int(line.split()[1])
                            break
            except OSError:
                pass
            shards = getattr(self.bot, "shard_count", None) or 1
            e = dxd.dxd_embed(
                "🤖 Диагностика слуги",
                f"Ping: **{round(self.bot.latency * 1000)} мс** 📡\n"
                f"Память процесса: **{mem_kb // 1024} МБ**\n"
                f"Серверов под опекой: **{len(self.bot.guilds)}** • Шердов: **{shards}**",
                dxd.COLOR_DRAGON, gif_key="isma",
                fields={"API": "discord.py", "Python": __import__("sys").version.split()[0]})
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/botstats ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Диагностический гримуар молчит."),
                                                    ephemeral=True)

    # ------------------------------------------------------------------
    # 12. /ping — проверка связи
    # ------------------------------------------------------------------
    @app_commands.command(name="ping", description="🏓 Проверить, жив ли дух-хранитель сервера")
    async def ping(self, interaction: discord.Interaction) -> None:
        try:
            t0 = dt.datetime.now(dt.timezone.utc)
            ms = round((dt.datetime.now(dt.timezone.utc) - t0).total_seconds() * 1000)
            e = dxd.dxd_info(f"🏓 Понг! Отклик: **{ms} мс** • WebSocket: "
                             f"**{round(self.bot.latency * 1000)} мс**",
                             title="Связь с драконом установлена", gif_key="isma")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/ping ошибка")

    # ------------------------------------------------------------------
    # 13. /uptime — сколько бот служит клану
    # ------------------------------------------------------------------
    _started = dt.datetime.now(dt.timezone.utc)

    @app_commands.command(name="uptime", description="⏱️ Как долго бот защищает академию")
    async def uptime(self, interaction: discord.Interaction) -> None:
        try:
            delta = dt.datetime.now(dt.timezone.utc) - self._started
            secs = int(delta.total_seconds())
            d, h, m = secs // 86400, secs % 86400 // 3600, secs % 3600 // 60
            e = dxd.dxd_info(f"⏱️ На посту: **{d}д {h}ч {m}м**\n"
                             "Ни одна стена не пострадала при простое.",
                             title="Хроника бодрствования", gif_key="koneko")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/uptime ошибка")


async def setup(bot: commands.Bot) -> None:
    stores = getattr(bot, "dx_stores", None)
    if stores is None:
        raise RuntimeError("bot.dx_stores не инициализирован — проверьте main.py")
    await bot.add_cog(Server(bot, stores.counters))
