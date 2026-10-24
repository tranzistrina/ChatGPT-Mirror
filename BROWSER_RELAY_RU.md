# ChatGPT для локальной сети без зеркалирования API

**Это отдельная, простая схема**, не использующая старый ChatGPT-Mirror,
Django, Vue, web accessToken, неофициальный ChatGPT API, Redis или Cloudflare-обход.

На Mac с интернетом запускается настоящий **Chromium**. Другие устройства LAN
открывают защищённую HTTPS-страницу с этим браузером и пользуются настоящим
[chatgpt.com](https://chatgpt.com/) через потоковое изображение/клавиатуру.

Это **не буквальное переадресовывание TLS-пакетов в браузере клиента**: такое
не работает как обычный сайт из-за cookies, ограничений доменов, WebSocket,
TLS и механизмов аутентификации. Все запросы ChatGPT выполняются непосредственно
из Chromium-контейнера на Mac, а LAN-клиенту передаются экран и действия.
В этом варианте не нужно выпрашивать или копировать web accessToken.

Проверенная основа: [LinuxServer.io Chromium](https://docs.linuxserver.io/images/docker-chromium/),
[Security and Hardening](https://docs.linuxserver.io/selkies/user-guide/security/).
Поддерживаются Apple Silicon/arm64 и x86-64. При запуске используется
изолированный Docker-контейнер с сохранённым профилем Chromium. Страница
использует HTTPS со встроенным самоподписанным сертификатом, поэтому при
первом открытии браузер предупредит о недоверенном сертификате.

## Быстрый запуск на Mac 192.168.0.100

Подключитесь к Mac с интернетом. Docker Desktop должен быть уже запущен.

```bash
cd /Users/inh/Documents/lab/ChatGPT-Mirror
git fetch origin
git switch --track origin/feature/simple-chatgpt-browser-relay
```

Если эта ветка уже существует локально, используйте `git switch feature/simple-chatgpt-browser-relay`
и `git pull --ff-only origin feature/simple-chatgpt-browser-relay`.

Освободите порт 50002, если там запущен прежний экспериментальный gateway:

```bash
docker compose --env-file .env.lan -f docker-compose.open-gateway.yml down
```

Если предыдущий запуск использовал `docker-compose.no-auth-test.yml`, у него то
же имя Compose-проекта: команда выше останавливает его тоже. **Не** применяйте
`down -v`, чтобы сохранить прежнюю базу.

Сгенерируйте собственный пароль, не меняя .env.lan:

```bash
python3 scripts/setup_browser_relay.py
cat .env.browser-relay
```

В файле указаны `BROWSER_USER` и `BROWSER_PASSWORD`.
Это **локальные** данные входа в удалённый браузер, а не пароль ChatGPT.
Если IP Mac другой, измените `LAN_BIND_IP` через редактор.

Запустите **отдельный** Compose-файл:

```bash
docker compose --env-file .env.browser-relay \
  -f docker-compose.browser-relay.yml up -d
```

Проверить контейнер:

```bash
docker compose --env-file .env.browser-relay \
  -f docker-compose.browser-relay.yml ps
```

На Mac и на других устройствах LAN (которым доступен Mac) откройте:

**https://192.168.0.100:50002/**

Это `https`, а НЕ `http`. На первой странице браузер предупредит о
самоподписанном TLS-сертификате: только убедившись, что это ваш Mac и
`192.168.0.100`, выберите вариант продолжить. Затем браузер запросит
логин и пароль из `.env.browser-relay` (обычное встроенное окно браузера).
После авторизации появится Chromium, направленный на chatgpt.com.
Зайдите в ChatGPT **внутри этого удалённого Chromium** обычным способом.
Ваши cookies и сеанс сохраняются в Docker volume `browser_profile`.

## Важные ограничения

- **Один удалённый Chromium на всех.** Пользователи с паролем видят одну
  и ту же сессию, чаты и историю, могут перехватывать управление друг у
  друга. Не подходит для независимых пользователей/аккаунтов. Для них
  нужны отдельные контейнеры и профили или система отдельных сессий.
- Для ChatGPT с Mac требуется работающий интернет. LAN-клиентам
  прямой доступ в интернет не нужен, но доступ к Mac:50002 обязателен.
- ChatGPT может запросить подтверждение входа, капчу или заблокировать
  вход из контейнерного Chromium. Эта схема не обходит эти проверки.
- Сотрудники/пользователи с паролем управляют целым удалённым браузером,
  а не только формой ChatGPT. Не открывайте порт в интернет. Никакие
  каталоги Mac или Docker socket внутрь браузера не монтируются.
- Историю и cookies удалённого браузера хранит Docker volume. Он
  переживает `down`, если не указывать `-v`.
- Пароль браузерного шлюза и отдельный логин ChatGPT не связаны. Если
  пароль слишком широко известен, замените `BROWSER_PASSWORD` в
  `.env.browser-relay` и пересоздайте контейнер.

## Остановка и возвращение старого проекта

```bash
docker compose --env-file .env.browser-relay \
  -f docker-compose.browser-relay.yml down
```

Это останавливает только удалённый браузер, не удаляя его профиль.
Для прежнего gateway отдельно:

```bash
docker compose --env-file .env.lan \
  -f docker-compose.open-gateway.yml up -d
```

Не запускайте оба одновременно на порту 50002.

## Если сайт не открывается

```bash
docker compose --env-file .env.browser-relay \
  -f docker-compose.browser-relay.yml ps

docker compose --env-file .env.browser-relay \
  -f docker-compose.browser-relay.yml logs --tail=80
```

Возможные причины: Docker Desktop не работает, старый контейнер ещё
занимает порт 50002, IP Mac изменился, не загрузился Chromium для arm64,
или ChatGPT потребовал подтверждение входа. При диагностике не
публикуйте сеансовые cookies ChatGPT.
