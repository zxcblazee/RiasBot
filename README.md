# 🛡️ Discord Admin Bot

Полноценный бот-администратор для Discord на **Python 3.11+** (включая 3.14) и **discord.py 2.6**.
Все команды — слэш-команды (`app_commands`), код разбит на коги, конфигурация — через `.env`.

> ⚙️ Про хостинги (Pterodactyl/Bot-Hosting и т.п.) с Python 3.14: ранее закреплённые
> `discord.py==2.4.0` + `aiohttp==3.10.11` на 3.14 не устанавливаются — aiohttp
> собирается из исходников и компиляция убивается по памяти (`gcc: Killed signal`).
> В `requirements.txt` теперь версии с готовыми wheels под CPython 3.14
> (`discord.py==2.6.0`, `aiohttp==3.13.0`) — установка идёт без gcc.

## Возможности

| Ког | Команды |
|---|---|
| 🛡️ Модерация (`cogs/moderation.py`) | `/kick`, `/ban`, `/unban`, `/mute`, `/unmute`, `/warn`, `/warnings`, `/clear`, `/slowmode` |
| 🧰 Утилиты (`cogs/utility.py`) | `/poll`, `/say`, `/embed`, `/userinfo` |
| ℹ️ Информация (`cogs/info.py`) | `/serverinfo`, `/ping`, `/help` |

Особенности:
- ✅ Проверка прав пользователя и бота (вежливый ephemeral-отказ).
- ✅ Защита иерархии ролей: нельзя модерировать равных/старших по роли и владельца сервера; бот не забанит себя и других ботов.
- ✅ Предупреждения сохраняются в `data/warnings.json` (атомарная запись, защита от повреждения).
- ✅ Логи модерации в отдельный канал (`LOG_CHANNEL_ID`).
- ✅ Логирование в `bot.log` + консоль, все ошибки с полным traceback.

## Структура проекта

```
.
├── main.py              # точка входа: загрузка когов, sync команд, обработчик ошибок
├── config.py            # загрузка и валидация .env (никаких токенов в коде)
├── utils.py             # логгер, embed-фабрики, парсер времени, проверки иерархии, WarningStore
├── cogs/
│   ├── moderation.py    # /kick /ban /unban /mute /unmute /warn /warnings /clear /slowmode
│   ├── utility.py       # /poll /say /embed /userinfo
│   └── info.py          # /serverinfo /ping /help
├── data/                # warnings.json создаётся автоматически
├── requirements.txt
├── .env.example         # шаблон конфигурации
└── README.md
```

---

## Шаг 1. Создание бота в Discord Developer Portal

1. Откройте <https://discord.com/developers/applications> → **New Application**, дайте имя.
2. Вкладка **Bot** → **Reset Token** → скопируйте токен (это ваш `DISCORD_TOKEN`).
   ⚠️ Токен = пароль бота: никому не давайте, в код не вставляйте.
3. На той же вкладке **Bot** включите **Privileged Gateway Intents** (у бота `Intents.all()`):
   - ✅ Server Members Intent
   - ✅ Message Content Intent
   - ✅ Presence Intent
4. Сохраните изменения.

## Шаг 2. Пригласить бота на сервер

1. Вкладка **OAuth2 → URL Generator**: scopes = `bot` + `applications.commands`.
2. Bot Permissions: минимум `Kick Members`, `Ban Members`, `Moderate Members`,
   `Manage Messages`, `Manage Channels`, `Send Messages`, `Embed Links`, `Add Reactions`, `Read Message History`.
3. Откройте сгенерированную ссылку, выберите сервер, пригласите.
4. **Важно:** в «Настройки сервера → Роли» поднимите роль бота **выше** ролей участников,
   которых планируете модерировать (иначе Discord отклонит kick/ban/timeout).

## Шаг 3. Узнать ID

Включите режим разработчика: *Настройки пользователя → Расширенные → Режим разработчика*.
Затем ПКМ:
- по названию сервера → **Copy Server ID** → это `GUILD_ID`;
- по каналу для логов модерации → **Copy Channel ID** → это `LOG_CHANNEL_ID` (необязательно).

## Шаг 4. Установка и настройка

```bash
# Python 3.11+ должен быть установлен
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # Windows: copy .env.example .env
# откройте .env и заполните DISCORD_TOKEN, GUILD_ID, (опц.) LOG_CHANNEL_ID
```

## Шаг 5. Запуск

```bash
python main.py
```

При успехе в консоли/bot.log появится:
`Бот онлайн: Name#1234 ...` и `Слэш-команды синхронизированы: 16 шт.`
Команды появятся в поле ввода Discord на вашем сервере мгновенно
(регистрация скоупнута на конкретную гильдию).

---

## Быстрая инструкция по командам

- `/mute @user duration=1h30m reason=флуд` — тайм-аут форматами `s/m/h/d`, максимум 28 дней.
- `/ban @user delete_days=7` — бан с удалением сообщений за неделю.
- `/unban user_id=123456789` — ID берётся из аудита или профиля (ПКМ → Copy User ID).
- `/warn` хранит историю в `data/warnings.json`, `/warnings @user` её показывает.
- `/clear amount=50` — удаление до 100 сообщений (ответ виден только вам).
- `/slowmode seconds=10 [channel=#общение]` — `0` выключает слоумод.
- `/poll` — опрос на 2–5 вариантов, голосование реакциями 1️⃣–5️⃣.

## Неисправности

| Симптом | Решение |
|---|---|
| Бот не запускается: `PrivilegedIntentsRequired` | Включите привилегированные интенты (Шаг 1.3) |
| `LoginFailure` | Неверный токен — возьмите новый через Reset Token |
| Слэш-команд не видно | Бот должен быть на сервере из `GUILD_ID`; перезапустите для повторного sync |
| Kick/Ban не работают | Роль бота ниже целевой — поднимьте её в настройках сервера |
| Логи модерации не пишутся | Проверьте `LOG_CHANNEL_ID` и права бота в канале |
