# ChatGPT-Mirror на macOS: с Docker и без Docker

Эта инструкция предназначена для **macOS на Apple Silicon (M1/M2/M3/M4/новее) или Intel**. Для обеих архитектур команды одинаковы, кроме возможной эмуляции старых x86-образов Docker.

> **Ограничение проекта:** исходники `chatgpt-gateway` и `cf5s` не опубликованы. Без них **чат не работает**. В Docker-варианте их старые сторонние образы можно *отдельно* включить, но их безопасность, поддержка текущего ChatGPT и возможность запуска на Mac **не проверены**. Не передавайте им рабочие аккаунты или токены без самостоятельного аудита.

**Для полного accessToken-сайта в закрытой локальной сети, где только Mac-сервер имеет интернет, используйте [отдельное руководство LAN_SETUP_RU.md](LAN_SETUP_RU.md) и `docker-compose.lan.yml`.** Это отдельный экспериментальный режим с оригинальными закрытыми gateway/cf5s, а не схема с OpenAI API-ключом.

## Что выбрать

| Вариант | Панель RU/EN | Django API | Чат |
|---|---|---|---|
| **A. Docker, только открытый код (по умолчанию)** | Да | Да | Нет |
| **A+. Docker со старым закрытым gateway, по вашему явному решению** | Да | Да | Возможно; не гарантируется |
| **B. Без Docker, полностью нативно** | Да | Да | Нет, пока не предоставлен отдельный совместимый gateway |

Для начала лучше **A**: Docker изолирует окружение, и его проще остановить/удалить. Публикация сервиса в Интернет не поддерживается этим локальным руководством.

## Общая подготовка для обоих вариантов

Откройте **Terminal.app** (`Applications → Utilities → Terminal`). Установите Command Line Tools, если их нет:

```bash
xcode-select -p || xcode-select --install
```

