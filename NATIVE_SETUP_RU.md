# ChatGPT-Mirror: запуск без Docker

**Ограничение:** ChatGPT-gateway и cf5s поставлялись готовыми Docker-образами. Их исходников здесь нет. Сам по себе Django + Vue не создаёт работающий чат. Для нативного запуска необходим отдельно работающий и проверенный совместимый gateway (например, localhost:8787).

## Требования
Linux, Python 3.12+, Node.js 22+, npm, Caddy, cron и независимо проверенный gateway. Порты 8000 и 8787 не публикуйте в Интернет.

## Установка
1. Скопируйте пример окружения:
    cp .env.native.example .env.native
2. Сгенерируйте секрет:
    python3 -c "import secrets; print(secrets.token_urlsafe(48))"
3. В .env.native вставьте значение DJANGO_SECRET_KEY, установите разные надёжные секреты, список DJANGO_ALLOWED_HOSTS, реальный CHATGPT_GATEWAY_URL и GATEWAY_UPSTREAM.
4. Установите компоненты:
    chmod +x scripts/install_native.sh scripts/run_native.sh
    ./scripts/install_native.sh
5. Запустите:
    ./scripts/run_native.sh

Панель будет доступна на http://127.0.0.1:50002/admin/ . Маршрут / обслуживает не панель, а gateway.

## Периодические задачи
Для обновления ChatGPT-токенов исходный проект применяет django-crontab. При установке без Docker выполните в каталоге backend:
    ../.venv/bin/python manage.py crontab add
    ../.venv/bin/python manage.py crontab show

Проверьте наличие и работоспособность обычного системного crond и прав пользователя. Задачи должны запускаться раз в пять минут, их расписание уже содержится в backend/app/config/production.py.

## Важные замечания
- Caddyfile.native слушает HTTP и подходит для локального тестирования. Для публичного сервера добавьте TLS, firewall и ограничение доступов.
- Gunicorn слушает только loopback, наружу отдаёт Caddy.
- Никогда не используйте оригинальные стандартные учётные данные.
- Раздельный gateway не проверен. Нельзя обещать безопасность данных и токенов.
- Перевод касается только открытого интерфейса администрирования; чат отдаёт отдельный gateway.
- Зависимости перед публикацией нужно обновить и протестировать. Здесь не заявляется проверка всего приложения.

Upstream commit: 8c3a24093f8c7b4c72a4ab39fc94afe9f3aacbf7. Лицензия GPL-3.0.
