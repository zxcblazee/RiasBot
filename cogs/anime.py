# -*- coding: utf-8 -*-
"""
cogs/anime.py — аниме-контент и ролевые команды DxD (13 команд).

Культовый шарм сериала: персонажи, цитаты, «гаремная химия»,
комплименты от Аси, «исцеление» после проигрыша.

Команды:
/quote /waifu /husbando /rollchar /character /meme /animefact
/pat /hug /kiss /cuddle /compliment /heal
"""

from __future__ import annotations

import random

import discord
from discord import app_commands
from discord.ext import commands

import dxd
from utils import log


# Мужская линия DxD: по этим подстрокам имени определяем «хусбандо».
MALE_NAMES = ("Иссэй", "Мауро", "Вали", "Сираорг", "Кибой", "Газанада", "Росвисей",
              "Албион", "Офпэр", "Персеполь", "Баркиэль", "Джербаакс", "Куо")


class Anime(commands.Cog):
    """Ролевые и контентные команды во вселенной DxD."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ------------------------------------------------------------------
    # 1. /quote — случайная цитата персонажа
    # ------------------------------------------------------------------
    @app_commands.command(name="quote", description="💬 Цитата персонажа High School DxD")
    async def quote(self, interaction: discord.Interaction) -> None:
        try:
            who, text = random.choice(dxd.QUOTES)
            char = next((c for c in dxd.CHARACTERS if who.split()[0].lower() in c["name"].lower()),
                        {"color": int(dxd.COLOR_DEVIL), "gif": "isma"})
            e = dxd.dxd_embed(
                f"💬 {who} говорит:",
                f"*«{text}»* ",
                discord.Color(char["color"]), gif_key=char["gif"])
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/quote ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Цитата растворилась в эфире."), ephemeral=True)

    # ------------------------------------------------------------------
    # 2. /waifu — ваша ваифу из DxD (случайная или по имени)
    # ------------------------------------------------------------------
    # Женская линия: все персонажи, не входящие в мужской список MALE_NAMES.
    _FEM = [c for c in dxd.CHARACTERS
            if not any(k in c["name"] for k in MALE_NAMES)]

    @app_commands.command(name="waifu", description="🌸 Ваша ваифу из мира DxD (или проверьте конкретную)")
    @app_commands.describe(name="Имя персонажа (пусто = случайная)")
    async def waifu(self, interaction: discord.Interaction, name: str | None = None) -> None:
        try:
            pool = self._FEM
            if name:
                matches = [c for c in pool if name.lower() in c["name"].lower()]
                if not matches:
                    await interaction.response.send_message(
                        embed=dxd.dxd_error(f"Дама «{name}» не найдена в академии Куо.",
                                            title="🌸 Неверный призыв"), ephemeral=True)
                    return
                char = matches[0]
            else:
                char = random.choice(pool)
            aff = random.randint(50, 100)
            e = dxd.dxd_embed(
                f"🌸 Призвана дама: {char['name']}",
                f"**{char['role']}** • фракция **{char['faction']}**\n"
                f"Сила: `{char['power']}` ⚡ • Ваша симпатия: `{aff}/100` 💗\n\n"
                + ("*«Не подведи меня, мой рыцарь.»*" if aff > 80 else "*«Ещё есть куда расти...»*"),
                discord.Color(char["color"]), gif_key=char["gif"])
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/waifu ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Заклинание призыва не сработало."), ephemeral=True)

    # ------------------------------------------------------------------
    # 3. /husbando — мужская линия персонажей
    # ------------------------------------------------------------------
    _MALE = [c for c in dxd.CHARACTERS if any(k in c["name"] for k in MALE_NAMES)]

    @app_commands.command(name="husbando", description="🐉 Ваш хусбандо из мира DxD")
    @app_commands.describe(name="Имя персонажа (пусто = случайный)")
    async def husbando(self, interaction: discord.Interaction, name: str | None = None) -> None:
        try:
            if name:
                matches = [c for c in self._MALE if name.lower() in c["name"].lower()]
                if not matches:
                    await interaction.response.send_message(
                        embed=dxd.dxd_error(f"Джентльмен «{name}» не найден в драконьем реестре."),
                        ephemeral=True)
                    return
                char = matches[0]
            else:
                char = random.choice(self._MALE)
            cool = random.randint(60, 100)
            e = dxd.dxd_embed(
                f"🐉 Пробуждён мужчина: {char['name']}",
                f"**{char['role']}** • фракция **{char['faction']}**\n"
                f"Сила: `{char['power']}` ⚡ • Харизма: `{cool}/100` 😎",
                discord.Color(char["color"]), gif_key=char["gif"])
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/husbando ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Печать не открылась."), ephemeral=True)

    # ------------------------------------------------------------------
    # 4. /rollchar — ролл случайного персонажа как «напарника дня»
    # ------------------------------------------------------------------
    @app_commands.command(name="rollchar", description="🎭 Кто ваш напарник на сегодня? Судьба решает!")
    async def rollchar(self, interaction: discord.Interaction) -> None:
        try:
            char = random.choice(dxd.CHARACTERS)
            synergy = random.randint(1, 100)
            bond = "S" if synergy > 85 else "A" if synergy > 65 else "B" if synergy > 45 else "C"
            e = dxd.dxd_embed(
                f"🎭 Напарник дня: {char['name']}",
                f"Ранг связи: **{bond}** ({synergy}/100)\n"
                f"Роль: {char['role']} • Фракция: {char['faction']}\n"
                + ("*Идеальный тандем для Рейтинговой игры!*" if bond == "S"
                   else "*Сгодится, но Иссэй был бы полезнее.*" if bond == "C"
                   else "*Продуктивный союз!*"),
                discord.Color(char["color"]), gif_key=char["gif"])
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/rollchar ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Судьба перемолола карты."), ephemeral=True)

    # ------------------------------------------------------------------
    # 5. /character — досье на конкретного персонажа
    # ------------------------------------------------------------------
    @app_commands.command(name="character", description="📇 Досье на персонажа DxD по имени")
    @app_commands.describe(name="Часть имени: Иссэй, Риате, Конеко, Вали, Ася...")
    async def character(self, interaction: discord.Interaction, name: str) -> None:
        try:
            matches = [c for c in dxd.CHARACTERS if name.lower() in c["name"].lower()]
            if not matches:
                hint = ", ".join(sorted({c["name"].split()[0] for c in dxd.CHARACTERS})[:8])
                await interaction.response.send_message(
                    embed=dxd.dxd_error(f"Персонаж не найден. Попробуйте одно из имён: {hint}..."),
                    ephemeral=True)
                return
            c = matches[0]
            e = dxd.dxd_embed(
                f"📇 Досье: {c['name']}",
                f"Статус: **{c['role']}**\nФракция: **{c['faction']}**\n"
                f"Рейтинг силы: **{c['power']}** ⚡",
                discord.Color(c["color"]), gif_key=c["gif"])
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/character ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Архив закрыт."), ephemeral=True)

    # ------------------------------------------------------------------
    # 6. /meme — мем-строка из жизни академии
    # ------------------------------------------------------------------
    _MEMES = [
        "POV: Иссэй сказал «boost» 9008 раз за вечер, а харема всё нет 😔",
        "Когда Конеко назвала тебя «вкусным» — это комплимент или меню?",
        "Уровень доверия к библиотеке: Росвисей снова сожгла полку 🔥📚",
        " Gazanada использует Standby чтобы достать печенье с верхней полки 🍪",
        "Тот момент, когда Ася лечит все раны, кроме уязвлённого эго Иссэя",
        "Мауро наблюдает за рейтинговой игрой людей так же, как вы за этим мемом 👁️",
        "— Иссэй, почему ты опоздал?\n— Тренировал «Balloon Blade»... то есть балансировку книг 📚",
        "Когда в чате спойлерят 25 том: *все ангелы покидают сервер* 😇➡️🚪",
        "Kiba: speedblitz. Isekai: oppaigen. Баланс сил нарушен навсегда.",
        "Ravel вызывает на дуэль. Вы принимаете. Это была ловушка клана Феникс 🔥",
    ]

    @app_commands.command(name="meme", description="😂 Случайный мем из жизни академии Куо")
    async def meme(self, interaction: discord.Interaction) -> None:
        try:
            e = dxd.dxd_info(random.choice(self._MEMES), title="😂 Мемы академии Куо",
                              gif_key=random.choice(["diving", "oppai", "isma", "ravel"]))
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/meme ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Мем оказался слишком культовым."), ephemeral=True)

    # ------------------------------------------------------------------
    # 7. /animefact — факт о сериале/ранобэ
    # ------------------------------------------------------------------
    _FACTS = [
        "High School DxD начался как ранобэ Миэбуно Итиэй в 2008 году; иллюстрации — Misaki Miyama.",
        "«Boosted Gear» — один из двух Sacred Gear драконов; второй — Divine Dividing у Вали.",
        "Автор планировал закончить серию на 5 томах, но она растянулась на 25+.",
        "Каждый сезон DxD менял студию: TNK, Passione, Zero-G...",
        "Имя «Issei Hyoudou» созвучно слову «issei» — «одна жизнь/усердие».",
        "Rias Gremori — явная отсылка к демону Астароту из демонологии Гримуара Арса Темена.",
        "Koneko — сокращение от «kotetsu no neko» (стальная кошка), её фамилия Abyssal.",
        "В японском оригинале фразы Иссэя содержат игру слов с «oppai», что теряется в переводе.",
        "Draconic Metamorphosis Иссэя — финальная форма, доступная лишь приняв природу дракона.",
        "Vali Team и Benedrette Team — два взвода, пародирующих структуру Рейтинговых игр.",
    ]

    @app_commands.command(name="animefact", description="🧠 Интересный факт о вселенной DxD")
    async def animefact(self, interaction: discord.Interaction) -> None:
        try:
            e = dxd.dxd_info(random.choice(self._FACTS), title="🧠 Знание Гримуара",
                             gif_key="book")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/animefact ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Мудрость ещё не пробудилась."), ephemeral=True)

    # ------------------------------------------------------------------
    # 8–12. Ролевые: /pat /hug /kiss /cuddle /compliment /heal
    # ------------------------------------------------------------------

    async def _roleplay(self, interaction: discord.Interaction, member: discord.Member,
                        emoji: str, action: str, gif_key: str, color: discord.Color) -> None:
        """Общий механизм ролевых команд: валидации + красивый embed."""
        if member.id == interaction.user.id:
            await interaction.response.send_message(
                embed=dxd.dxd_error("Это действие требует второго участника — магия одиночества бессильна."),
                ephemeral=True)
            return
        if member.bot and member.id != self.bot.user.id:
            await interaction.response.send_message(
                embed=dxd.dxd_error("Другие боты не участвуют в человеческих ритуалах."), ephemeral=True)
            return
        e = dxd.dxd_embed(
            f"{emoji} {action}",
            f"**{interaction.user.display_name}** {action.lower()} **{member.display_name}** {emoji}",
            color, gif_key=gif_key)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="pat", description="🐾 Погладить участника (как Конеко разрешает)")
    @app_commands.describe(member="Кого гладим")
    async def pat(self, interaction: discord.Interaction, member: discord.Member) -> None:
        try:
            await self._roleplay(interaction, member, "🐾", "нежно гладит", "koneko", dxd.COLOR_KITONE)
        except Exception:
            log.exception("/pat ошибка")

    @app_commands.command(name="hug", description="🫂 Обнять участника (объятие клана)")
    @app_commands.describe(member="Кого обнимаем")
    async def hug(self, interaction: discord.Interaction, member: discord.Member) -> None:
        try:
            await self._roleplay(interaction, member, "🫂", "крепко обнимает", "asia", dxd.COLOR_ANGEL)
        except Exception:
            log.exception("/hug ошибка")

    @app_commands.command(name="kiss", description="💋 Поцелуй на лоб (только по-дружески!)")
    @app_commands.describe(member="Кого целуем в лобик")
    async def kiss(self, interaction: discord.Interaction, member: discord.Member) -> None:
        try:
            await self._roleplay(interaction, member, "💋", "дарит дружеский поцелуй в лоб",
                                  "ryate", dxd.COLOR_DEVIL)
        except Exception:
            log.exception("/kiss ошибка")

    @app_commands.command(name="cuddle", description="🤗 Уютное обнимашки-заседание чайной")
    @app_commands.describe(member="С кем уютимся")
    async def cuddle(self, interaction: discord.Interaction, member: discord.Member) -> None:
        try:
            await self._roleplay(interaction, member, "🤗", "утюжит в обнимашках",
                                  "iris", dxd.COLOR_DREAM)
        except Exception:
            log.exception("/cuddle ошибка")

    _compliments = [
        "Ваша аура сильнее чем пирсинг Дивинга!",
        "Вы улыбаетесь как Равель после победы в ставке.",
        "Ваша преданность серверу достойна короля Гремори.",
        "С вами даже Татэнэби не уснёт на уроке.",
        "Ваш рейтинг привлекательности только что вырос на 100.",
        "Вы несёте свет, как Ася в самой тёмной главе.",
    ]

    @app_commands.command(name="compliment", description="✨ Сделать участнику комплимент от лица бота")
    @app_commands.describe(member="Кому комплимент")
    async def compliment(self, interaction: discord.Interaction, member: discord.Member) -> None:
        try:
            line = random.choice(self._compliments)
            e = dxd.dxd_embed(
                "✨ Комплимент от Хрониста",
                f"**{member.display_name}:**\n*«{line}»*\n\nОтправитель: {interaction.user.mention}",
                dxd.COLOR_PHOENIX, gif_key="asia")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/compliment ошибка")

    @app_commands.command(name="heal", description="💖 Исцелить расстроенного участника (Healing Magic)")
    @app_commands.describe(member="Кому нужна поддержка")
    async def heal(self, interaction: discord.Interaction, member: discord.Member) -> None:
        try:
            e = dxd.dxd_embed(
                "💖 Healing Touch!",
                f"**{interaction.user.display_name}** творит светлую магию над **{member.display_name}**:\n"
                "*«Rejuvenate! Пусть грусть уходит, как падшие ангелы передBoosted Gear!»*",
                dxd.COLOR_ANGEL, gif_key="asia")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/heal ошибка")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Anime(bot))
