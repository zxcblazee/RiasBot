# -*- coding: utf-8 -*-
"""
cogs/moderation.py — cog модерации.

Команды: /kick /ban /unban /mute /unmute /warn /warnings /clear /slowmode

Ключевые моменты качества (по ТЗ):
- Проверка прав через @app_commands.checks.has_permissions(...) + собственный
  обработчик ошибок в main.py (вежливый ephemeral-отказ).
- Проверка иерархии ролей через utils.ensure_can_moderate — учитывает и роль
  бота, и роль модерирующего участника, и неприкосновенность владельца.
- Все действия логируются в LOG_CHANNEL_ID (если задан) красивым embed'ом.
- Любая ошибка -> try/except -> красный embed юзеру + traceback в bot.log.
"""

from __future__ import annotations

from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from config import LOG_CHANNEL_ID
from utils import (
    HierarchyError,
    WarningStore,
    ensure_can_moderate,
    error_embed,
    format_seconds,
    info_embed,
    log,
    make_embed,
    parse_duration,
    success_embed,
)


class Moderation(commands.Cog):
    """Cog со всеми модерационными слэш-командами."""

    def __init__(self, bot: commands.Bot, warnings: WarningStore) -> None:
        self.bot = bot
        self.warnings = warnings

    # ------------------------------------------------------------------
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ------------------------------------------------------------------

    async def _send_mod_log(self, embed: discord.Embed) -> None:
        """Пишет embed в канал логов модерации (если настроен).

        Ошибку отправки НЕ пробрасываем в команду: логирование — фоновая
        функция, модерация уже выполнена, роллить её из-за битого канала
        неправильно. Пишем warning в bot.log.
        """
        if LOG_CHANNEL_ID is None:
            return
        channel = self.bot.get_channel(LOG_CHANNEL_ID)
        if channel is None:
            log.warning("LOG_CHANNEL_ID=%s не найден (бот не в канале/нет доступа)", LOG_CHANNEL_ID)
            return
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            log.warning("Нет прав на запись в канал логов %s", LOG_CHANNEL_ID)
        except Exception:
            log.exception("Не удалось отправить лог модерации в канал %s", LOG_CHANNEL_ID)

    @staticmethod
    def _resolve_member(interaction: discord.Interaction, member: discord.Member | None) -> discord.Member:
        """Достаёт Member из гильдии с проверками. Бросает ValueError с
        человекочитаемым текстом (вызывающий код превратит его в embed)."""
        guild = interaction.guild
        if guild is None:
            raise ValueError("Команда доступна только на сервере.")
        if member is None:
            raise ValueError("Участник не найден на этом сервере. Укажите ник или ID участника, который здесь состоит.")
        # На всякий случай сверяем, что объект действительно из этой гильдии.
        resolved = guild.get_member(member.id)
        if resolved is None:
            raise ValueError("Участник не найден на этом сервере.")
        return resolved

    def _moderator_fields(self, interaction: discord.Interaction, target: discord.Member, reason: str) -> dict[str, str]:
        """Стандартный набор полей для логов модерации."""
        return {
            "Участник": f"{target.mention} (`{target.id}`)",
            "Модератор": f"{interaction.user} (`{interaction.user.id}`)",
            "Причина": reason,
        }

    # ------------------------------------------------------------------
    # /kick
    # ------------------------------------------------------------------

    @app_commands.command(name="kick", description="Кикнуть участника с сервера с причиной")
    @app_commands.describe(member="Участник для кика", reason="Причина кика")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.checks.bot_has_permissions(kick_members=True)
    async def kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
        reason: str = "Причина не указана",
    ) -> None:
        try:
            target = self._resolve_member(interaction, member)
            # Иерархия: проверяем и от лица бота (реальный исполнитель),
            # и от лица модера (чтобы модер не «одолжил» права бота на равных).
            ensure_can_moderate(interaction.guild.me, target, "kick")
            ensure_can_moderate(interaction.user, target, "kick")

            await target.kick(reason=f"[{interaction.user}] {reason}")

            await interaction.response.send_message(
                embed=success_embed(
                    f"Участник {target.mention} кикнут с сервера.",
                    title="✅ Кик выполнен",
                    fields=self._moderator_fields(interaction, target, reason),
                ),
                ephemeral=False,
            )
            await self._send_mod_log(
                make_embed("📤 Модерация: KICK", "", discord.Color.orange(),
                           fields=self._moderator_fields(interaction, target, reason))
            )
            log.info("KICK: %s -> %s | причина: %s", interaction.user, target, reason)
        except ValueError as e:
            await interaction.response.send_message(embed=error_embed(str(e)), ephemeral=True)
        except HierarchyError as e:
            await interaction.response.send_message(embed=error_embed(str(e)), ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed("Discord отклонил действие: не хватает прав (проверьте иерархию ролей бота)."),
                ephemeral=True,
            )
        except Exception:
            log.exception("Ошибка в /kick")
            await interaction.response.send_message(
                embed=error_embed("Произошла непредвиденная ошибка. Подробности в логах."),
                ephemeral=True,
            )

    # ------------------------------------------------------------------
    # /ban
    # ------------------------------------------------------------------

    @app_commands.command(name="ban", description="Забанить участника с сервера")
    @app_commands.describe(
        member="Участник для бана",
        reason="Причина бана",
        delete_days="Удалять сообщения за последние N дней (0–7)",
    )
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    async def ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
        reason: str = "Причина не указана",
        delete_days: app_commands.Range[int, 0, 7] = 0,
    ) -> None:
        try:
            target = self._resolve_member(interaction, member)
            ensure_can_moderate(interaction.guild.me, target, "ban")
            ensure_can_moderate(interaction.user, target, "ban")

            await target.ban(
                reason=f"[{interaction.user}] {reason}",
                delete_message_days=delete_days,
            )

            desc = f"Участник {target.mention} забанен."
            if delete_days:
                desc += f"\nУдалены сообщения за последние {delete_days} дн."
            await interaction.response.send_message(
                embed=success_embed(desc, title="✅ Бан выполнен",
                                    fields=self._moderator_fields(interaction, target, reason)),
            )
            await self._send_mod_log(
                make_embed("⛔ Модерация: BAN", "", discord.Color.red(),
                           fields={**self._moderator_fields(interaction, target, reason),
                                   "Удаление сообщений": f"за {delete_days} дн."})
            )
            log.info("BAN: %s -> %s | %d дн. сообщений | причина: %s",
                     interaction.user, target, delete_days, reason)
        except ValueError as e:
            await interaction.response.send_message(embed=error_embed(str(e)), ephemeral=True)
        except HierarchyError as e:
            await interaction.response.send_message(embed=error_embed(str(e)), ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed("Discord отклонил бан: не хватает прав (проверьте иерархию ролей бота)."),
                ephemeral=True,
            )
        except Exception:
            log.exception("Ошибка в /ban")
            await interaction.response.send_message(
                embed=error_embed("Произошла непредвиденная ошибка. Подробности в логах."),
                ephemeral=True,
            )

    # ------------------------------------------------------------------
    # /unban
    # ------------------------------------------------------------------

    @app_commands.command(name="unban", description="Разбанить участника по ID")
    @app_commands.describe(user_id="ID забаненного пользователя", reason="Причина разбана")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    async def unban(
        self,
        interaction: discord.Interaction,
        user_id: str,
        reason: str = "Причина не указана",
    ) -> None:
        try:
            # user_id принимаем строкой и парсим сами: так мы покажем
            # понятную ошибку вместо системной валидации app_commands.
            try:
                uid = int(user_id)
            except ValueError:
                raise ValueError("ID должен быть числом (snowflake). Пример: 123456789012345678")

            # entry.ban() требует discord.Object / User; Object экономит REST-запрос.
            await interaction.guild.unban(
                discord.Object(id=uid),
                reason=f"[{interaction.user}] {reason}",
            )

            await interaction.response.send_message(
                embed=success_embed(
                    f"Пользователь `{uid}` разбанен.",
                    title="✅ Разбан выполнен",
                    fields={"Модератор": f"{interaction.user}", "Причина": reason},
                ),
            )
            await self._send_mod_log(
                make_embed("🔓 Модерация: UNBAN", "", discord.Color.green(),
                           fields={"Пользователь": f"`{uid}`",
                                   "Модератор": f"{interaction.user}",
                                   "Причина": reason})
            )
            log.info("UNBAN: %s -> user_id=%s | причина: %s", interaction.user, uid, reason)
        except discord.NotFound:
            await interaction.response.send_message(
                embed=error_embed(f"Пользователь `{user_id}` не найден в бан-листе сервера."),
                ephemeral=True,
            )
        except ValueError as e:
            await interaction.response.send_message(embed=error_embed(str(e)), ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed("Нет прав на разбан (ban_members у бота)."), ephemeral=True,
            )
        except Exception:
            log.exception("Ошибка в /unban")
            await interaction.response.send_message(
                embed=error_embed("Произошла непредвиденная ошибка. Подробности в логах."),
                ephemeral=True,
            )

    # ------------------------------------------------------------------
    # /mute (timeout)
    # ------------------------------------------------------------------

    @app_commands.command(name="mute", description="Выдать участнику тайм-аут (например: 10m, 1h, 1d)")
    @app_commands.describe(
        member="Участник",
        duration="Длительность: 1m, 30m, 1h, 2h, 1d ... (макс. 28d)",
        reason="Причина тайм-аута",
    )
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    async def mute(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
        duration: str = "10m",
        reason: str = "Причина не указана",
    ) -> None:
        try:
            target = self._resolve_member(interaction, member)
            ensure_can_moderate(interaction.guild.me, target, "mute")
            ensure_can_moderate(interaction.user, target, "mute")

            seconds = parse_duration(duration)
            until = discord.utils.utcnow() + timedelta(seconds=seconds)
            await target.timeout(until, reason=f"[{interaction.user}] {reason}")

            await interaction.response.send_message(
                embed=success_embed(
                    f"Участник {target.mention} отправлен в тайм-аут на **{format_seconds(seconds)}**.",
                    title="🔇 Тайм-аут выдан",
                    fields=self._moderator_fields(interaction, target, reason),
                ),
            )
            await self._send_mod_log(
                make_embed("🔇 Модерация: MUTE", "", discord.Color.dark_grey(),
                           fields={**self._moderator_fields(interaction, target, reason),
                                   "Длительность": format_seconds(seconds)})
            )
            log.info("MUTE: %s -> %s | %s сек | причина: %s", interaction.user, target, seconds, reason)
        except ValueError as e:
            await interaction.response.send_message(embed=error_embed(str(e)), ephemeral=True)
        except HierarchyError as e:
            await interaction.response.send_message(embed=error_embed(str(e)), ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed("Нет прав moderate_members у бота или участника."), ephemeral=True,
            )
        except Exception:
            log.exception("Ошибка в /mute")
            await interaction.response.send_message(
                embed=error_embed("Произошла непредвиденная ошибка. Подробности в логах."),
                ephemeral=True,
            )

    # ------------------------------------------------------------------
    # /unmute
    # ------------------------------------------------------------------

    @app_commands.command(name="unmute", description="Снять тайм-аут с участника")
    @app_commands.describe(member="Участник", reason="Причина снятия тайм-аута")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    async def unmute(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
        reason: str = "Причина не указана",
    ) -> None:
        try:
            target = self._resolve_member(interaction, member)
            ensure_can_moderate(interaction.guild.me, target, "unmute")
            ensure_can_moderate(interaction.user, target, "unmute")

            if target.is_timed_out():
                await target.timeout(None, reason=f"[{interaction.user}] {reason}")
                result = f"Тайм-аут у {target.mention} снят."
            else:
                # Не ошибка, но полезно сообщить: участник и так без тайм-аута.
                result = f"У {target.mention} не было активного тайм-аута."

            await interaction.response.send_message(
                embed=success_embed(result, title="🔊 Тайм-аут снят",
                                    fields=self._moderator_fields(interaction, target, reason)),
            )
            await self._send_mod_log(
                make_embed("🔊 Модерация: UNMUTE", "", discord.Color.light_grey(),
                           fields=self._moderator_fields(interaction, target, reason))
            )
            log.info("UNMUTE: %s -> %s | причина: %s", interaction.user, target, reason)
        except ValueError as e:
            await interaction.response.send_message(embed=error_embed(str(e)), ephemeral=True)
        except HierarchyError as e:
            await interaction.response.send_message(embed=error_embed(str(e)), ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed("Нет прав moderate_members у бота или участника."), ephemeral=True,
            )
        except Exception:
            log.exception("Ошибка в /unmute")
            await interaction.response.send_message(
                embed=error_embed("Произошла непредвиденная ошибка. Подробности в логах."),
                ephemeral=True,
            )

    # ------------------------------------------------------------------
    # /warn
    # ------------------------------------------------------------------

    @app_commands.command(name="warn", description="Выдать участнику предупреждение")
    @app_commands.describe(member="Участник", reason="Причина предупреждения")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
        reason: str = "Причина не указана",
    ) -> None:
        try:
            target = self._resolve_member(interaction, member)
            # Предупреждение — мягкое действие, но иерархию всё равно соблюдаем:
            # выдавать варны равным/старшим по ролям нельзя.
            ensure_can_moderate(interaction.user, target, "warn")

            count = await self.warnings.add(interaction.guild.id, target.id, interaction.user, reason)

            # Пытаемся уведомить нарушителя в ЛС. Отказ (закрытые ЛС) — не ошибка.
            dm_note = ""
            try:
                await target.send(
                    embed=info_embed(
                        f"Вам выдано предупреждение #{count} на сервере **{interaction.guild.name}**.\n"
                        f"**Причина:** {reason}\n**Модератор:** {interaction.user}",
                        title="⚠️ Предупреждение",
                    )
                )
                dm_note = " Нарушителю отправлено уведомление в ЛС."
            except discord.Forbidden:
                dm_note = " (нарушитель закрыл ЛС — уведомление не доставлено)"
            except Exception:
                log.exception("Не удалось отправить ЛС-уведомление о варне")

            await interaction.response.send_message(
                embed=success_embed(
                    f"Участнику {target.mention} выдано предупреждение №{count}.{dm_note}",
                    title="⚠️ Предупреждение выдано",
                    fields=self._moderator_fields(interaction, target, reason),
                ),
            )
            await self._send_mod_log(
                make_embed("⚠️ Модерация: WARN", "", discord.Color.gold(),
                           fields={**self._moderator_fields(interaction, target, reason),
                                   "Всего предупреждений": str(count)})
            )
            log.info("WARN: %s -> %s #%s | причина: %s", interaction.user, target, count, reason)
        except ValueError as e:
            await interaction.response.send_message(embed=error_embed(str(e)), ephemeral=True)
        except HierarchyError as e:
            await interaction.response.send_message(embed=error_embed(str(e)), ephemeral=True)
        except Exception:
            log.exception("Ошибка в /warn")
            await interaction.response.send_message(
                embed=error_embed("Произошла непредвиденная ошибка. Подробности в логах."),
                ephemeral=True,
            )

    # ------------------------------------------------------------------
    # /warnings
    # ------------------------------------------------------------------

    @app_commands.command(name="warnings", description="Показать список предупреждений участника")
    @app_commands.describe(member="Участник")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warnings_list(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        try:
            target = self._resolve_member(interaction, member)
            history = await self.warnings.get(interaction.guild.id, target.id)

            if not history:
                await interaction.response.send_message(
                    embed=info_embed(f"У {target.mention} нет предупреждений. 🎉",
                                     title="📋 Предупреждения"),
                )
                return

            # Embed ограничен ~1024 символами в description — формируем список
            # с обрезкой, чтобы не словать TypeError от Discord.
            lines = []
            for i, w in enumerate(history, start=1):
                ts = w.get("timestamp", "?")[:10]
                lines.append(f"**#{i}** `{ts}` — {w['reason']}\n↳ выдал: {w['moderator_name']}")
            body = "\n\n".join(lines)
            if len(body) > 1000:
                # Предсказуемое поведение: показываем последние записи целиком,
                # older скрываем с явной пометкой о лимите embed'а.
                trimmed: list[str] = []
                used = 0
                for line in reversed(lines):
                    if used + len(line) + 2 > 990:
                        break
                    trimmed.insert(0, line)
                    used += len(line) + 2
                hidden = len(lines) - len(trimmed)
                body = ("\n\n".join(trimmed)
                        + (f"\n\n…и ещё {hidden} шт. скрыто (лимит embed)." if hidden else ""))

            await interaction.response.send_message(
                embed=info_embed(
                    body,
                    title=f"📋 Предупреждения: {target.display_name}",
                    footer=f"Всего: {len(history)}",
                ),
            )
        except ValueError as e:
            await interaction.response.send_message(embed=error_embed(str(e)), ephemeral=True)
        except Exception:
            log.exception("Ошибка в /warnings")
            await interaction.response.send_message(
                embed=error_embed("Произошла непредвиденная ошибка. Подробности в логах."),
                ephemeral=True,
            )

    # ------------------------------------------------------------------
    # /clear
    # ------------------------------------------------------------------

    @app_commands.command(name="clear", description="Удалить N сообщений в текущем канале (до 100)")
    @app_commands.describe(amount="Количество сообщений (1–100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.checks.bot_has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]) -> None:
        try:
            # defer обязательна: purge может длиться >3 секунд, иначе interaction
            # истечёт. Затем ephemeral-ответ с итогом.
            await interaction.response.defer(ephemeral=True, thinking=True)
            deleted = await interaction.channel.purge(limit=amount)
            await interaction.followup.send(
                embed=success_embed(
                    f"Удалено сообщений: **{len(deleted)}** в канале {interaction.channel.mention}.",
                    title="🧹 Очистка выполнена",
                ),
                ephemeral=True,
            )
            await self._send_mod_log(
                make_embed("🧹 Модерация: CLEAR", "", discord.Color.dark_teal(),
                           fields={"Канал": f"{interaction.channel.mention} (`{interaction.channel.id}`)",
                                   "Модератор": f"{interaction.user} (`{interaction.user.id}`)",
                                   "Удалено": str(len(deleted))})
            )
            log.info("CLEAR: %s -> #%s x%d", interaction.user, getattr(interaction.channel, 'name', '?'), len(deleted))
        except discord.Forbidden:
            await interaction.followup.send(
                embed=error_embed("Нет прав manage_messages (у вас или у бота)."), ephemeral=True,
            )
        except Exception:
            log.exception("Ошибка в /clear")
            await interaction.followup.send(
                embed=error_embed("Произошла непредвиденная ошибка. Подробности в логах."),
                ephemeral=True,
            )

    # ------------------------------------------------------------------
    # /slowmode
    # ------------------------------------------------------------------

    @app_commands.command(name="slowmode", description="Установить слоумод в канале (секунды, 0 = выключить)")
    @app_commands.describe(
        seconds="Задержка между сообщениями, сек (0–21600; 0 — выключить)",
        channel="Канал (по умолчанию — текущий)",
    )
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    async def slowmode(
        self,
        interaction: discord.Interaction,
        seconds: app_commands.Range[int, 0, 21600],
        channel: discord.TextChannel | None = None,
    ) -> None:
        try:
            target_channel = channel or interaction.channel
            if not isinstance(target_channel, (discord.TextChannel, discord.VoiceChannel, discord.ForumChannel)):
                raise ValueError("Слоумод можно установить только в текстовом/голосовом/форум-канале.")

            await target_channel.edit(slowmode_delay=seconds, reason=f"[{interaction.user}] slowmode")

            status = "выключен" if seconds == 0 else f"{seconds} сек"
            await interaction.response.send_message(
                embed=success_embed(
                    f"Слоумод в {target_channel.mention}: **{status}**.",
                    title="🐢 Слоумод обновлён",
                    fields={"Модератор": f"{interaction.user}"},
                ),
            )
            await self._send_mod_log(
                make_embed("🐢 Модерация: SLOWMODE", "", discord.Color.teal(),
                           fields={"Канал": f"{target_channel.mention} (`{target_channel.id}`)",
                                   "Модератор": f"{interaction.user} (`{interaction.user.id}`)",
                                   "Новый слоумод": status})
            )
            log.info("SLOWMODE: %s -> #%s = %s", interaction.user, target_channel.name, seconds)
        except ValueError as e:
            await interaction.response.send_message(embed=error_embed(str(e)), ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed("Нет прав manage_channels (у вас или у бота)."), ephemeral=True,
            )
        except Exception:
            log.exception("Ошибка в /slowmode")
            await interaction.response.send_message(
                embed=error_embed("Произошла непредвиденная ошибка. Подробности в логах."),
                ephemeral=True,
            )


async def setup(bot: commands.Bot) -> None:
    """Точка загрузки кога: discord.py сам вызовет её при load_extension.
    Хранилище варнов создаём здесь же — оно нужно только этому когу."""
    from config import WARNINGS_FILE
    await bot.add_cog(Moderation(bot, WarningStore(WARNINGS_FILE)))
