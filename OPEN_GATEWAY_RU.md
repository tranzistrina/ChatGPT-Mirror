# Собственный accessToken gateway для macOS и изолированной LAN

Этот экспериментальный gateway написан на Python и находится в каталоге gateway_native/. Он использует *ChatGPT web accessToken*, а НЕ OpenAI API key. Закрытые dairoot/chatgpt-gateway и dairoot/cf5s, Redis и Watchtower для этого варианта **не нужны**.

**Статус: прототип, не проверен с настоящим ChatGPT.** Приватный веб-протокол может требовать дополнительные Sentinel/Conduit-проверки, а ответ иногда идёт через WebSocket-handoff. Эти механизмы ещё не поддерживаются. При их обнаружении код выдаст ошибку вместо выдуманного ответа.

## Архитектура

LAN клиент без интернета -> Mac IP:50002 -> Caddy -> локальная панель Django/Vue + наш gateway -> chatgpt.com.

Страницы чата (HTML, CSS, JS) подгружаются локально без внешнего CDN. Отправку сообщений в интернет делает Mac-сервер.

## Docker на Mac

1. Установите и запустите Docker Desktop for Mac (Apple Silicon или Intel).
2. Скачайте репозиторий или обновите его:

    cd ~
    git clone https://github.com/tranzistrina/ChatGPT-Mirror.git
    cd ChatGPT-Mirror

    Если каталог уже есть: cd ~/ChatGPT-Mirror && git pull

3. Создайте конфигурацию LAN с уникальными секретами:

    python3 scripts/setup_lan_env.py
    nano .env.lan

    Генератор не перезаписывает существующий файл. Укажите настоящий IP Mac в LAN_BIND_IP и LAN_ALLOWED_HOSTS (например, 192.168.1.10). Получить IP Wi-Fi обычно можно командой: ipconfig getifaddr en0

4. Запустите ТОЛЬКО открытый стек:

    docker compose --env-file .env.lan -f docker-compose.open-gateway.yml up -d --build

5. Проверка:

    docker compose --env-file .env.lan -f docker-compose.open-gateway.yml ps
    docker compose --env-file .env.lan -f docker-compose.open-gateway.yml logs --tail=80 web gateway

6. На клиенте в этой LAN откройте http://IP_MAC:50002/admin/ для входа и http://IP_MAC:50002/ для чата. Клиенту внешний интернет не нужен.

Логин администратора по умолчанию admin. Пароль на Mac:

    grep '^ADMIN_PASSWORD=' .env.lan

Через панель добавьте свой действующий ChatGPT accessToken, создайте и свяжите локального пользователя с пулом ChatGPT-аккаунтов. Затем пользователь входит в админ-панель, выбирает назначенный аккаунт и перенаправляется на локальный чат.

Остановка без удаления данных:

    docker compose --env-file .env.lan -f docker-compose.open-gateway.yml down

Не используйте down -v: это удалит SQLite Docker volume.

## Полностью нативно на macOS, без Docker

Нужны Homebrew, Git, Python 3.12, Node.js 22, Caddy:

    brew install git python@3.12 node@22 caddy
    export PATH="$(brew --prefix python@3.12)/libexec/bin:$(brew --prefix node@22)/bin:$PATH"

В каталоге проекта:

    cp .env.native.example .env.native
    python3 -c "import secrets;print(secrets.token_hex(48))"
    nano .env.native

В .env.native вручную задайте выведенный DJANGO_SECRET_KEY, уникальный длинный ADMIN_PASSWORD и добавьте реальный IP Mac:

    DJANGO_ENV=PRODUCTION
    DJANGO_ALLOWED_HOSTS=192.168.1.10,127.0.0.1,localhost
    LAN_BIND_IP=192.168.1.10
    CHATGPT_WEB_MODEL=auto

Эти IP лишь пример. Не коммитьте .env.native в Git.

    chmod +x scripts/install_native.sh scripts/run_native_access_token.sh
    ./scripts/install_native.sh
    ./scripts/run_native_access_token.sh

После запуска интерфейсы доступны на том же IP и порту 50002. Остановка через Ctrl+C. Два способа запуска одновременно использовать нельзя.

## Что есть в gateway

- Серверное подтверждение accessToken через закрытый веб-эндпоинт моделей ChatGPT.
- Методы для Django: get-user-info, login, logout, get-chatgpt-use-count и get-user-use-count.
- Собственные случайные локальные сессии, проверка прав, защита от CSRF через Origin, лимиты сообщений и одновременных запросов.
- Чтение старого формата SSE из chatgpt.com/backend-api/f/conversation; локальная передача текста клиенту.
- RU/EN чат, браузер не обращается к CDN; модель задаётся серверной переменной CHATGPT_WEB_MODEL.

## Что НЕ готово

- **Нет гарантии отправки сообщений в актуальный ChatGPT.** Возможно потребуются дополнительные Sentinel/Conduit проверки и WebSocket-хенд-офф. Эти механизмы не реализованы, капчу мы не обходим.
- Автоматическое обновление accessToken из sessionToken/refreshToken не реализовано. При истечении токена потребуется заново добавить действующий accessToken.
- Mirror Token ссылки не поддерживаются: метод get-mirror-token возвращает пустой список.
- Учёт использования и лимиты моделей в оригинальном gateway не воспроизведены; соответствующие статистические методы возвращают пустые объекты.
- Метод close-chatgpt-memory возвращает статус unsupported: память аккаунта **не отключается**.
- История на сервере между рестартами не сохраняется; клиентский чат тоже сбрасывается при обновлении страницы.
- Сквозного теста с актуальным веб-протоколом ChatGPT нет.

## Безопасность

Токены в Django SQLite исходного форка пока не зашифрованы; изолируйте и резервируйте базу. Сессии нового gateway живут только в памяти, а сам accessToken хранится только на сервере; при перезапуске gateway нужен повторный вход.

По умолчанию LAN-сайт работает по HTTP: внутри сети могут перехватываться данные, в том числе пароли и переписка. Для эксплуатационного доступа нескольких пользователей настройте HTTPS с доверенным локальным сертификатом и фильтруйте доступ фаерволом. Не открывайте порт на внешнюю сеть.

Эта экспериментальная версия не является проверенным безопасным релизом. Работа с приватным протоколом ChatGPT может измениться без предупреждения.
