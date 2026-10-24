# ChatGPT-Mirror, RU/EN fork

> ⚠️ **Security warning:** the original project is discontinued. The separate chatgpt-gateway and cf5s binaries are NOT included or audited. Do not use this fork with important accounts or expose it to the public Internet without an independent gateway audit and dependency upgrades.

Based on [dairoot/ChatGPT-Mirror](https://github.com/dairoot/ChatGPT-Mirror) at commit `8c3a24093f8c7b4c72a4ab39fc94afe9f3aacbf7`. Licensed under GPL-3.0.

## Русский

Изменения в этой ветке:

- Переключение **Русский / English** в открытой Vue-панели администрирования, включая вход. Большая часть обычных надписей переведена на оба языка.
- Исправлены опасные настройки Django, IDOR при выдаче mirror token, ошибочный полный доступ к аккаунтам при пустом пуле, проверка просроченных токенов пользователя и ряд других дефектов.
- **Запуск Python + Vue + Caddy без Docker** возможен при наличии отдельного совместимого gateway. В исходном репозитории нет исходников gateway, поэтому без него основной чат не запустится.

**Собственный открытый gateway (экспериментальный):** [установка на macOS / LAN, с Docker и без](OPEN_GATEWAY_RU.md). Он использует ChatGPT web accessToken, не OpenAI API-ключ и не закрытые образы. **Совместимость с ChatGPT не подтверждена**: современный приватный протокол может требовать Sentinel и WebSocket-handoff.

**Инструкции:** [Полный accessToken-стек для изолированной LAN (macOS)](LAN_SETUP_RU.md) · [macOS: с Docker и без Docker](MACOS_SETUP_RU.md) · [Linux: без Docker](NATIVE_SETUP_RU.md) · [Аудит безопасности](SECURITY_REVIEW_RU.md)

**macOS и Docker:** запускайте `docker compose -f docker-compose.mac.yml up -d --build web` (после настройки `.env.docker`). В отличие от исходного `docker-compose.yml`, этот файл **собирает ваш изменённый исходный код**, открывает только localhost и не запускает старый закрытый gateway без явного параметра `--profile legacy-gateway`.

**Установка (только после прочтения ограничений):**

```bash
cp .env.native.example .env.native
# Установите уникальные пароли и секреты в .env.native.
chmod +x scripts/install_native.sh scripts/run_native.sh
./scripts/install_native.sh
./scripts/run_native.sh
```

Панель: http://127.0.0.1:50002/admin/

Перевод **самого чата** ограничен: эту часть отдает внешний gateway, не входящий в открытый код. Не путайте RU/EN административную панель с полноценной локализацией закрытого компонента.

## English

This is a security-improved, bilingual **administration-panel** fork of a discontinued project. It adds RU/EN UI controls, authorization/configuration hardening, security regression checks, and a native deployment option for the open Vue+Django+Caddy components.

**A separately supplied, trusted compatible gateway is still required for chat.** The original gateway/cf5s images are not open-source here and are not audited or supplied by this repository. Token data is still stored in unencrypted SQLite, dependencies need security upgrades, and the original chat UI cannot be localized here.

The [experimental open accessToken gateway (Russian)](OPEN_GATEWAY_RU.md) does not require an OpenAI API key, but cannot guarantee compatibility with ChatGPT web auth or its modern streaming protocol. Read the [macOS Docker/native guide (Russian)](MACOS_SETUP_RU.md), [Linux native guide (Russian)](NATIVE_SETUP_RU.md) and [security assessment (Russian)](SECURITY_REVIEW_RU.md) before deploying. Production use is **not recommended** without resolving the remaining risks.
