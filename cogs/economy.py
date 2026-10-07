# -*- coding: utf-8 -*-
"""
cogs/economy.py — экономика «Рейтинговой игры» DxD (13 команд).

Валюта: 🔶 монеты Гремори. Заработок: /daily /work /rob /feed + квесты.
Траты: /shop /buy /food /gamble /bet /slot не связано (см. games).
Социальное: /pay /balance /leaderboard /profile(в rpg) /inventory /useitem.

Команды:
/daily /balance /leaderboard /pay /shop /buy /inventory /useitem
/work /gamble /rob /food /feed
"""

from __future__ import annotations

import datetime as dt
import random

import discord
from discord import app_commands
from discord.ext import commands

import dxd
from store import JsonStore, economy_defaults
from utils import log

# Профессии для /work: (название, эмодзи, min, max)
JOBS: list[tuple[str, str, int, int]] = [
    ("Медсестра в чайной", "🩹", 20, 60),        # работа Аси
    ("Библиотекарь", "📚", 30, 70),              # Росвисей
    ("Тренер рыцарей", "⚔️", 40, 90),             # Кибой
    ("Шпион Серого Дракона", "🕵️", 10, 150),       # рискованно
    ("Пекарь мооти", "🍡", 25, 55),               # Куцубэ
    ("Оценщик рейтингов", "🗂️", 35, 80),
    ("Укротитель драконов", "🐉", 60, 140),
]


