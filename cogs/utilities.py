# -*- coding: utf-8 -*-
"""
cogs/utilities.py — бытовые утилиты сервера в стиле DxD (12 команд).

Повседневные инструменты, которые «по твоему будут полезны боту»:
заметки на потом, калькулятор силы, таймер тренировки, цветовой пикер,
список желаний, автоответы чайной, цитатник правил.

Команды:
/reminder /reminders /cancelreminder /calc /timer /color /wishes
/wishdel /rules /help_dxd /avatar /servericon /snowflake
"""

from __future__ import annotations

import asyncio
import datetime as dt
import re

import discord
from discord import app_commands
from discord.ext import commands, tasks

import dxd
from utils import log


class Utilities(commands.Cog):
    """Полезные мелочи повседневности академии Куо."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._timers: dict[int, asyncio.TimerHandle] = {}

    # ------------------------------------------------------------------
    # 1. /reminder — напомнить мне через время
    # ------------------------------------------------------------------
    @app_commands.command(name="reminder", description="⏰ Напомнить мне о чём-то через N минут")
    @app_commands.describe(text="О чём напомнить", minutes="Через сколько минут (1–1440)")
    async def reminder(self, interaction: discord.Interaction, text: str,
                       minutes: app_commands.Range[int, 1, 1440]) -> None:
        try:
            when = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=minutes)
            entry = {"user": interaction.user.id, "channel": interaction.channel_id,
                     "text": text[:300], "when": when.isoformat()}
            key = str(interaction.user.id)
            lst = await self.bot.dx_stores.reminders.get_field(key, "list", []) or []
            lst.append(entry)
            await self.bot.dx_stores.reminders.set_field(key, "list", lst)
            await interaction.response.send_message(
                embed=dxd.dxd_success(f"⏰ Напомню {dxd.ts(when)}: *{text[:120]}*",
                                      title="Запись в Гримуар памяти", gif_key="gasper"),
                ephemeral=True)
        except Exception:
            log.exception("/reminder ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Память отказалась записывать."),
                                                    ephemeral=True)

    # ------------------------------------------------------------------
    # 2. /reminders — список моих напоминаний
    # ------------------------------------------------------------------
    @app_commands.command(name="reminders", description="📋 Мои активные напоминания")
    async def reminders(self, interaction: discord.Interaction) -> None:
        try:
            lst = await self.bot.dx_stores.reminders.get_field(str(interaction.user.id), "list", []) or []
            if not lst:
                await interaction.response.send_message(
                    embed=dxd.dxd_info("Напоминаний нет. Дзен Конеко с вами 🍪", title="📋 Пусто"),
                    ephemeral=True)
                return
            lines = [f"**#{i + 1}** {dxd.ts_short(dt.datetime.fromisoformat(r['when']))} — {r['text']}"
                     for i, r in enumerate(lst[-10:])]
            e = dxd.dxd_info("\n".join(lines), title=f"📋 Напоминания: {len(lst)}",
                             gif_key="book")
            await interaction.response.send_message(embed=e, ephemeral=True)
        except Exception:
            log.exception("/reminders ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Свиток не разворачивается."),
                                                    ephemeral=True)

    # ------------------------------------------------------------------
    # 3. /cancelreminder — удалить напоминание по номеру
    # ------------------------------------------------------------------
    @app_commands.command(name="cancelreminder", description="🗑️ Отменить напоминание по его номеру")
    @app_commands.describe(number="Номер из /reminders")
    async def cancelreminder(self, interaction: discord.Interaction,
                             number: app_commands.Range[int, 1, 100]) -> None:
        try:
            key = str(interaction.user.id)
            lst = await self.bot.dx_stores.reminders.get_field(key, "list", []) or []
            if not (1 <= number <= len(lst)):
                await interaction.response.send_message(
                    embed=dxd.dxd_error(f"Нет напоминания №{number}. Проверьте /reminders."),
                    ephemeral=True)
                return
            removed = lst.pop(number - 1)
            await self.bot.dx_stores.reminders.set_field(key, "list", lst)
            await interaction.response.send_message(
                embed=dxd.dxd_success(f"Удалено: *{removed['text'][:100]}*", title="🗑️ Вычеркнуто"),
                ephemeral=True)
        except Exception:
            log.exception("/cancelreminder ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Ластик не справился."),
                                                    ephemeral=True)

    # ------------------------------------------------------------------
    # 4. /calc — безопасный калькулятор силы
    # ------------------------------------------------------------------
    _CALC_RE = re.compile(r"^[\d\s+\-*/().%]+$")

    @app_commands.command(name="calc", description="🧮 Посчитать что угодно (безопасный калькулятор)")
    @app_commands.describe(expression="Выражение, например: (9008 * 2 + 50) / 3")
    async def calc(self, interaction: discord.Interaction, expression: str) -> None:
        try:
            expr = expression.replace(",", ".").strip()
            if not self._CALC_RE.match(expr) or len(expr) > 100:
                await interaction.response.send_message(
                    embed=dxd.dxd_error("Разрешены только числа и операторы + - * / ( ) % ."),
                    ephemeral=True)
                return
            result = eval(expr, {"__builtins__": {}}, {})
            e = dxd.dxd_info(f"`{expression[:100]}` = **{result}**",
                             title="🧮 Магический расчёт", gif_key="isma")
            await interaction.response.send_message(embed=e)
        except ZeroDivisionError:
            await interaction.response.send_message(
                embed=dxd.dxd_error("Деление на ноль разрушило бы реальность (как Дивайн Дивайдинг)."),
                ephemeral=True)
        except Exception:
            log.exception("/calc ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Заклинание вычислений не сработало."),
                                                    ephemeral=True)

    # ------------------------------------------------------------------
    # 5. /timer — песочные часы для тренировки
    # ------------------------------------------------------------------
    @app_commands.command(name="timer", description="⏳ Завести песочные часы (секунды)")
    @app_commands.describe(seconds="Длительность 5–3600 сек", label="Для чего таймер")
    async def timer(self, interaction: discord.Interaction,
                    seconds: app_commands.Range[int, 5, 3600], label: str = "тренировка") -> None:
        try:
            end = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=seconds)
            e = dxd.dxd_info(f"⏳ Таймер **{label}** запущен на {seconds} сек.\n"
                             f"Завершится: {dxd.ts(end)}", title="Часы Газанады", gif_key="gasper")
            await interaction.response.send_message(embed=e)

            async def finish() -> None:
                await asyncio.sleep(seconds)
                done = dxd.dxd_success(f"⌛ Время вышло! **{label}** завершена.",
                                       title="Гонг Рейтинговой игры", gif_key="levelup")
                try:
                    await interaction.followup.send(content=interaction.user.mention, embed=done)
                except discord.HTTPException:
                    pass

            task = self.bot.loop.create_task(finish())
            self._timers[interaction.user.id] = task

            # Автоудаление записи при новом таймере того же юзера — чистим зависшие задачи
            old = getattr(self, "_old_tasks", {}).get(interaction.user.id)
            if old and not old.done():
                old.cancel()
            self._old_tasks = getattr(self, "_old_tasks", {})
            self._old_tasks[interaction.user.id] = task
        except Exception:
            log.exception("/timer ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Песок закончился."), ephemeral=True)

    # ------------------------------------------------------------------
    # 6. /color — HEX → превью цвета во фрагменте embed
    # ------------------------------------------------------------------
    @app_commands.command(name="color", description="🎨 Показать цвет по HEX (для ролей и фракций)")
    @app_commands.describe(hex_code="HEX без решётки или с ней, напр. b30733")
    async def color(self, interaction: discord.Interaction, hex_code: str) -> None:
        try:
            h = hex_code.lstrip("#")
            if len(h) != 6 or not all(c in "0123456789abcdefABCDEF" for c in h):
                await interaction.response.send_message(
                    embed=dxd.dxd_error("Нужен корректный HEX вида `b30733`."), ephemeral=True)
                return
            col = discord.Color(int(h, 16))
            e = dxd.dxd_embed("🎨 Печать цвета", f"HEX: `#{h.upper()}`\nRGB: `{col.to_rgb()}`",
                              col, gif_key="diving")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/color ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Краски смешались в хаос."),
                                                    ephemeral=True)

    # ------------------------------------------------------------------
    # 7-8. /wishes /wishdel — список желаний участника (на награды квестов)
    # ------------------------------------------------------------------
    @app_commands.command(name="wish", description="✨ Записать желание (мечта о награде)")
    @app_commands.describe(wish="Что хотите получить?")
    async def wish(self, interaction: discord.Interaction, wish: str) -> None:
        try:
            key = str(interaction.user.id)
            lst = await self.bot.dx_stores.notes.get_field(key, "wishes", []) or []
            if len(lst) >= 10:
                await interaction.response.send_message(
                    embed=dxd.dxd_error("Не жадничайте как Иссэй — максимум 10 желаний!"), ephemeral=True)
                return
            lst.append(wish[:200])
            await self.bot.dx_stores.notes.set_field(key, "wishes", lst)
            e = dxd.dxd_success(f"✨ Желание записано: *{wish[:150]}*\nВсего желаний: {len(lst)}",
                                title="Звёздная мечта", gif_key="iris")
            await interaction.response.send_message(embed=e, ephemeral=True)
        except Exception:
            log.exception("/wish ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Звёзды не слушают."), ephemeral=True)

    @app_commands.command(name="wishes", description="🌠 Посмотреть мои желания")
    async def wishes(self, interaction: discord.Interaction) -> None:
        try:
            lst = await self.bot.dx_stores.notes.get_field(str(interaction.user.id), "wishes", []) or []
            lines = "\n".join(f"**{i + 1}.** ⭐ {w}" for i, w in enumerate(lst)) or "*пусто*"
            e = dxd.dxd_info(lines, title="🌠 Свиток желаний", gif_key="asia")
            await interaction.response.send_message(embed=e, ephemeral=True)
        except Exception:
            log.exception("/wishes ошибка")

    @app_commands.command(name="wishdel", description="🗑️ Удалить желание по номеру")
    @app_commands.describe(number="Номер из /wishes")
    async def wishdel(self, interaction: discord.Interaction, number: int) -> None:
        try:
            key = str(interaction.user.id)
            lst = await self.bot.dx_stores.notes.get_field(key, "wishes", []) or []
            if not (1 <= number <= len(lst)):
                await interaction.response.send_message(
                    embed=dxd.dxd_error("Такого желания нет."), ephemeral=True)
                return
            removed = lst.pop(number - 1)
            await self.bot.dx_stores.notes.set_field(key, "wishes", lst)
            await interaction.response.send_message(
                embed=dxd.dxd_success(f"Исполнено (удалено): *{removed[:100]}*", title="🗑️"),
                ephemeral=True)
        except Exception:
            log.exception("/wishdel ошибка")

    # ------------------------------------------------------------------
    # 9. /rules — свод правил академии Куо
    # ------------------------------------------------------------------
    RULES = [
        "**1.** Уважайте жителей академии — оскорбления караются молотом стафа.",
        "**2.** Никакого спама и флуда: Иссэй флудит «boost» — это его привилегия.",
        "**3.** Реклама только с разрешения Совета (иначе — Standby и бан).",
        "**4.** NSFW контент строго запрещён (кроме шуток про Oppai Balance — грань тонка).",
        "**5.** Споры решайте в ЛС; публичные конфликты портят рейтинг клана.",
        "**6.** Язык общения — договорились в закрепле; иначе переводчик Аси не справится.",
        "**7.** Решения модерации обсуждайте в /ticket, а не общим чатом.",
    ]

    @app_commands.command(name="rules", description="📜 Свод законов академии Куо")
    async def rules(self, interaction: discord.Interaction) -> None:
        try:
            e = dxd.dxd_info("\n\n".join(self.RULES), title="📜 Конституция клана Гремори",
                             gif_key="ryate")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/rules ошибка")

    # ------------------------------------------------------------------
    # 10. /help_dxd — путеводитель по всем командам DxD
    # ------------------------------------------------------------------
    @app_commands.command(name="help_dxd", description="📖 Гид по DxD-командам этого бота")
    async def help_dxd(self, interaction: discord.Interaction) -> None:
        try:
            sections = {
                "🎮 Мини-игры": "/8ball /coinflip /dice /rps /slot /duel /rankup /jankenpopai /guess /memory /trivia /harem",
                "💰 Экономика": "/daily /balance /leaderboard /pay /shop /buy /inventory /useitem /work /gamble /rob /food /feed",
                "⚔️ RPG": "/profile /xp /rank /leaderboard_xp /quest /quests /achievements /title /giveaway /rep /repstats /note",
                "🌸 Аниме": "/quote /waifu /husbando /rollchar /character /meme /animefact /pat /hug /kiss /cuddle /compliment /heal",
                "🏛️ Сервер": "/poll /announce /suggest /serverinfo /memberinfo /roles /emojis /counter /starboard_set /pollresult /botstats /ping /uptime",
                "🧰 Утилиты": "/reminder /reminders /cancelreminder /calc /timer /color /wish /wishes /wishdel /rules /help_dxd /avatar /servericon /snowflake",
            }
            e = dxd.dxd_info("\n\n".join(f"**{k}**\n`{v}`" for k, v in sections.items()),
                             title="📖 Гримуар команд (DxD-режим)", gif_key="book")
            await interaction.response.send_message(embed=e, ephemeral=True)
        except Exception:
            log.exception("/help_dxd ошибка")

    # ------------------------------------------------------------------
    # 11. /avatar — аватар участника в полном размере
    # ------------------------------------------------------------------
    @app_commands.command(name="avatar", description="🖼️ Показать аватар участника крупно")
    @app_commands.describe(member="Чей аватар")
    async def avatar(self, interaction: discord.Interaction, member: discord.Member | None = None) -> None:
        try:
            target = member or interaction.user
            url = str(target.display_avatar.url)
            e = dxd.dxd_info(f"[Открыть в полном размере]({url})",
                             title=f"🖼️ Аватар: {target.display_name}", gif_key=None)
            e.set_image(url=url)
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/avatar ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Зеркало запотело."), ephemeral=True)

    # ------------------------------------------------------------------
    # 12. /servericon — иконка сервера
    # ------------------------------------------------------------------
    @app_commands.command(name="servericon", description="🏯 Герб крепости (иконка сервера)")
    async def servericon(self, interaction: discord.Interaction) -> None:
        try:
            g = interaction.guild
            if g.icon is None:
                await interaction.response.send_message(
                    embed=dxd.dxd_error("У клана нет герба — только знамёна."), ephemeral=True)
                return
            e = dxd.dxd_info(f"[Полный размер]({g.icon.url})", title=f"🏯 {g.name}")
            e.set_image(url=str(g.icon.url))
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/servericon ошибка")

    # ------------------------------------------------------------------
    # 13. /snowflake — расшифровать snowflake ID
    # ------------------------------------------------------------------
    @app_commands.command(name="snowflake", description="❄️ Расшифровать Discord ID: дата создания и др.")
    @app_commands.describe(object_id="Любой Discord ID (сообщения, юзера, канала)")
    async def snowflake(self, interaction: discord.Interaction, object_id: str) -> None:
        try:
            sid = int(object_id)
            # Формула: (snowflake >> 22) + DISCORD_EPOCH (мс)
            created = dt.datetime.fromtimestamp(((sid >> 22) + 1420070400000) / 1000,
                                                tz=dt.timezone.utc)
            worker = (sid >> 17) & 63
            process = (sid >> 12) & 31
            increment = sid & 2047
            e = dxd.dxd_embed(
                "❄️ Snowflake расшифрован",
                f"ID: `{sid}`\nСоздан: **{dxd.ts_short(created)}** UTC\n"
                f"Worker: `{worker}` • Process: `{process}` • Increment: `{increment}`",
                dxd.COLOR_DREAM, gif_key="asia")
            await interaction.response.send_message(embed=e)
        except ValueError:
            await interaction.response.send_message(embed=dxd.dxd_error("ID должен быть числом."),
                                                    ephemeral=True)
        except Exception:
            log.exception("/snowflake ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Снежинка растаяла."), ephemeral=True)

    # ------------------------------------------------------------------
    # ФОН: доставка напоминаний каждые 20 секунд
    # ------------------------------------------------------------------
    @tasks.loop(seconds=20)
    async def reminder_deliverer(self) -> None:
        try:
            now = dt.datetime.now(dt.timezone.utc)
            stores = self.bot.dx_stores
            async with stores.reminders.lock:
                await stores.reminders.load()
                due_any = False
                for uid, blob in list(stores.reminders.data.items()):
                    keep, due = [], []
                    for r in blob.get("list", []):
                        if dt.datetime.fromisoformat(r["when"]) <= now:
                            due.append(r)
                        else:
                            keep.append(r)
                    if due:
                        blob["list"] = keep
                        due_any = True
                        for r in due:
                            channel = self.bot.get_channel(r["channel"])
                            if channel is None:
                                continue
                            e = dxd.dxd_embed(
                                "⏰ НАПОМИНАНИЕ ИЗ ГРИМУАРА",
                                f"<@{r['user']}> пора!\n*{r['text']}*",
                                dxd.COLOR_PHOENIX, gif_key="koneko")
                            try:
                                await channel.send(embed=e)
                            except discord.Forbidden:
                                log.warning("Нет доступа в канал %s для напоминания", r["channel"])
                if due_any:
                    stores.reminders._save_sync()
        except Exception:
            log.exception("reminder_deliverer ошибка")

    @reminder_deliverer.before_loop
    async def before_deliverer(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    if getattr(bot, "dx_stores", None) is None:
        raise RuntimeError("bot.dx_stores не инициализирован — проверьте main.py")
    await bot.add_cog(Utilities(bot))
