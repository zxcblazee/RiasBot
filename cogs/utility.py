# -*- coding: utf-8 -*-
"""
cogs/utility.py — cog утилит.

Команды: /poll /say /embed /userinfo

Решения senior-уровня (не оговорены в ТЗ, приняты разумно):
- /poll: варианты принимаются отдельными параметрами option_1..option_5
  (2 обязательных, до 5 опциональных). Это надёжнее парсинга одной строки
  с разделителями — слэш-UI Discord сам подскажет поля.
- Реакции добавляются с обработкой cooldown'а (429): ставим по очереди,
  ошибки отдельной реакции не валят весь опрос.
- /say и /embed доступны всем, но результат отправляется в канал;
  ephemeral используется только для ошибок валидации.
"""

from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from utils import error_embed, info_embed, log, make_embed, success_embed

# Юникод-«цифры» для реакций-вариантов опроса (эмодзи-кнопки 1️⃣…5️⃣).
POLL_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

# Разрешённые имена цветов для /embed (COLOR_* discord.py не принимает строки
# произвольно — маппим сами, это прозрачнее для пользователя).
EMBED_COLORS = {
    "red": discord.Color.red(),
    "green": discord.Color.green(),
    "blue": discord.Color.blue(),
    "yellow": discord.Color.gold(),
    "orange": discord.Color.orange(),
    "purple": discord.Color.purple(),
    "pink": discord.Color.pink(),
    "grey": discord.Color.dark_grey(),
    "dark": discord.Color.darker_grey(),
    "blurple": discord.Color.blurple(),
}