Для установки Homebrew используйте [официальную инструкцию](https://brew.sh/) (прочитайте, что будет устанавливаться):

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

В свежем Terminal проверьте `brew --version`. Если `brew` ещё не находится в PATH, инициализируйте его:

```bash
if [ -x /opt/homebrew/bin/brew ]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [ -x /usr/local/bin/brew ]; then
  eval "$(/usr/local/bin/brew shellenv)"
fi
brew --version
```

Установите Git и Python 3.12; это пригодится для генерации секретов в обоих вариантах:

```bash
brew install git python@3.12
export PATH="$(brew --prefix python@3.12)/libexec/bin:$PATH"
```

Скачайте **ваш форк**, а не репозиторий первоначального автора:

```bash
cd ~
git clone https://github.com/tranzistrina/ChatGPT-Mirror.git
cd ChatGPT-Mirror
```

Если каталог уже создан, вместо `git clone` используйте `cd ~/ChatGPT-Mirror && git pull`.

---

## Вариант A: установка на Mac с Docker Desktop

### A1. Поставьте Docker Desktop

Скачайте [Docker Desktop for Mac](https://docs.docker.com/desktop/setup/install/mac-install/), выбрав **Apple Silicon** или **Intel** под ваш процессор. Установите, откройте Docker.app и дождитесь запуска движка Docker.

Проверьте в Terminal:

```bash
docker version
docker compose version
```

`docker compose` входит в Docker Desktop.

### A2. Создайте файл с личными настройками

В каталоге `~/ChatGPT-Mirror`:

```bash
cp .env.native.example .env.docker
python3 - <<'PY'
from pathlib import Path
from secrets import token_hex

p = Path(".env.docker")
s = p.read_text()
s = s.replace("REPLACE_WITH_RANDOM_SECRET", token_hex(48))
s = s.replace("REPLACE_WITH_LONG_RANDOM_PASSWORD", token_hex(24))
p.write_text(s)
PY
chmod 600 .env.docker
```

Здесь будет пароль администратора. Узнать его можно так:

```bash
grep '^ADMIN_PASSWORD=' .env.docker
```

Имя пользователя: `admin`. Не публикуйте файл `.env.docker` и не храните пароль в чужих чатах или issue на GitHub.

### A3. Соберите и запустите **свою изменённую** версию

```bash
docker compose -f docker-compose.mac.yml up -d --build web
```

После запуска откройте **http://127.0.0.1:50002/admin/** и войдите с логином `admin` и паролем из `.env.docker`.

**Важно:** используется именно **`docker-compose.mac.yml`**, а не старый `docker-compose.yml` и не `deploy.sh`. Старый compose скачивает `dairoot/chatgpt-mirror:latest` и не использует изменения вашего репозитория.

Новый compose:

- собирает панель из актуальных исходников;
- слушает порт **только на `127.0.0.1`**;
- сохраняет SQLite в Docker volume;
- **не запускает Watchtower**, у которого в исходном compose есть доступ к Docker socket;
- по умолчанию **не загружает закрытые gateway/cf5s**.

Проверить состояние и логи:

```bash
docker compose -f docker-compose.mac.yml ps
docker compose -f docker-compose.mac.yml logs -f web
```

Остановить:

```bash
docker compose -f docker-compose.mac.yml down
```

Данные при `down` сохраняются. **Не запускайте `down -v`**, если не хотите удалить базу данных.

### A4. Необязательно: попробовать оригинальный закрытый gateway

Только если вы сознательно согласны запускать **непроверенные бинарные образы** автора проекта:

```bash
docker compose -f docker-compose.mac.yml --profile legacy-gateway up -d --build
```

Эта команда *попытается* скачать и запустить:

- `dairoot/chatgpt-gateway:latest`;
- `dairoot/cf5s:latest`;
- Redis.

У gateway/cf5s в Compose установлена архитектура `linux/amd64`: на Apple Silicon возможна эмуляция через Docker Desktop, **но это не гарантия запуска**. Сами образы могут оказаться недоступны; совместимость с актуальным ChatGPT также не подтверждена.

Проверка:

```bash
docker compose -f docker-compose.mac.yml --profile legacy-gateway ps
docker compose -f docker-compose.mac.yml --profile legacy-gateway logs --tail=80 gateway cf5s
```

Остановка всех контейнеров (с сохранением данных):

```bash
docker compose -f docker-compose.mac.yml --profile legacy-gateway down
```

В контейнере `web` оригинальный entrypoint запускает Django через `runserver`, поэтому даже эта конфигурация **предназначена только для локального тестирования**, не для публичного сервера.

---

## Вариант B: установка на Mac **без Docker**

### B1. Установите зависимости

Homebrew из раздела выше уже установлен. В терминале:

```bash
brew install python@3.12 node@22 caddy
export PATH="$(brew --prefix python@3.12)/libexec/bin:$(brew --prefix node@22)/bin:$PATH"
python3 --version
node --version
npm --version
caddy version
```

Python должен быть **3.12+**, Node **22.x**. Если терминал закрыть, на новом сеансе повторите `export PATH=...` (или добавьте строку в `~/.zshrc`).

### B2. Создайте настройки

В каталоге `~/ChatGPT-Mirror`:

```bash
cp .env.native.example .env.native
python3 - <<'PY'
from pathlib import Path
from secrets import token_hex

p = Path(".env.native")
s = p.read_text()
s = s.replace("REPLACE_WITH_RANDOM_SECRET", token_hex(48))
s = s.replace("REPLACE_WITH_LONG_RANDOM_PASSWORD", token_hex(24))
p.write_text(s)
PY
chmod 600 .env.native
```

Посмотреть пароль:

```bash
grep '^ADMIN_PASSWORD=' .env.native
```

`CHATGPT_GATEWAY_URL=http://127.0.0.1:8787` и `GATEWAY_UPSTREAM=127.0.0.1:8787` в примере **не устанавливают gateway**. Это только адреса, которые заработают, если вы отдельно развернёте действительно совместимый и проверенный сервис.

### B3. Установка и запуск

```bash
chmod +x scripts/install_native.sh scripts/run_native.sh
./scripts/install_native.sh
./scripts/run_native.sh
```

Откройте **http://127.0.0.1:50002/admin/**. Логин `admin`, пароль из `.env.native`.

Приложение работает, пока открыт терминал. `Ctrl+C` останавливает Caddy и Django. Повторный запуск:

```bash
cd ~/ChatGPT-Mirror
export PATH="$(brew --prefix python@3.12)/libexec/bin:$(brew --prefix node@22)/bin:$PATH"
./scripts/run_native.sh
```

На этом этапе работоспособна административная панель, но **сам чат** без отдельного gateway не заработает.

При необходимости на macOS можно настроить фоновый запуск через `launchd`, но текущие скрипты и планировщик заданий **не настроены как сервис macOS**.

---

## Ошибки и вопросы

| Проблема | Что делать |
|---|---|
| `brew: command not found` | Инициализируйте Homebrew через `brew shellenv` из общей подготовки |
| `python3` слишком старый | Выполните `export PATH="$(brew --prefix python@3.12)/libexec/bin:$PATH"` |
| `node` не найден | Добавьте `$(brew --prefix node@22)/bin` в PATH |
| `Cannot connect to the Docker daemon` | Запустите Docker.app и дождитесь готовности |
| `no matching manifest` / ошибка запуска gateway на M-серии | Старый закрытый образ не поддерживает вашу архитектуру или эмуляцию |
| `502 Bad Gateway` по адресу `/` | Без отдельного gateway это ожидаемо |
| Порт `50002` занят | Остановите другую версию проекта; одновременно два способа на одном порту не запускайте |
| Не принимает пароль | Проверьте `.env.native` или `.env.docker` соответственно |
| Docker-контейнеры работают, а переводов нет | Вы запустили старый `docker-compose.yml` вместо `docker-compose.mac.yml` |

**Предупреждение по безопасности:** в upstream были уязвимости, часть которых исправлена в этой ветке. Но зависимости остаются устаревшими, токены хранятся в SQLite без отдельного шифрования, а оригинальный gateway не проходил аудит. Не используйте эту сборку как доверенный публичный сервис. Подробности: [SECURITY_REVIEW_RU.md](SECURITY_REVIEW_RU.md).

Исходная лицензия GPL-3.0.