class Economy(commands.Cog):
    """Экономика сервера в лоре Рейтинговых Игр."""

    def __init__(self, bot: commands.Bot, economy: JsonStore) -> None:
        self.bot = bot
        self.eco = economy

    # ------------------------------------------------------------------
    # ВНУТРЕННИЕ ХЕЛПЕРЫ
    # ------------------------------------------------------------------

    async def _adjust(self, user_id: int, delta: int) -> int:
        """Изменяет баланс и сохраняет. Возвращает новый баланс."""
        async with self.eco.lock:
            prof = await self.eco.get_profile(user_id, economy_defaults())
            prof["coins"] = max(0, int(prof["coins"]) + delta)
            self.eco._save_sync()
            return prof["coins"]

    # ------------------------------------------------------------------
    # 1. /daily — ежедневная выплата от клана
    # ------------------------------------------------------------------
    @app_commands.command(name="daily", description="📅 Забрать дневную выплату от клана Гремори")
    async def daily(self, interaction: discord.Interaction) -> None:
        try:
            now = dt.datetime.now(dt.timezone.utc)
            async with self.eco.lock:
                prof = await self.eco.get_profile(interaction.user.id, economy_defaults())
                last_raw = prof.get("last_daily")
                if last_raw:
                    last = dt.datetime.fromisoformat(last_raw)
                    if (now - last) < dt.timedelta(hours=20):
                        nxt = last + dt.timedelta(hours=20)
                        await interaction.response.send_message(
                            embed=dxd.dxd_error(
                                f"Выплата уже получена! Следующая {dxd.ts(nxt)}.",
                                title="📅 Ежедневная казна"), ephemeral=True)
                        return
                streak_bonus = 0
                if last_raw and (now - dt.datetime.fromisoformat(last_raw)) <= dt.timedelta(hours=48):
                    streak_bonus = min(50, (prof.get("streak_days", 0) + 1) * 5)
                amount = 100 + streak_bonus
                prof["coins"] += amount
                prof["last_daily"] = now.isoformat()
                prof["streak_days"] = prof.get("streak_days", 0) + 1
                self.eco._save_sync()
            e = dxd.dxd_success(
                f"💰 **+{dxd.fmt_amount(amount)}** 🔶 (бония серии: +{streak_bonus})\n"
                f"Новый баланс: **{dxd.fmt_amount(prof['coins'])}** 🔶",
                title="📅 Клана Гремори казна открыта", gif_key="ryate")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/daily ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Казна заперта. Попробуйте позже."),
                                                    ephemeral=True)

    # ------------------------------------------------------------------
    # 2. /balance — кошелёк
    # ------------------------------------------------------------------
    @app_commands.command(name="balance", description="👛 Проверить свои монеты (или чужие)")
    @app_commands.describe(member="Чей баланс посмотреть (пусто = ваш)")
    async def balance(self, interaction: discord.Interaction, member: discord.Member | None = None) -> None:
        try:
            target = member or interaction.user
            prof = await self.eco.get_profile(target.id, economy_defaults())
            # Плащ Газанады скрывает чужой баланс (кроме самого владельца/админов)
            if prof.get("cloak") and target.id != interaction.user.id \
                    and not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message(
                    embed=dxd.dxd_info("**Плащ Газанады**: этот участник скрыл свой баланс 🧥",
                                       title="👛 Невидимые монеты"),
                    ephemeral=True)
                return
            e = dxd.dxd_info(
                f"💰 Баланс: **{dxd.fmt_amount(prof['coins'])}** 🔶\n"
                f"🎯 Побед в играх: {prof['wins']} • 💀 Поражений: {prof['losses']}",
                title=f"👛 Кошелёк: {target.display_name}", gif_key="ravel")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/balance ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Кошелёк потерян в озере."), ephemeral=True)

    # ------------------------------------------------------------------
    # 3. /leaderboard — топ богатейших
    # ------------------------------------------------------------------
    @app_commands.command(name="leaderboard", description="🏆 Топ-10 богатейших участников сервера")
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        try:
            async with self.eco.lock:
                await self.eco.load()
                rows = []
                for uid, prof in self.eco.data.items():
                    coins = int(prof.get("coins", 0))
                    if coins > 0:
                        rows.append((int(uid), coins))
            rows.sort(key=lambda x: -x[1])
            medals = ["🥇", "🥈", "🥉"]
            lines = []
            for i, (uid, coins) in enumerate(rows[:10]):
                name = f"<@{uid}>"
                prefix = medals[i] if i < 3 else f"**#{i + 1}**"
                lines.append(f"{prefix} {name} — **{dxd.fmt_amount(coins)}** 🔶")
            if not lines:
                lines = ["*Пока никто не разбогател. Все ещё пешки.*"]
            e = dxd.dxd_info("\n".join(lines), title="🏆 Совет Богачей DxD", gif_key="sairaorg")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/leaderboard ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Совет богачей на перерыве."), ephemeral=True)

    # ------------------------------------------------------------------
    # 4. /pay — перевод монет
    # ------------------------------------------------------------------
    @app_commands.command(name="pay", description="🎁 Перевести монеты другому участнику")
    @app_commands.describe(member="Получатель", amount="Сколько монет отправить", reason="За что (необязательно)")
    async def pay(self, interaction: discord.Interaction, member: discord.Member,
                  amount: app_commands.Range[int, 1, 1_000_000], reason: str = "Просто так") -> None:
        try:
            if member.id == interaction.user.id:
                await interaction.response.send_message(
                    embed=dxd.dxd_error("Себе переводить нельзя — это не экономика, а магия."),
                    ephemeral=True)
                return
            if member.bot:
                await interaction.response.send_message(
                    embed=dxd.dxd_error("Боты не берут взятки. Почти."), ephemeral=True)
                return
            # Атомарная транзакция под одним локом: списание -> зачисление
            async with self.eco.lock:
                sender = await self.eco.get_profile(interaction.user.id, economy_defaults())
                if int(sender["coins"]) < amount:
                    await interaction.response.send_message(
                        embed=dxd.dxd_error(f"Недостаточно монет: у вас {dxd.fmt_amount(int(sender['coins']))} 🔶, "
                                            f"а вы хотите отправить {dxd.fmt_amount(amount)} 🔶."),
                        ephemeral=True)
                    return
                sender["coins"] -= amount
                receiver = await self.eco.get_profile(member.id, economy_defaults())
                receiver["coins"] += amount
                sender["has_paid"] = True   # отметка для квеста socialite
                self.eco._save_sync()
            e = dxd.dxd_success(
                f"💸 **{interaction.user.display_name}** → **{member.display_name}**: "
                f"**{dxd.fmt_amount(amount)}** 🔶\nПричина: *{reason[:100]}*",
                title="🎁 Казна перетекает", gif_key="isma")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/pay ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Перевод заблокирован банком Raijin."),
                                                    ephemeral=True)

    # ------------------------------------------------------------------
    # 5. /shop — витрина магических предметов
    # ------------------------------------------------------------------
    @app_commands.command(name="shop", description="🛒 Магазин артефактов Бифроста")
    async def shop(self, interaction: discord.Interaction) -> None:
        try:
            lines = []
            for it in dxd.SHOP_ITEMS:
                lines.append(f"{it['emoji']} **{it['name']}** — `{it['price']}` 🔶\n┗ {it['desc']}")
            e = dxd.dxd_info("\n\n".join(lines), title="🛒 Артефакты у торговца Дорни",
                             gif_key="roswei", fields=None)
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/shop ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Торговец уснул."), ephemeral=True)

    # ------------------------------------------------------------------
    # 6. /buy — покупка предмета
    # ------------------------------------------------------------------
    @app_commands.command(name="buy", description="🧾 Купить артефакт из магазина")
    @app_commands.describe(item_id="ID товара (см. /shop)")
    @app_commands.choices(item_id=[
        app_commands.Choice(name=f"{it['emoji']} {it['name']} ({it['price']} 🔶)", value=it["id"])
        for it in dxd.SHOP_ITEMS
    ])
    async def buy(self, interaction: discord.Interaction, item_id: app_commands.Choice[str]) -> None:
        try:
            item = next(i for i in dxd.SHOP_ITEMS if i["id"] == item_id.value)
            async with self.eco.lock:
                prof = await self.eco.get_profile(interaction.user.id, economy_defaults())
                if prof["coins"] < item["price"]:
                    await interaction.response.send_message(
                        embed=dxd.dxd_error(f"Не хватает {item['price'] - prof['coins']} 🔶. "
                                            "Идите работать (/work)!"), ephemeral=True)
                    return
                prof["coins"] -= item["price"]
                inv = prof.setdefault("inventory", {})
                inv[item["id"]] = inv.get(item["id"], 0) + 1
                self.eco._save_sync()
            e = dxd.dxd_success(
                f"{item['emoji']} Куплено: **{item['name']}** за `{item['price']}` 🔶\n"
                f"Остаток на счету: **{dxd.fmt_amount(prof['coins'])}** 🔶",
                title="🧾 Сделка заключена", gif_key=item["gif"])
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/buy ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Касса сломалась."), ephemeral=True)

    # ------------------------------------------------------------------
    # 7. /inventory — сумка артефактов
    # ------------------------------------------------------------------
    @app_commands.command(name="inventory", description="🎒 Ваши купленные артефакты")
    async def inventory(self, interaction: discord.Interaction) -> None:
        try:
            prof = await self.eco.get_profile(interaction.user.id, economy_defaults())
            inv = prof.get("inventory", {})
            if not inv:
                await interaction.response.send_message(
                    embed=dxd.dxd_info("Сумка пуста, как комната Иссэя после рейда гарема.\n"
                                       "Загляните в /shop!", title="🎒 Инвентарь"),
                    ephemeral=True)
                return
            by_id = {i["id"]: i for i in dxd.SHOP_ITEMS}
            lines = [f"{by_id[k]['emoji']} **{by_id[k]['name']}** ×{v}"
                     for k, v in inv.items() if k in by_id]
            e = dxd.dxd_info("\n".join(lines), title=f"🎒 Сумка: {interaction.user.display_name}",
                             gif_key="gasper")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/inventory ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Инвентарь недоступен."), ephemeral=True)

    # ------------------------------------------------------------------
    # 8. /useitem — активировать артефакт
    # ------------------------------------------------------------------
    @app_commands.command(name="useitem", description="✨ Активировать купленный артефакт")
    @app_commands.describe(item_id="Какой предмет использовать")
    @app_commands.choices(item_id=[
        app_commands.Choice(name=f"{it['emoji']} {it['name']}", value=it["id"])
        for it in dxd.SHOP_ITEMS
    ])
    async def useitem(self, interaction: discord.Interaction, item_id: app_commands.Choice[str]) -> None:
        try:
            item = next(i for i in dxd.SHOP_ITEMS if i["id"] == item_id.value)
            async with self.eco.lock:
                prof = await self.eco.get_profile(interaction.user.id, economy_defaults())
                inv = prof.get("inventory", {})
                if inv.get(item["id"], 0) < 1:
                    await interaction.response.send_message(
                        embed=dxd.dxd_error(f"У вас нет **{item['name']}**. Сначала купите в /shop!"),
                        ephemeral=True)
                    return
                inv[item["id"]] -= 1
                if inv[item["id"]] <= 0:
                    inv.pop(item["id"])
                effect = item["effect"]
                if effect == "boost8":
                    prof["buff_boost"] = int(prof.get("buff_boost", 0)) + 8
                    msg = "🔺 **BOOST ×8!** Ваш следующий бой будет усилен!"
                elif effect == "shield":
                    prof["shield"] = int(prof.get("shield", 0)) + 1
                    msg = "🛡️ **Aegis активирована.** Один штраф теперь не страшен."
                elif effect == "cloak":
                    prof["cloak"] = int(prof.get("cloak", 0)) + 1
                    msg = "🧥 **Плащ надеть.** Ваш баланс скрыт от любопытных."
                elif effect == "lucky":
                    prof["buff_lucky"] = int(prof.get("buff_lucky", 0)) + 5
                    msg = "🪙 **Удача Феникса:** +шансы на джекпот в следующих 5 спинах."
                elif effect == "xp2x":
                    prof["buff_xp"] = 10
                    msg = "🧪 **Эликсир опыта:** ×2 XP за следующие 10 сообщений."
                else:
                    msg = "✨ Эффект активирован."
                prof["inventory"] = inv
                self.eco._save_sync()
            e = dxd.dxd_success(msg, title=f"{item['emoji']} {item['name']}", gif_key=item["gif"])
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/useitem ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Артефакт не слушается хозяина."),
                                                    ephemeral=True)

    # ------------------------------------------------------------------
    # 9. /work — сменить профессию на день
    # ------------------------------------------------------------------
    _work_cd: dict[int, float] = {}

    @app_commands.command(name="work", description="💼 Отработать смену и получить монеты")
    async def work(self, interaction: discord.Interaction) -> None:
        try:
            import time as _t
            now = _t.time()
            if now - self._work_cd.get(interaction.user.id, 0) < 3600:
                left = 3600 - (now - self._work_cd[interaction.user.id])
                await interaction.response.send_message(
                    embed=dxd.dxd_error(f"Смена ещё не окончена! Отдыхайте {int(left // 60)} мин."),
                    ephemeral=True)
                return
            self._work_cd[interaction.user.id] = now
            job = random.choice(JOBS)
            earned = random.randint(job[2], job[3])
            await self._adjust(interaction.user.id, earned)
            e = dxd.dxd_success(
                f"{job[1]} Вы работали: **{job[0]}**\nЗаработано: **+{earned}** 🔶",
                title="💼 Смена завершена", gif_key="kibou")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/work ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Работодатель передумал."), ephemeral=True)

    # ------------------------------------------------------------------
    # 10. /gamble — ставка на выпадение символа
    # ------------------------------------------------------------------
    @app_commands.command(name="gamble", description="🎲 Поставить монеты на удачу (×2 шанс ~45%)")
    @app_commands.describe(amount="Сколько ставите")
    async def gamble(self, interaction: discord.Interaction,
                     amount: app_commands.Range[int, 10, 100_000]) -> None:
        try:
            prof = await self.eco.get_profile(interaction.user.id, economy_defaults())
            if prof["coins"] < amount:
                await interaction.response.send_message(
                    embed=dxd.dxd_error("На счету меньше, чем вы хотите проиграть."), ephemeral=True)
                return
            lucky = int(prof.get("buff_lucky", 0)) > 0
            win_chance = 0.50 if lucky else 0.45
            won = random.random() < win_chance
            async with self.eco.lock:
                p = await self.eco.get_profile(interaction.user.id, economy_defaults())
                p["bets"] = int(p.get("bets", 0)) + 1
                if p.get("buff_lucky"):
                    p["buff_lucky"] = int(p["buff_lucky"]) - 1
                if won:
                    p["coins"] += amount
                    p["wins"] = int(p.get("wins", 0)) + 1
                else:
                    if int(p.get("shield", 0)) > 0:
                        p["shield"] = int(p["shield"]) - 1
                        shield_saved = True
                    else:
                        p["coins"] -= amount
                        p["losses"] = int(p.get("losses", 0)) + 1
                        shield_saved = False
                self.eco._save_sync()
            if won:
                e = dxd.dxd_success(f"🎉 **Выигрыш +{amount}** 🔶!\nБаланс: {dxd.fmt_amount(p['coins'])} 🔶",
                                    title="🎲 Фортуна улыбнулась", gif_key="iris")
            elif locals().get("shield_saved"):
                e = dxd.dxd_info("🛡️ Ставка проиграна, но **щит Аegis** поглотил потери!",
                                 title="🎲 Спасение", gif_key="xenovia")
            else:
                e = dxd.dxd_error(f"💀 **Проигрыш -{amount}** 🔶.\nБаланс: {dxd.fmt_amount(p['coins'])} 🔶",
                                  title="🎲 Казино всегда побеждает", gif_key="zenith")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/gamble ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Столы перевернулись."), ephemeral=True)

    # ------------------------------------------------------------------
    # 11. /rob — попытка ограбить (рискованно!)
    # ------------------------------------------------------------------
    @app_commands.command(name="rob", description="🦹 Попытаться ограбить участника (шанс 30%, риск штрафа)")
    @app_commands.describe(member="Жертва ограбления")
    async def rob(self, interaction: discord.Interaction, member: discord.Member) -> None:
        try:
            if member.id == interaction.user.id:
                await interaction.response.send_message(
                    embed=dxd.dxd_error("Ограбить себя — это не преступление, а психотерапия."),
                    ephemeral=True)
                return
            victim = await self.eco.get_profile(member.id, economy_defaults())
            if int(victim["coins"]) < 50:
                await interaction.response.send_message(
                    embed=dxd.dxd_error(f"У {member.display_name} слишком бедный кошелёк — "
                                        "не стоит риска (нужно ≥50 🔶)."), ephemeral=True)
                return
            success = random.random() < 0.30
            loot = random.randint(50, min(300, int(victim["coins"])))
            async with self.eco.lock:
                v = await self.eco.get_profile(member.id, economy_defaults())
                m = await self.eco.get_profile(interaction.user.id, economy_defaults())
                if success:
                    v["coins"] = max(0, int(v["coins"]) - loot)
                    m["coins"] += loot
                    self.eco._save_sync()
                    e = dxd.dxd_success(
                        f"🦹 **Ограбление удалось!** Добыча: **{loot}** 🔶 у {member.display_name}.",
                        title="💰 Дело в тени", gif_key="maura")
                else:
                    fine = min(int(m["coins"]), 50)
                    m["coins"] -= fine
                    v["coins"] += fine // 2
                    self.eco._save_sync()
                    e = dxd.dxd_error(
                        f"🚔 Вас поймала стража Гремори! Штраф **-{fine}** 🔶, "
                        "половина ушла жертве как компенсация.", title="⛔ Провал", gif_key="xenovia")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/rob ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("План ограбления сорвался."), ephemeral=True)

    # ------------------------------------------------------------------
    # 12. /food — меню чайной Куцубэ
    # ------------------------------------------------------------------
    @app_commands.command(name="food", description="🍽️ Меню чайной комнаты Куцубэ")
    async def food(self, interaction: discord.Interaction) -> None:
        try:
            lines = [f"{m['emoji']} **{m['name']}** — `{m['price']}` 🔶 (+{m['heal']} настроения)"
                     for m in dxd.MENU]
            e = dxd.dxd_info("\n".join(lines), title="🍽️ Чайная Куцубэ: сегодня в меню",
                             gif_key="koneko")
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/food ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Кухня закрыта."), ephemeral=True)

    # ------------------------------------------------------------------
    # 13. /feed — купить еду и восстановить «силу»
    # ------------------------------------------------------------------
    @app_commands.command(name="feed", description="🍜 Перекусить в чайной (монеты → настроение)")
    @app_commands.describe(dish_id="Блюдо из меню /food")
    @app_commands.choices(dish_id=[
        app_commands.Choice(name=f"{m['emoji']} {m['name']} ({m['price']} 🔶)", value=m["id"])
        for m in dxd.MENU
    ])
    async def feed(self, interaction: discord.Interaction, dish_id: app_commands.Choice[str]) -> None:
        try:
            dish = next(m for m in dxd.MENU if m["id"] == dish_id.value)
            async with self.eco.lock:
                prof = await self.eco.get_profile(interaction.user.id, economy_defaults())
                if prof["coins"] < dish["price"]:
                    await interaction.response.send_message(
                        embed=dxd.dxd_error("Не хватает монет на обед. Голод — плохой бафф."),
                        ephemeral=True)
                    return
                prof["coins"] -= dish["price"]
                prof["mood"] = min(100, int(prof.get("mood", 50)) + dish["heal"])
                self.eco._save_sync()
            e = dxd.dxd_success(
                f"{dish['emoji']} Вы съели **{dish['name']}**!\n"
                f"Настроение: **{prof['mood']}/100** ✨ (остаток {prof['coins']} 🔶)",
                title="🍽️ Приятного аппетита!", gif_key=dish["gif"])
            await interaction.response.send_message(embed=e)
        except Exception:
            log.exception("/feed ошибка")
            await interaction.response.send_message(embed=dxd.dxd_error("Поднос упал."), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    stores = getattr(bot, "dx_stores", None)
    if stores is None:
        raise RuntimeError("bot.dx_stores не инициализирован — проверьте main.py")
    await bot.add_cog(Economy(bot, stores.economy))
