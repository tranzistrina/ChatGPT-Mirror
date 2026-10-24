# ChatGPT-Mirror: установка без Docker на Ubuntu 24.04 LTS

> **Важно:** эта инструкция запускает открытую панель Vue, API Django и Caddy. **Сам чат не заработает**, пока нет отдельно развёрнутого совместимого `chatgpt-gateway`. Исходников gateway и cf5s в проекте нет, а готовые образы не проходили аудит. Не вводите реальные токены и не публикуйте сервис, пока это не исправлено.

## 1. Установите системные пакеты

Все команды выполняйте в терминале Ubuntu 24.04 (не от root).

```bash
sudo apt update
sudo apt install -y git curl ca-certificates python3 python3-venv python3-pip caddy
python3 --version
caddy version
```

Нужен Python 3.12 или новее. Если Caddy не находится в apt, воспользуйтесь [официальной инструкцией Caddy](https://caddyserver.com/docs/install).

## 2. Установите Node.js 22

Для Ubuntu удобно использовать [nvm](https://github.com/nvm-sh/nvm). Команда ниже загружает установочный скрипт nvm; при необходимости сначала просмотрите его.

```bash
curl -fsSLo /tmp/nvm-install.sh https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.8/install.sh
bash /tmp/nvm-install.sh
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
nvm install 22
nvm alias default 22
node --version
npm --version
```

Версия Node должна начинаться с `v22.`.

## 3. Получите репозиторий и настройте секреты

```bash
cd ~
git clone https://github.com/tranzistrina/ChatGPT-Mirror.git
cd ChatGPT-Mirror
cp .env.native.example .env.native
python3 - <<'PY'
from pathlib import Path
from secrets import token_hex
path = Path(".env.native")
text = path.read_text()
text = text.replace("REPLACE_WITH_RANDOM_SECRET", token_hex(48))
text = text.replace("REPLACE_WITH_LONG_RANDOM_PASSWORD", token_hex(24))
path.write_text(text)
PY
chmod 600 .env.native
```

Администратор по умолчанию называется `admin`; его случайный пароль записан в `.env.native` в переменную `ADMIN_PASSWORD`. Не публикуйте этот файл. Можете поменять `ADMIN_USERNAME` через `nano .env.native`.

## 4. Укажите адрес совместимого gateway

По умолчанию в `.env.native` указано:

```dotenv
CHATGPT_GATEWAY_URL=http://127.0.0.1:8787
GATEWAY_UPSTREAM=127.0.0.1:8787
```

**Этот адрес не запустит gateway автоматически.** Если проверенного gateway у вас нет, пропустите его настройку и запустите только панель. Маршруты чата, API gateway и вход в сам ChatGPT работать не будут. Не подставляйте посторонний адрес: этому серверу могут передаваться чувствительные токены.

## 5. Установите Python/Node зависимости и запустите

```bash
chmod +x scripts/install_native.sh scripts/run_native.sh
./scripts/install_native.sh
./scripts/run_native.sh
```

После запуска оставьте терминал открытым. Административная панель доступна **на этом компьютере**:

**http://127.0.0.1:50002/admin/**

Для входа используйте `ADMIN_USERNAME` и `ADMIN_PASSWORD` из `.env.native`. Посмотреть пароль:

```bash
grep '^ADMIN_PASSWORD=' .env.native
```

Чтобы остановить, нажмите `Ctrl+C`. При повторном запуске `./scripts/install_native.sh` не нужен: просто `./scripts/run_native.sh`.

## 6. Если установка на VPS, а не на локальном компьютере

Caddy специально слушает только `127.0.0.1:50002`. **Не открывайте его всему Интернету**; с собственного компьютера создайте SSH-туннель:

```bash
ssh -L 50002:127.0.0.1:50002 USER@SERVER_IP
```

Затем на своём компьютере откройте тот же адрес `http://127.0.0.1:50002/admin/`. Замените USER и SERVER_IP на пользователя и адрес вашего VPS.

## 7. Обновление токенов по расписанию

Если позже будете запускать и проверенный gateway, установите `cron` и настройте задания из Django:

Для обычной установки **этот шаг не нужен**. Если позже будет подключён проверенный gateway, потребуется отдельный cron/systemd timer, запускающий `app.cron.check_access_token` и `app.cron.update_access_token` каждые пять минут **с переменными из `.env.native`**. Простая команда `manage.py crontab add` без передачи секретов в окружение для этой нативной схемы недостаточна.

## Возможные ошибки

- `python3 -m venv` не срабатывает: установите `python3-venv`; нужен Python 3.12+.
- `node` / `npm` не найден: повторно загрузите nvm и выполните `nvm use 22`.
- `caddy` не найден: установите Caddy из apt или официального репозитория.
- `50002: address already in use`: остановите сервис, занявший порт 50002, или выберите другой порт в `Caddyfile.native`.
- `502 Bad Gateway` на главной странице: gateway не работает по указанному адресу. При этом `/admin/` и `/0x/` обслуживаются собственными компонентами.
- После добавления аккаунта ChatGPT ничего не происходит: это ожидаемо без совместимого gateway.
- Если браузер находится на другом компьютере, `127.0.0.1` обозначает **его**, а не VPS; используйте SSH-туннель.

## О безопасности

Проект upstream больше не поддерживается. На время первоначального `npm ci` зафиксированы предупреждения аудита зависимостей. Для веб-публикации потребуется отдельная работа над HTTPS, фаерволом, обновлением пакетов, управлением секретами и аудитом закрытого gateway.

Читайте также [SECURITY_REVIEW_RU.md](SECURITY_REVIEW_RU.md).

Основа: dairoot/ChatGPT-Mirror commit 8c3a24093f8c7b4c72a4ab39fc94afe9f3aacbf7, GPL-3.0.
