# -*- coding: utf-8 -*-
"""
cogs/games.py — мини-игры в стиле High School DxD (12 команд).

Противостояния Рейтинговой игры, казино Куцубэ и дуэли драконов:
/8ball /coinflip /dice /rps /slot /duel /rankup /jankenpopai
/guess /memory /trivia /harem

Все команды публичные (ответ ephemeral=False там, где это часть фана),
ошибки -> красный embed + traceback в bot.log.
"""

from __future__ import annotations

import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

import dxd
from utils import log


class Games(commands.Cog):
    """Мини-игры и азартные забавы фракций DxD."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Активные дуэли: {guild_id: {"challenger":..., "opponent":..., "task":...}}
        self._duels: dict[int, dict] = {}

    # ------------------------------------------------------------------
    # 1. /8ball — Магический шар Куцубэ Касики
    # ------------------------------------------------------------------
    @app_commands.command(name="8ball", description="🔮 Спросить магический шар лисы Куцубэ Касики")
    @app_commands.describe(question="Ваш вопрос вселенной рейтинговых игр")
    async def eight_ball(self, interaction: discord.Interaction, question: str) -> None:
        try:
            answer = random.choice(dxd.MAGIC_ANSWERS)
            e = dxd.dxd_embed(
                "🔮 Шар Девяти Хвостов отвечает",
                f"**Вопрос:** {question[:250]}\n\n**Ответ:** *{answer}*",
                dxd.COLOR_KITONE, gif_key="koneko",
            )
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/8ball ошибка")
            await interaction.response.send_message(
                embed=dxd.dxd_error("Шар отказался отвечать. Попробуйте позже."), ephemeral=True)

    # ------------------------------------------------------------------
    # 2. /coinflip — Дракон или Ангел
    # ------------------------------------------------------------------
    @app_commands.command(name="coinflip", description="🪙 Монета: сторона Дракона или Ангела?")
    @app_commands.describe(side="Ваша ставка на сторону (необязательно)")
    @app_commands.choices(side=[
        app_commands.Choice(name="🐉 Дракон", value="dragon"),
        app_commands.Choice(name="😇 Ангел", value="angel"),
    ])
    async def coin_flip(self, interaction: discord.Interaction, side: app_commands.Choice[str] | None = None) -> None:
        try:
            result = random.choice(dxd.COIN_SIDES)
            won = None
            if side:
                pick = dxd.COIN_SIDES[0] if side.value == "dragon" else dxd.COIN_SIDES[1]
                won = (pick == result)
            verdict = ""
            if won is True:
                verdict = "\n\n🎉 **Победа!** Фортунa благосклонна к вам."
            elif won is False:
                verdict = "\n\n💀 **Поражение.** Проклящение Зенита сработало."
            e = dxd.dxd_embed(
                "🪙 Подбрасываем монету Гремори",
                f"Выпало: **{result}**{verdict}",
                dxd.COLOR_DEVIL if won is not True else dxd.COLOR_SUCCESS,
                gif_key="diving",
            )
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/coinflip ошибка")
            await interaction.response.send_message(
                embed=dxd.dxd_error("Монета упала за шкаф."), ephemeral=True)

    # ------------------------------------------------------------------
    # 3. /dice — Бросок кубика клана Гремори
    # ------------------------------------------------------------------
    @app_commands.command(name="dice", description="🎲 Бросьте кубик: d4, d6, d8, d12, d20 или d100")
    @app_commands.describe(dice="Тип кубика")
    @app_commands.choices(dice=[app_commands.Choice(name=k, value=k) for k in dxd.DICE_SETS])
    async def dice_roll(self, interaction: discord.Interaction, dice: app_commands.Choice[str]) -> None:
        try:
            sides = dxd.DICE_SETS[dice.value]
            roll = random.randint(1, sides)
            crit = " 🐉 **КРИТ!**" if roll == sides else (" 💀 провал..." if roll == 1 else "")
            e = dxd.dxd_embed(
                f"🎲 {interaction.user.display_name} бросает {dice.value}",
                f"Результат: **{roll}** из {sides}{crit}",
                dxd.COLOR_DRAGON, gif_key="isma",
            )
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/dice ошибка")
            await interaction.response.send_message(
                embed=dxd.dxd_error("Кубик раскололся, как сердце Иссэя."), ephemeral=True)

    # ------------------------------------------------------------------
    # 4. /rps — Камень-ножницы-бумага (версия: Дракон-Рыцарь-Лиса)
    # ------------------------------------------------------------------
    _RPS = {"🐉 Дракон": "✂️ Ножницы", "✊ Камень": "🐉 Дракон", "✂️ Ножницы": "📄 Бумага",
            "📄 Бумага": "✊ Камень"}

    @app_commands.command(name="rps", description="✊✂️📄 Камень-ножницы-бумага против бота")
    @app_commands.describe(your_move="Ваш ход")
    @app_commands.choices(your_move=[
        app_commands.Choice(name="✊ Камень", value="rock"),
        app_commands.Choice(name="✂️ Ножницы", value="scissors"),
        app_commands.Choice(name="📄 Бумага", value="paper"),
    ])
    async def rps(self, interaction: discord.Interaction, your_move: app_commands.Choice[str]) -> None:
        try:
            names = {"rock": "✊ Камень", "scissors": "✂️ Ножницы", "paper": "📄 Бумага"}
            mine = random.choice(list(names.values()))
            yours = names[your_move.value]
            if mine == yours:
                res, col = "🤝 Ничья! Оба потратили рейтинг зря.", dxd.COLOR_INFO
            elif self._RPS.get(mine) == yours:
                res, col = f"😈 **Бот побеждает.** {mine} контрит {yours}.", dxd.COLOR_ERROR
            else:
                res, col = f"🏆 **Ваша победа!** {yours} контрит {mine}.", dxd.COLOR_SUCCESS
            e = dxd.dxd_embed("⚔️ Поединок рук", f"Вы: **{yours}** — Бот: **{mine}**\n\n{res}",
                              col, gif_key="isma")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/rps ошибка")
            await interaction.response.send_message(
                embed=dxd.dxd_error("Руки не слушаются — это проклятие."), ephemeral=True)

    # ------------------------------------------------------------------
    # 5. /slot — Слот-машина чайной комнаты Куцубэ
    # ------------------------------------------------------------------
    @app_commands.command(name="slot", description="🎰 Слот-машина Рейтинговой игры (3 символа)")
    async def slot(self, interaction: discord.Interaction) -> None:
        try:
            spin = [dxd.weighted_choice(dxd.SLOT_SYMBOLS) for _ in range(3)]
            if spin[0] == spin[1] == spin[2]:
                verdict = "💥 **ДЖЕКПОТ!** Три символа подряд — клан Феникс платит дань!"
                col = dxd.COLOR_SUCCESS
            elif len(set(spin)) == 2:
                verdict = "✨ Два совпадения — небольшой выигрыш рейтинга."
                col = dxd.COLOR_PHOENIX
            else:
                verdict = "💢 Пусто. Даже Газанада расстроился бы."
                col = dxd.COLOR_ERROR
            e = dxd.dxd_embed(
                "🎰 Слоты Куцубэ",
                f"`{spin[0]}  {spin[1]}  {spin[2]}`\n\n{verdict}",
                col, gif_key="ravel",
            )
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/slot ошибка")
            await interaction.response.send_message(
                embed=dxd.dxd_error("Слоты зажевали вашу ставку и исчезли."), ephemeral=True)

    # ------------------------------------------------------------------
    # 6. /duel — Вызов на дуэль (Boost vs Divide)
    # ------------------------------------------------------------------
    @app_commands.command(name="duel", description="⚔️ Вызвать участника на дуэль силы драконов")
    @app_commands.describe(opponent="Кого вызываете на бой?")
    async def duel(self, interaction: discord.Interaction, opponent: discord.Member) -> None:
        try:
            guild_id = interaction.guild.id
            if guild_id in self._duels:
                await interaction.response.send_message(
                    embed=dxd.dxd_error("В сервере уже идёт дуэль. Дождитесь её окончания."),
                    ephemeral=True)
                return
            if opponent.bot:
                await interaction.response.send_message(
                    embed=dxd.dxd_error("Драконы не дерутся с механизмами (ботами)."),
                    ephemeral=True)
                return
            if opponent.id == interaction.user.id:
                await interaction.response.send_message(
                    embed=dxd.dxd_error("Нельзя сразиться с собственным отражением в озере."),
                    ephemeral=True)
                return

            view_challenger = _DuelView(self, interaction.user, opponent)
            e = dxd.dxd_embed(
                "⚔️ ВЫЗОВ НА ДУЭЛЬ",
                f"**{interaction.user.display_name}** бросает вызов **{opponent.display_name}**!\n"
                f"{opponent.mention}, примете бой? Ставка на кону — ваша гордость!",
                dxd.COLOR_DEVIL, gif_key="vali",
            )
            await interaction.response.send_message(embed=e, view=view_challenger)
        except Exception:
            log.exception("/duel ошибка")
            try:
                await interaction.followup.send(embed=dxd.dxd_error("Дуэль не состоялась."), ephemeral=True)
            except discord.HTTPException:
                pass

    async def resolve_duel(self, interaction: discord.Interaction, challenger: discord.Member,
                           opponent: discord.Member, accepted: bool) -> None:
        """Проводит бой после принятия вызова (колбэк из _DuelView)."""
        try:
            if not accepted:
                await interaction.edit_original_response(
                    embed=dxd.dxd_info(f"**{opponent.display_name}** отклонил вызов. Трусость зафиксирована в хрониках.",
                                        title="🏳️ Дуэль отменена", gif_key="gasper"))
                return
            a, b = random.randint(1, 100), random.randint(1, 100)
            winner = challenger if a >= b else opponent
            e = dxd.dxd_embed(
                "🐉 РЕЗУЛЬТАТ ДУЭЛИ",
                f"{challenger.display_name}: **{a}** ⚡ vs {opponent.display_name}: **{b}** ⚡\n\n"
                f"🏆 Победитель: **{winner.display_name}**! «BOOST!!»",
                dxd.COLOR_SUCCESS, gif_key="boosted",
            )
            await interaction.edit_original_response(embed=e)
        except Exception:
            log.exception("resolve_duel ошибка")

    # ------------------------------------------------------------------
    # 7. /rankup — Тренировка силы (кулдаун 30 сек)
    # ------------------------------------------------------------------
    @app_commands.command(name="rankup", description="🏋️ Тренировка: шанс поднять свой рейтинг силы")
    async def rankup(self, interaction: discord.Interaction) -> None:
        try:
            cooldown = getattr(self, "_rankup_cd", {})
            now = asyncio.get_event_loop().time()
            last = cooldown.get(interaction.user.id, 0)
            if now - last < 30:
                await interaction.response.send_message(
                    embed=dxd.dxd_error(f"Мышцы ещё болят! Следующая тренировка через "
                        f"{30 - int(now - last)} сек."), ephemeral=True)
                return
            cooldown[interaction.user.id] = now
            self._rankup_cd = cooldown
            chance = random.randint(1, 100)
            if chance <= 40:
                gain = random.randint(50, 150)
                msg, col, g = f"🔥 **PROTEGE → BOOST!** Ваш рейтинг вырос на **+{gain}**!", dxd.COLOR_SUCCESS, "boosted"
            elif chance <= 75:
                msg, col, g = "😴 Тренировка прошла впустую... Вы уснули на турнике.", dxd.COLOR_INFO, "gasper"
            else:
                loss = random.randint(10, 40)
                msg, col, g = f"💢 Травма! Рейтинг **-{loss}**. Ася, нужен Healing Magic!", dxd.COLOR_ERROR, "zenith"
            e = dxd.dxd_embed("🏋️ Тренировка дракона", msg, col, gif_key=g)
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/rankup ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Спортзал закрыт."), ephemeral=True)

    # ------------------------------------------------------------------
    # 8. /jankenpopai — Японские кендо-каменные ножницы (как у Кибоя)
    # ------------------------------------------------------------------
    @app_commands.command(name="jankenpopai", description="👊 Быстрая игра «jan-ken-po» с ботом-самураем")
    @app_commands.describe(move="gu (камень) / choki (ножницы) / pa (бумага)")
    @app_commands.choices(move=[
        app_commands.Choice(name="👊 Gu (камень)", value="gu"),
        app_commands.Choice(name="✌️ Choki (ножницы)", value="choki"),
        app_commands.Choice(name="🖐️ Pa (бумага)", value="pa"),
    ])
    async def jankenpopai(self, interaction: discord.Interaction, move: app_commands.Choice[str]) -> None:
        try:
            beats = {"gu": "choki", "choki": "pa", "pa": "gu"}
            emoji = {"gu": "👊", "choki": "✌️", "pa": "🖐️"}
            mine = random.choice(["gu", "choki", "pa"])
            yours = move.value
            if mine == yours:
                res, col = "🤝 Синхронный удар! Ничья.", dxd.COLOR_INFO
            elif beats[yours] == mine:
                res, col = f"⚔️ **Вы победили!** {emoji[yours]} обездвиживает {emoji[mine]}.", dxd.COLOR_SUCCESS
            else:
                res, col = f"🩸 **Поражение.** {emoji[mine]} парирует ваш {emoji[yours]}.", dxd.COLOR_ERROR
            e = dxd.dxd_embed("🎋 Додзё Минато", f"Вы: {emoji[yours]} — Кибой-сенсей: {emoji[mine]}\n\n{res}",
                              col, gif_key="kibou")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/jankenpopai ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Додзё закрыто на уборку."), ephemeral=True)

    # ------------------------------------------------------------------
    # 9. /guess — Угадай число от 1 до N
    # ------------------------------------------------------------------
    @app_commands.command(name="guess", description="🧠 Угадайте число, задуманное Мауро (1–100)")
    @app_commands.describe(max_number="До какого числа загадываем (по умолчанию 100)")
    async def guess(self, interaction: discord.Interaction, max_number: app_commands.Range[int, 10, 1000] = 100) -> None:
        try:
            secret = random.randint(1, max_number)
            tries = 7 if max_number <= 100 else 12
            e = dxd.dxd_embed(
                "🧠 Игра «Число Дьявола»",
                f"Мауро загадал число от 1 до **{max_number}**. У вас **{tries}** попыток.\n"
                f"Отвечайте прямо в чат! (игра активна 60 секунд)",
                dxd.COLOR_FALLLEN, gif_key="maura",
            )
            await interaction.response.send_message(embed=e)

            def check(m: discord.Message) -> bool:
                return m.channel.id == interaction.channel_id and m.author.id == interaction.user.id \
                    and m.content.isdigit()

            for attempt in range(tries):
                try:
                    msg = await self.bot.wait_for("message", check=check, timeout=60)
                except asyncio.TimeoutError:
                    await interaction.followup.send(
                        embed=dxd.dxd_error(f"⏳ Время вышло! Число было **{secret}."))
                    return
                num = int(msg.content)
                if num == secret:
                    await interaction.followup.send(
                        embed=dxd.dxd_success(
                            f"🎯 **УГАДАНО!** {secret} — с {attempt + 1} попытки!\n"
                            "Даже Вали впечатлён вашей интуицией.", title="🏆 Победа",
                            gif_key="levelup"))
                    return
                hint = "⬆️ Больше" if num < secret else "⬇️ Меньше"
                remaining = tries - attempt - 1
                await msg.reply(f"{hint}. Осталось попыток: **{remaining}**", mention_author=False)
            await interaction.followup.send(
                embed=dxd.dxd_error(f"💀 Попытки кончились. Правильный ответ: **{secret}**."))
        except Exception:
            log.exception("/guess ошибка")
            try:
                await interaction.followup.send(embed=dxd.dxd_error("Игра прервана."), ephemeral=True)
            except discord.HTTPException:
                pass

    # ------------------------------------------------------------------
    # 10. /memory — Найди пару артефактов (эмодзи-мемо)
    # ------------------------------------------------------------------
    _MEMO_POOL = ["🐉", "⚔️", "🍑", "🔥", "🌸", "🍪", "🎴", "💢"]

    @app_commands.command(name="memory", description="🃏 Мемо-игра: найдите пары артефактов DxD")
    async def memory(self, interaction: discord.Interaction) -> None:
        try:
            pairs = random.sample(self._MEMO_POOL, 4)
            cards = pairs * 2
            random.shuffle(cards)
            hidden = ["||❔||"] * 8
            view = _MemoryView(self, cards, pairs, interaction.user)
            e = dxd.dxd_embed(
                "🃏 Мемо: Артефакты Бифроста",
                "`" + " ".join(hidden[:4]) + "`\n`" + " ".join(hidden[4:]) + "`\n\n"
                "Нажимайте кнопки, чтобы открывать карты. Найдите все 4 пары!",
                dxd.COLOR_DREAM, gif_key="gasper",
            )
            await interaction.response.send_message(embed=e, view=view)
        except Exception:
            log.exception("/memory ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Карты перетасованы ветром."), ephemeral=True)

    # ------------------------------------------------------------------
    # 11. /trivia — Викторина по лору DxD
    # ------------------------------------------------------------------
    _TRIVIA = [
        ("Как зовут Sacred Gear Иссэя?", "Red Dragon Emperor / Boosted Gear",
         ["Boosted Gear", "Драконий Перчатый", "Оппай Баллон"]),
        ("Какой рангpiece у Риате Гремори?", "King", ["King", "Queen", "Rook"]),
        ("Кто такой Вали Люцифуг?", "White Dragon Emperor",
         ["White Dragon Emperor", "Ангел", "Вампир"]),
        ("Как фамилия Конеко?", "Abissal", ["Abissal", "Kimura", "Tojo"]),
        ("Что использует Газанада перед атакой?", "Standby", ["Standby", "Boost", "Divide"]),
        ("Кто лидер культа «Грималькин»?", "Tatenashi", ["Tatenashi", "Rossweisse", "Kalawacarn"]),
        ("Какой напиток любит Мауро?", "Кофе", ["Кофе", "Сакэ", "Мохи"]),
        ("Как называется школа главных героев?", "Kukyou Academy",
         ["Kukyou Academy", "Kuoh Academy", "Touwa Academy"]),
    ]

    @app_commands.command(name="trivia", description="❓ Викторина по лору High School DxD")
    async def trivia(self, interaction: discord.Interaction) -> None:
        try:
            q, correct, wrongs = random.choice(self._TRIVIA)
            options = [correct] + random.sample(wrongs, 2)
            random.shuffle(options)
            view = _TriviaView(self, correct, interaction.user)
            e = dxd.dxd_embed(
                "❓ Лор-викторина Гриммуара",
                f"**{q}**",
                dxd.COLOR_ANGEL, gif_key="book",
            )
            await interaction.response.send_message(embed=e, view=view)
        except Exception:
            log.exception("/trivia ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Книга закрылась."), ephemeral=True)

    # ------------------------------------------------------------------
    # 12. /harem — Ваша гаремная совместимость (чистый фан, SFW)
    # ------------------------------------------------------------------
    @app_commands.command(name="harem", description="💕 Проверьте свою совместимость с персонажами DxD (фан)")
    @app_commands.describe(partner="Персонаж (пусто = случайный)")
    async def harem(self, interaction: discord.Interaction, partner: str | None = None) -> None:
        try:
            chars = dxd.CHARACTERS
            if partner:
                matches = [c for c in chars if partner.lower() in c["name"].lower()]
                if not matches:
                    await interaction.response.send_message(
                        embed=dxd.dxd_error(f"Персонаж «{partner}» не найден в хрониках DxD. "
                                            "Попробуйте: Иссэй, Риате, Конеко, Ася, Зенавия..."),
                        ephemeral=True)
                    return
                char = random.choice(matches)
            else:
                char = random.choice(chars)
            score = random.randint(1, 100)
            hearts = "❤️" * max(1, score // 10) + "🖤" * (10 - max(1, score // 10))
            verdict = ("Идеальная пара — даже Мауро одобряет!" if score > 85 else
                       "Хорошая совместимость, работаю над харемом!" if score > 60 else
                       "Шансы есть, но тренируйтесь чаще." if score > 35 else
                       "Проклятие Зенита сильнее вашей романтики...")
            e = dxd.dxd_embed(
                f"💕 Совместимость: {interaction.user.display_name} × {char['name']}",
                f"{hearts}  **{score}/100**\n\n*{verdict}*\n\n"
                f"Роль: {char['role']} • Фракция: {char['faction']}",
                discord.Color(char["color"]), gif_key=char["gif"],
            )
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/harem ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Романтика сегодня недоступна."), ephemeral=True)


# ---------------------------------------------------------------------------
# VIEW'Ы ДЛЯ ИНТЕРАКТИВНЫХ ИГР
# ---------------------------------------------------------------------------

class _DuelView(discord.ui.View):
    """Кнопки «Принять / Отклонить» для /duel."""

    def __init__(self, cog: Games, challenger: discord.Member, opponent: discord.Member) -> None:
        super().__init__(timeout=60)
        self.cog, self.challenger, self.opponent = cog, challenger, opponent

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message(
                embed=dxd.dxd_error("Только вызванный участник может принять решение."), ephemeral=True)
            return False
        return True

    @discord.ui.button(label="⚔️ Принять бой", style=discord.ButtonStyle.danger)
    async def accept(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.stop()
        await self.cog.resolve_duel(interaction, self.challenger, self.opponent, True)

    @discord.ui.button(label="🏳️ Отклонить", style=discord.ButtonStyle.secondary)
    async def decline(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.stop()
        await self.cog.resolve_duel(interaction, self.challenger, self.opponent, False)

    async def on_timeout(self) -> None:
        # Вызов истёк, не дожидаясь ответа — молча останавливаем кнопки.
        self.stop()


class _MemoryView(discord.ui.View):
    """Кнопки-карточки для мемо-игры."""

    def __init__(self, cog: Games, cards: list[str], pairs: list[str], owner: discord.Member) -> None:
        super().__init__(timeout=120)
        self.cards, self.pairs, self.owner = cards, pairs, owner
        self.revealed: set[int] = set()
        self.found: set[str] = set()
        self.first_pick: int | None = None
        for idx in range(8):
            btn = discord.ui.Button(label=f"#{idx + 1}", style=discord.ButtonStyle.secondary,
                                    row=idx // 4)
            btn.callback = self._make_callback(idx, btn)
            self.add_item(btn)

    def _make_callback(self, idx: int, btn: discord.ui.Button):
        async def callback(interaction: discord.Interaction) -> None:
            await self._pick(interaction, idx, btn)
        return callback

    async def _pick(self, interaction: discord.Interaction, idx: int, btn: discord.ui.Button) -> None:
        try:
            if interaction.user.id != self.owner.id:
                await interaction.response.send_message(
                    embed=dxd.dxd_error("Это чужая мемо-игра!"), ephemeral=True)
                return
            if idx in self.revealed:
                await interaction.response.defer()
                return
            self.revealed.add(idx)
            btn.label = self.cards[idx]
            btn.style = discord.ButtonStyle.primary
            await interaction.response.edit_message(view=self)

            open_unmatched = [i for i in self.revealed if self.cards[i] not in self.found]
            if len(open_unmatched) == 2:
                a, b = open_unmatched
                await asyncio.sleep(0.6)
                if self.cards[a] == self.cards[b]:
                    self.found.add(self.cards[a])
                    for i in (a, b):
                        self.children[i].disabled = True
                        self.children[i].style = discord.ButtonStyle.success
                else:
                    for i in (a, b):
                        self.children[i].label = "❔"
                        self.children[i].style = discord.ButtonStyle.secondary
                self.revealed -= set(open_unmatched)
                await interaction.edit_original_response(view=self)
                if len(self.found) == len(self.pairs):
                    await interaction.followup.send(
                        embed=dxd.dxd_success("🎉 Все пары найдены! Росвисей гордится вами.",
                                              title="🏆 Мемо пройден", gif_key="roswei"))
                    self.stop()
        except Exception:
            log.exception("Мемо-игра ошибка")

    async def on_timeout(self) -> None:
        self.stop()


class _TriviaView(discord.ui.View):
    """Кнопки ответов для викторины."""

    def __init__(self, cog: Games, correct: str, owner: discord.Member) -> None:
        super().__init__(timeout=45)
        self.correct, self.owner = correct, owner
        for opt in self._options():
            btn = discord.ui.Button(label=opt, style=discord.ButtonStyle.secondary)
            btn.callback = self._make_cb(opt, btn)
            self.add_item(btn)

    def _options(self) -> list[str]:
        for q, corr, wrongs in Games._TRIVIA:
            if corr == self.correct:
                opts = [corr] + list(wrongs)
                random.shuffle(opts)
                return opts
        return [self.correct]

    def _make_cb(self, opt: str, btn: discord.ui.Button):
        async def cb(interaction: discord.Interaction) -> None:
            try:
                if interaction.user.id != self.owner.id:
                    await interaction.response.send_message(
                        embed=dxd.dxd_error("Викторина запущена для другого игрока."), ephemeral=True)
                    return
                if opt == self.correct:
                    btn.style = discord.ButtonStyle.success
                    emb = dxd.dxd_success(f"✅ Верно! **{self.correct}**", title="🏆 Правильно",
                                          gif_key="levelup")
                else:
                    btn.style = discord.ButtonStyle.danger
                    emb = dxd.dxd_error(f"❌ Мимо. Правильный ответ: **{self.correct}**")
                self.stop()
                await interaction.response.edit_message(embed=emb, view=self)
            except Exception:
                log.exception("Викторина ошибка")
        return cb

    async def on_timeout(self) -> None:
        self.stop()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Games(bot))