class Utility(commands.Cog):
    """Утилиты: опросы, сообщения от бота, embed-конструктор, инфо о юзере."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ------------------------------------------------------------------
    # /poll
    # ------------------------------------------------------------------

    @app_commands.command(name="poll", description="Создать опрос с реакциями (2–5 вариантов)")
    @app_commands.describe(
        question="Вопрос опроса",
        option_1="Вариант 1",
        option_2="Вариант 2",
        option_3="Вариант 3 (необязательно)",
        option_4="Вариант 4 (необязательно)",
        option_5="Вариант 5 (необязательно)",
    )
    async def poll(
        self,
        interaction: discord.Interaction,
        question: str,
        option_1: str,
        option_2: str,
        option_3: str | None = None,
        option_4: str | None = None,
        option_5: str | None = None,
    ) -> None:
        try:
            # Собираем непустые варианты, сохраняя порядок.
            options = [o for o in (option_1, option_2, option_3, option_4, option_5) if o and o.strip()]
            if len(options) < 2:
                await interaction.response.send_message(
                    embed=error_embed("Опрос должен содержать минимум 2 варианта."), ephemeral=True,
                )
                return
            if len(options) > 5:  # защита на будущее
                await interaction.response.send_message(
                    embed=error_embed("Максимум 5 вариантов."), ephemeral=True,
                )
                return

            lines = [f"**{question}**\n"]
            for emoji, opt in zip(POLL_EMOJIS, options):
                lines.append(f"{emoji} — {opt}")

            embed = info_embed("\n".join(lines), title="📊 Опрос",
                               footer=f"Автор: {interaction.user.display_name} • голосуйте реакциями")
            await interaction.response.send_message(embed=embed)

            # Реакции ставим ПОСЛЕ ответа (message доступен после send_message).
            message = await interaction.original_response()
            for emoji in POLL_EMOJIS[: len(options)]:
                try:
                    await message.add_reaction(emoji)
                    # Небольшая пауза — страховка от rate limit при 5 реакциях.
                    await asyncio.sleep(0.2)
                except discord.HTTPException:
                    # Одна упавшая реакция не должна отменять опрос —
                    # логируем и идём дальше.
                    log.exception("Не удалось поставить реакцию %s на опрос", emoji)

            log.info("POLL: %s задал опрос «%s» (%d вариантов)", interaction.user, question, len(options))
        except Exception:
            log.exception("Ошибка в /poll")
            try:
                await interaction.response.send_message(
                    embed=error_embed("Не удалось создать опрос. Подробности в логах."),
                    ephemeral=True,
                )
            except discord.InteractionResponded:
                await interaction.followup.send(
                    embed=error_embed("Не удалось создать опрос. Подробности в логах."),
                    ephemeral=True,
                )

    # ------------------------------------------------------------------
    # /say
    # ------------------------------------------------------------------

    @app_commands.command(name="say", description="Отправить сообщение от имени бота")
    @app_commands.describe(message="Текст сообщения", channel="Канал (по умолчанию — текущий)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def say(
        self,
        interaction: discord.Interaction,
        message: app_commands.Range[str, 1, 2000],
        channel: discord.TextChannel | None = None,
    ) -> None:
        try:
            target_channel = channel or interaction.channel
            await target_channel.send(message)
            # Подтверждение — только автору, чтобы не спамить в канал.
            await interaction.response.send_message(
                embed=success_embed(f"Сообщение отправлено в {target_channel.mention}."),
                ephemeral=True,
            )
            log.info("SAY: %s -> #%s", interaction.user, getattr(target_channel, 'name', '?'))
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed("Бот не может писать в этот канал (нет прав Send Messages)."),
                ephemeral=True,
            )
        except Exception:
            log.exception("Ошибка в /say")
            await interaction.response.send_message(
                embed=error_embed("Произошла непредвиденная ошибка. Подробности в логах."),
                ephemeral=True,
            )

    # ------------------------------------------------------------------
    # /embed
    # ------------------------------------------------------------------

    @app_commands.command(name="embed", description="Создать и отправить embed-сообщение")
    @app_commands.describe(
        title="Заголовок embed",
        description="Текст embed (поддерживает markdown)",
        color="Цвет: red/green/blue/yellow/orange/purple/pink/grey/dark/blurple",
        channel="Канал (по умолчанию — текущий)",
    )
    @app_commands.choices(color=[
        app_commands.Choice(name=name, value=name) for name in EMBED_COLORS
    ])
    @app_commands.checks.has_permissions(manage_messages=True)
    async def embed_cmd(
        self,
        interaction: discord.Interaction,
        title: app_commands.Range[str, 1, 256],
        description: app_commands.Range[str, 1, 4096],
        color: app_commands.Choice[str] = None,  # type: ignore[assignment]
        channel: discord.TextChannel | None = None,
    ) -> None:
        try:
            chosen = EMBED_COLORS[color.value] if color else discord.Color.blurple()
            target_channel = channel or interaction.channel

            emb = make_embed(title, description, chosen,
                             footer=f"Отправлено через /embed • {interaction.user.display_name}")
            await target_channel.send(embed=emb)
            await interaction.response.send_message(
                embed=success_embed(f"Embed отправлен в {target_channel.mention}."),
                ephemeral=True,
            )
            log.info("EMBED: %s -> #%s | «%s»", interaction.user,
                     getattr(target_channel, 'name', '?'), title)
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed("Бот не может писать в этот канал (нет прав)."),
                ephemeral=True,
            )
        except Exception:
            log.exception("Ошибка в /embed")
            await interaction.response.send_message(
                embed=error_embed("Произошла непредвиденная ошибка. Подробности в логах."),
                ephemeral=True,
            )

    # ------------------------------------------------------------------
    # /userinfo
    # ------------------------------------------------------------------

    @app_commands.command(name="userinfo", description="Информация о пользователе: регистрация, роли, ID")
    @app_commands.describe(member="Участник (по умолчанию — вы)")
    async def userinfo(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        try:
            target = member or interaction.user
            guild = interaction.guild
            if guild is None:
                raise ValueError("Команда доступна только на сервере.")
            # Параметр может быть User из поиска вне кэша гильдии — берём свежий Member.
            resolved = guild.get_member(target.id)
            if resolved is None:
                raise ValueError("Этот пользователь не является участником сервера "
                                 "(используйте команду на сервере и укажите местного участника).")
            target = resolved

            # Роли без @everyone, от старшей к младшей. Если ролей много —
            # показываем топ-10 и счётчик, иначе embed превысит лимит 4096.
            roles = sorted(
                [r for r in target.roles if r != guild.default_role],
                key=lambda r: r.position,
                reverse=True,
            )
            roles_text = ", ".join(r.mention for r in roles[:10]) or "*нет ролей*"
            if len(roles) > 10:
                roles_text += f" …и ещё {len(roles) - 10}"

            status_map = {
                discord.Status.online: "🟢 В сети",
                discord.Status.idle: "🟡 Отошёл",
                discord.Status.dnd: "⛔ Не беспокоить",
                discord.Status.offline: "⚫ Не в сети",
            }
            activity = f" • {target.activity.name}" if target.activity else ""

            embed = info_embed(
                "",
                title=f"👤 {target.display_name}",
                fields={
                    "ID": f"`{target.id}`",
                    "Аккаунт создан": f"<t:{int(target.created_at.timestamp())}:F> (<t:{int(target.created_at.timestamp())}:R>)",
                    "На сервере с": (
                        f"<t:{int(target.joined_at.timestamp())}:F> (<t:{int(target.joined_at.timestamp())}:R>)"
                        if target.joined_at else "неизвестно"
                    ),
                    "Статус": status_map.get(target.status, "⚫ Не в сети") + activity,
                    "Роли": roles_text,
                    "Бот?": "Да 🤖" if target.bot else "Нет",
                },
            )
            embed.set_thumbnail(url=target.display_avatar.url)
            await interaction.response.send_message(embed=embed)
        except ValueError as e:
            await interaction.response.send_message(embed=error_embed(str(e)), ephemeral=True)
        except Exception:
            log.exception("Ошибка в /userinfo")
            await interaction.response.send_message(
                embed=error_embed("Произошла непредвиденная ошибка. Подробности в логах."),
                ephemeral=True,
            )


async def setup(bot: commands.Bot) -> None:
    """Загрузка кога discord.py-механикой setup_hook/load_extension."""
    await bot.add_cog(Utility(bot))
