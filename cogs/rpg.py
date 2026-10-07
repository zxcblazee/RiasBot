# -*- coding: utf-8 -*-
"""
cogs/rpg.py — RPG-прокачка участника в стиле Рейтинговой игры (12 команд).

XP начисляется за сообщения (кулдаун 60 сек, +5..12 XP), бафф «×2» из
экономистики умножает награду. Ранги — фигуры Рейтинговой Игры (см. dxd.RANKS).

Команды:
/profile /xp /rank /leaderboard_xp /quest /quests /achievements
/title /giveaway /rep /repstats /note
"""

from __future__ import annotations

import datetime as dt
import random

import discord
from discord import app_commands
from discord.ext import commands, tasks

import dxd
from store import JsonStore, economy_defaults, rep_defaults, xp_defaults
from utils import log


class RPG(commands.Cog):
    """Прокачка, квесты, достижения, репутация и розыгрыши."""

    def __init__(self, bot: commands.Bot, xp: JsonStore, rep: JsonStore,
                 econ: JsonStore, achievements: JsonStore, giveaways: JsonStore) -> None:
        self.bot = bot
        self.xp = xp
        self.rep = rep
        self.econ = econ
        self.ach = achievements
        self.giv = giveaways

    # ------------------------------------------------------------------
    # ФОН: начисление XP за сообщения
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """+XP за каждое сообщение (не ботам, не в ЛС, кулдаун на юзера)."""
        try:
            if message.author.bot or message.guild is None:
                return
            now = dt.datetime.now(dt.timezone.utc)
            async with self.xp.lock:
                prof = await self.xp.get_profile(message.author.id, xp_defaults())
                last_raw = prof.get("last_msg")
                if last_raw:
                    last = dt.datetime.fromisoformat(last_raw)
                    if (now - last).total_seconds() < 60:
                        return  # антифлуд: опыт максимум раз в минуту
                gain = random.randint(5, 12)
                # Бафф эликсира опыта из экономики
                eco = await self.econ.get_profile(message.author.id, economy_defaults())
                if int(eco.get("buff_xp", 0)) > 0:
                    gain *= 2
                    eco["buff_xp"] = int(eco["buff_xp"]) - 1
                    async with self.econ.lock:
                        self.econ._save_sync()
                old_rank = dxd.rank_for_xp(int(prof["xp"]))
                prof["xp"] = int(prof["xp"]) + gain
                prof["messages"] = int(prof["messages"]) + 1
                prof["last_msg"] = now.isoformat()
                self.xp._save_sync()
                new_rank = dxd.rank_for_xp(int(prof["xp"]))
            # Повышение ранга — праздничный embed в канал
            if new_rank[0] > old_rank[0]:
                chan_id = await self.bot.dx_stores.settings.get_field(
                    str(message.guild.id), "levelup_channel")
                channel = message.guild.get_channel(chan_id) if chan_id else message.channel
                e = dxd.dxd_embed(
                    "⬆️ РАНГ ПОВЫШЕН!",
                    f"<@{message.author.id}> достигает нового звания: **{new_rank[1]}**!\n"
                    f"*«{(random.choice(['BOOST!', 'Как дракон!', 'Рейтинг растёт!', 'Харем приближается!']))}*\"",
                    new_rank[2], gif_key=new_rank[3])
                await channel.send(embed=e)
        except Exception:
            log.exception("RPG: ошибка начисления XP")

    # ------------------------------------------------------------------
    # 1. /profile — карточка воина
    # ------------------------------------------------------------------
    @app_commands.command(name="profile", description="🪪 Ваша карточка воина Рейтинговой игры")
    @app_commands.describe(member="Чью карточку посмотреть")
    async def profile(self, interaction: discord.Interaction, member: discord.Member | None = None) -> None:
        try:
            target = member or interaction.user
            xprof = await self.xp.get_profile(target.id, xp_defaults())
            eprof = await self.econ.get_profile(target.id, economy_defaults())
            rprof = await self.rep.get_profile(target.id, rep_defaults())
            rank = dxd.rank_for_xp(int(xprof["xp"]))
            nxt = dxd.next_rank_for_xp(int(xprof["xp"]))
            progress = ""
            if nxt:
                need = nxt[0] - rank[0]
                have = int(xprof["xp"]) - rank[0]
                bar_len = 12
                filled = round(bar_len * have / max(1, need))
                progress = (f"{'▓' * filled}{'░' * (bar_len - filled)} "
                            f"{have}/{need} до **{nxt[1]}**")
            else:
                progress = "🐉 Максимальный ранг достигнут!"
            # Плащ Газанады: чужой профиль без баланса
            coins_line = ("🧥 скрыт плащом" if eprof.get("cloak") and target.id != interaction.user.id
                          else f"💰 {dxd.fmt_amount(int(eprof['coins']))} 🔶")
            user_title = xprof.get("title")
            title_line = f"Титул: «{user_title}»\n" if user_title else ""
            e = dxd.dxd_embed(
                f"🪪 Карточка: {target.display_name}",
                f"{title_line}Звание: **{rank[1]}**\n{progress}",
                rank[2],
                gif_key=rank[3],
                thumbnail=str(target.display_avatar.url),
                fields={
                    "✨ Опыт": dxd.fmt_amount(int(xprof["xp"])) + " XP",
                    "💬 Сообщений": dxd.fmt_amount(int(xprof["messages"])),
                    "👛 Монеты": coins_line,
                    "⭐ Репутация": f"+{rprof['received']} / −{int(rprof.get('negative', 0))}",
                    "🎯 Побед/поражений": f"{eprof['wins']}W / {eprof['losses']}L",
                },
            )
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/profile ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Карточка потерялась в гримуаре."),
                                                    ephemeral=True)

    # ------------------------------------------------------------------
    # 2. /xp — сколько опыта и где добрать
    # ------------------------------------------------------------------
    @app_commands.command(name="xp", description="✨ Ваш текущий опыт и прогресс звания")
    async def xp_cmd(self, interaction: discord.Interaction) -> None:
        try:
            prof = await self.xp.get_profile(interaction.user.id, xp_defaults())
            rank = dxd.rank_for_xp(int(prof["xp"]))
            nxt = dxd.next_rank_for_xp(int(prof["xp"]))
            tip = "Пишите сообщения в чате (+5–12 XP, раз в минуту)."
            e = dxd.dxd_info(
                f"Текущий XP: **{dxd.fmt_amount(int(prof['xp']))}**\n"
                f"Звание: **{rank[1]}**\n"
                + (f"До следующего: **{nxt[0] - int(prof['xp'])}** XP ({nxt[1]})\n" if nxt else "")
                + f"\n💡 {tip}",
                title="✨ Магия опыта", gif_key="asia")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/xp ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Гриммуар не открылся."), ephemeral=True)

    # ------------------------------------------------------------------
    # 3. /rank — список всех званий
    # ------------------------------------------------------------------
    @app_commands.command(name="rank", description="📜 Все звания Рейтинговой игры и их пороги")
    async def rank_list(self, interaction: discord.Interaction) -> None:
        try:
            lines = [f"`{thr:>5}` XP — {name}" for thr, name, _, _ in dxd.RANKS]
            e = dxd.dxd_info("\n".join(lines), title="📜 Табель о рангах DxD", gif_key="ryate")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/rank ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Табель унесло ветром."), ephemeral=True)

    # ------------------------------------------------------------------
    # 4. /leaderboard_xp — топ по опыту
    # ------------------------------------------------------------------
    @app_commands.command(name="leaderboard_xp", description="🏅 Топ-10 по опыту (самые активные)")
    async def leaderboard_xp(self, interaction: discord.Interaction) -> None:
        try:
            async with self.xp.lock:
                await self.xp.load()
                rows = sorted(((int(u), int(p.get("xp", 0))) for u, p in self.xp.data.items()),
                              key=lambda x: -x[1])[:10]
            medals = ["🥇", "🥈", "🥉"]
            lines = []
            for i, (uid, xp) in enumerate(rows):
                prefix = medals[i] if i < 3 else f"**#{i + 1}**"
                rank = dxd.rank_for_xp(xp)[1]
                lines.append(f"{prefix} <@{uid}> — **{dxd.fmt_amount(xp)}** XP • {rank}")
            if not lines:
                lines = ["*Никто ещё не начал путь воина. Станьте первым — просто пишите в чат!*"]
            e = dxd.dxd_info("\n".join(lines), title="🏅 Зал Славы Активности", gif_key="vali")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/leaderboard_xp ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Зал славы закрыт на ремонт."), ephemeral=True)

    # ------------------------------------------------------------------
    # 5. /quests — список заданий дня
    # ------------------------------------------------------------------
    @app_commands.command(name="quests", description="🗃️ Все ежедневные задания клана")
    async def quests(self, interaction: discord.Interaction) -> None:
        try:
            lines = []
            for q in dxd.QUESTS:
                lines.append(f"{q['emoji']} **{q['title']}** — {q['desc']}\n"
                             f"┗ Награда: `{q['reward_coins']}` 🔶 + `{q['reward_xp']}` XP")
            e = dxd.dxd_info("\n\n".join(lines), title="🗃️ Досок объявлений заданий",
                             gif_key="koneko")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/quests ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Доска заданий пуста."), ephemeral=True)

    # ------------------------------------------------------------------
    # 6. /quest — проверить выполнение конкретного задания
    # ------------------------------------------------------------------
    @app_commands.command(name="quest", description="✅ Проверить прогресс задания и забрать награду")
    @app_commands.describe(quest_id="ID задания (первое слово из /quests)")
    async def quest(self, interaction: discord.Interaction, quest_id: str) -> None:
        try:
            q = next((x for x in dxd.QUESTS if x["id"] == quest_id.lower()), None)
            if not q:
                await interaction.response.send_message(
                    embed=dxd.dxd_error(f"Задание «{quest_id}» не найдено. Список — в /quests."),
                    ephemeral=True)
                return
            uid = str(interaction.user.id)
            done = await self.ach.get_field(uid, "quests_done", []) or []
            if q["id"] in done:
                await interaction.response.send_message(
                    embed=dxd.dxd_info("Это задание уже выполнено и награда получена ✅",
                                       title=f"{q['emoji']} {q['title']}"), ephemeral=True)
                return
            # Простейшая проверка условий через существующие данные
            completed = False
            if q["id"] == "chat_10":
                xprof = await self.xp.get_profile(interaction.user.id, xp_defaults())
                completed = int(xprof["messages"]) >= 10
            elif q["id"] in ("daily_checkin",):
                eprof = await self.econ.get_profile(interaction.user.id, economy_defaults())
                if eprof.get("last_daily"):
                    today = dt.date.today().isoformat()
                    completed = str(eprof["last_daily"]).startswith(today)
            elif q["id"] == "duelist":
                eprof = await self.econ.get_profile(interaction.user.id, economy_defaults())
                completed = int(eprof.get("wins", 0)) >= 1
            elif q["id"] == "gambler":
                eprof = await self.econ.get_profile(interaction.user.id, economy_defaults())
                completed = int(eprof.get("bets", 0)) >= 1
            elif q["id"] == "socialite":
                completed = bool(await self.econ.get_field(uid, "has_paid"))
            elif q["id"] == "clean_freak":
                completed = bool(await self.econ.get_field(uid, "did_clear"))
            if not completed:
                await interaction.response.send_message(
                    embed=dxd.dxd_error(f"Условия **{q['title']}** ещё не выполнены: {q['desc']}",
                                        title=f"{q['emoji']} Ещё нет"), ephemeral=True)
                return
            # Выдача награды
            async with self.econ.lock:
                ep = await self.econ.get_profile(interaction.user.id, economy_defaults())
                ep["coins"] += q["reward_coins"]
                self.econ._save_sync()
            async with self.xp.lock:
                xp_p = await self.xp.get_profile(interaction.user.id, xp_defaults())
                xp_p["xp"] += q["reward_xp"]
                self.xp._save_sync()
            done.append(q["id"])
            await self.ach.set_field(uid, "quests_done", done)
            e = dxd.dxd_success(
                f"🎉 Задание **{q['title']}** выполнено!\nНаграда: `+{q['reward_coins']}` 🔶 "
                f"и `+{q['reward_xp']}` XP", title="✅ Квест сдан", gif_key="levelup")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/quest ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Гильдейский писарь болен."), ephemeral=True)

    # ------------------------------------------------------------------
    # 7. /achievements — витрина достижений
    # ------------------------------------------------------------------
    @app_commands.command(name="achievements", description="🏆 Ваши достижения и прогресс сервера")
    async def achievements(self, interaction: discord.Interaction) -> None:
        try:
            uid = str(interaction.user.id)
            unlocked = await self.ach.get_field(uid, "achievements", []) or []
            xprof = await self.xp.get_profile(interaction.user.id, xp_defaults())
            eprof = await self.econ.get_profile(interaction.user.id, economy_defaults())
            # автовыдача достижений по фактическим данным
            auto = []
            if int(xprof["messages"]) >= 100: auto.append("talkative")
            if int(eprof["bets"]) >= 25: auto.append("gambling_addict")
            if int(eprof["coins"]) >= 5000: auto.append("rich")
            if int(eprof["best_streak"] or 0) >= 3: auto.append("dragon_slayer")
            new_unlocks = [a for a in auto if a not in unlocked]
            if new_unlocks:
                unlocked.extend(new_unlocks)
                await self.ach.set_field(uid, "achievements", unlocked)
            lines = []
            for a in dxd.ACHIEVEMENTS:
                got = a["id"] in unlocked
                mark = "✅" if got else "🔒"
                lines.append(f"{mark} {a['emoji']} **{a['title']}** — {a['desc']}")
            e = dxd.dxd_info(
                "\n".join(lines),
                title=f"🏆 Достижения: {interaction.user.display_name} "
                      f"({len(unlocked)}/{len(dxd.ACHIEVEMENTS)})",
                gif_key="sairaorg")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/achievements ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Зал трофеев заперт."), ephemeral=True)

    # ------------------------------------------------------------------
    # 8. /title — выбрать титул (украшает /profile)
    # ------------------------------------------------------------------
    TITLES = ["Кандидат в Харем-Кинги", "Будущий Maou", "Рыцарь Печенья",
              "Летописец Куо", "Повелитель Мооти", "Тень Серого Дракона",
              "Ангел Чайной", "Standby-мастер"]

    @app_commands.command(name="title", description="🎖️ Установить себе титул (украшает профиль)")
    @app_commands.describe(title="Ваш новый титул")
    @app_commands.choices(title=[app_commands.Choice(name=t, value=t) for t in TITLES])
    async def title(self, interaction: discord.Interaction, title: app_commands.Choice[str]) -> None:
        try:
            await self.xp.set_field(interaction.user.id, "title", title.value)
            e = dxd.dxd_success(f"🎖️ Новый титул: **«{title.value}»**\nОн виден в вашем /profile!",
                                title="Титул присвоен", gif_key="ryate")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/title ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Герольд молчит."), ephemeral=True)

    # ------------------------------------------------------------------
    # 9. /giveaway — запустить розыгрыш (модерация Manage Guild)
    # ------------------------------------------------------------------
    @app_commands.command(name="giveaway", description="🎉 Запустить розыгрыш с реакцией-участием")
    @app_commands.describe(prize="Что разыгрываем", hours="Длительность в часах (1–168)",
                           winners="Сколько победителей")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway(self, interaction: discord.Interaction, prize: str,
                       hours: app_commands.Range[int, 1, 168] = 24,
                       winners: app_commands.Range[int, 1, 5] = 1) -> None:
        try:
            ends_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=hours)
            e = dxd.dxd_embed(
                "🎉 РОЗЫГРЫШ ОТ КЛАНА ГРЕМОРИ",
                f"Приз: **{prize[:300]}**\nПобедителей: **{winners}**\n"
                f"Реагируйте 🐉 на это сообщение!\nЗакончится: {dxd.ts_short(ends_at)}",
                dxd.COLOR_PHOENIX, gif_key="iris")
            msg = await interaction.channel.send(embed=e)
            await msg.add_reaction("🐉")
            entry = {"message_id": msg.id, "channel_id": interaction.channel_id,
                     "ends_at": ends_at.isoformat(), "prize": prize, "winners": winners,
                     "host": interaction.user.id, "ended": False}
            async with self.giv.lock:
                await self.giv.load()
                self.giv.data.setdefault(str(interaction.guild.id), {"list": []})
                self.giv.data[str(interaction.guild.id)]["list"].append(entry)
                self.giv._save_sync()
            await interaction.response.send_message(
                embed=dxd.dxd_success(f"Розыгрыш запущен! Продлится до {dxd.ts(ends_at)}.",
                                      title="🎉 Good luck!"), ephemeral=True)
        except Exception:
            log.exception("/giveaway ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Розыгрыш не удался."), ephemeral=True)

    # ------------------------------------------------------------------
    # 10-11. /rep и /repstats — репутация «+ / −»
    # ------------------------------------------------------------------
    @app_commands.command(name="rep", description="⭐ Оценить репутацию участника (+1 или −1)")
    @app_commands.describe(member="Кого оцениваем", vote="Плюс или минус")
    @app_commands.choices(vote=[
        app_commands.Choice(name="⭐ Плюс", value="up"),
        app_commands.Choice(name="💢 Минус", value="down"),
    ])
    async def rep(self, interaction: discord.Interaction, member: discord.Member,
                  vote: app_commands.Choice[str]) -> None:
        try:
            if member.id == interaction.user.id:
                await interaction.response.send_message(
                    embed=dxd.dxd_error("Самооценка оставлена магам."), ephemeral=True)
                return
            if member.bot:
                await interaction.response.send_message(
                    embed=dxd.dxd_error("Боты копят репутацию процессорным временем."), ephemeral=True)
                return
            async with self.rep.lock:
                giv = await self.rep.get_profile(interaction.user.id, rep_defaults())
                rec = await self.rep.get_profile(member.id, rep_defaults())
                key = f"voted_{member.id}"
                prev = giv.get(key)
                if prev and (dt.datetime.now(dt.timezone.utc)
                             - dt.datetime.fromisoformat(prev)) < dt.timedelta(hours=12):
                    await interaction.response.send_message(
                        embed=dxd.dxd_error(f"Голос за {member.display_name} учтён ранее — "
                                            "повторить можно через 12 часов."),
                        ephemeral=True)
                    return
                giv[key] = dt.datetime.now(dt.timezone.utc).isoformat()
                giv["given"] = int(giv["given"]) + 1
                if vote.value == "up":
                    rec["received"] = int(rec["received"]) + 1
                else:
                    rec["negative"] = int(rec.get("negative", 0)) + 1
                self.rep._save_sync()
            total = int(rec["received"]) - int(rec.get("negative", 0))
            e = dxd.dxd_success(
                f"{'⭐' if vote.value == 'up' else '💢'} {member.display_name}: "
                f"итоговая репутация **{total:+d}**", title="Голос учтён", gif_key="asia")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/rep ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Кафедра этики не отвечает."), ephemeral=True)

    @app_commands.command(name="repstats", description="📊 Рейтинг репутации сервера")
    async def repstats(self, interaction: discord.Interaction) -> None:
        try:
            async with self.rep.lock:
                await self.rep.load()
                rows = []
                for uid, p in self.rep.data.items():
                    score = int(p.get("received", 0)) - int(p.get("negative", 0))
                    rows.append((int(uid), score))
            rows.sort(key=lambda x: -x[1])
            lines = [f"**#{i + 1}** <@{u}> — **{s:+d}**" for i, (u, s) in enumerate(rows[:10])]
            e = dxd.dxd_info("\n".join(lines) or "*Оценок пока нет.*",
                             title="📊 Совет Репутаций", gif_key="ryate")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/repstats ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Статистика уснула."), ephemeral=True)

    # ------------------------------------------------------------------
    # 12. /note — личная заметка модератора об участнике
    # ------------------------------------------------------------------
    @app_commands.command(name="note", description="📝 Модераторская заметка об участнике (видят только staff)")
    @app_commands.describe(member="О ком заметка", text="Текст заметки")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def note(self, interaction: discord.Interaction, member: discord.Member, text: str) -> None:
        try:
            key = f"{interaction.guild.id}:{member.id}"
            notes = await self.bot.dx_stores.notes.get_field(key, "list", []) or []
            notes.append({"author": str(interaction.user), "text": text[:500],
                          "when": dt.datetime.now(dt.timezone.utc).isoformat()})
            await self.bot.dx_stores.notes.set_field(key, "list", notes[-50:])
            await interaction.response.send_message(
                embed=dxd.dxd_success(f"📝 Заметка о {member.display_name} сохранена "
                                      f"(всего: {len(notes)}).", title="Для глаз стафа"),
                ephemeral=True)
        except Exception:
            log.exception("/note ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Гримуар заметок закрыт."), ephemeral=True)

    # ------------------------------------------------------------------
    # ФОН: завершение розыгрышей (каждые 30 сек проверяем дедлайны)
    # ------------------------------------------------------------------
    @tasks.loop(seconds=30)
    async def giveaway_watcher(self) -> None:
        try:
            now = dt.datetime.now(dt.timezone.utc)
            async with self.giv.lock:
                await self.giv.load()
                for gid, blob in list(self.giv.data.items()):
                    guild = self.bot.get_guild(int(gid))
                    if not guild:
                        continue
                    changed = False
                    for entry in blob.get("list", []):
                        if entry.get("ended") or dt.datetime.fromisoformat(entry["ends_at"]) > now:
                            continue
                        channel = guild.get_channel(entry["channel_id"])
                        if channel is None:
                            entry["ended"] = True
                            changed = True
                            continue
                        try:
                            msg = await channel.fetch_message(entry["message_id"])
                            users = []
                            for reaction in msg.reactions:
                                if str(reaction.emoji) == "🐉":
                                    async for u in reaction.users():
                                        if not u.bot and u.id != entry["host"]:
                                            users.append(u.id)
                            pool = list(set(users))
                            winners = random.sample(pool, min(entry["winners"], len(pool))) if pool else []
                            win_text = " ".join(f"<@{w}>" for w in winners) if winners else "никого 😢"
                            e = dxd.dxd_embed(
                                "🎉 РОЗЫГРЫШ ЗАВЕРШЁН",
                                f"Приз **{entry['prize']}** получает: {win_text}\n"
                                f"Участников: {len(pool)}",
                                dxd.COLOR_PHOENIX, gif_key="iris")
                            await channel.send(embed=e)
                        except discord.HTTPException:
                            log.warning("Не удалось завершить розыгрыш %s", entry["message_id"])
                        entry["ended"] = True
                        changed = True
                    if changed:
                        self.giv._save_sync()
        except Exception:
            log.exception("giveaway_watcher ошибка")

    @giveaway_watcher.before_loop
    async def before_watcher(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    stores = getattr(bot, "dx_stores", None)
    if stores is None:
        raise RuntimeError("bot.dx_stores не инициализирован — проверьте main.py")
    cog = RPG(bot, stores.xp, stores.rep, stores.economy, stores.achievements, stores.giveaways)
    await bot.add_cog(cog)
