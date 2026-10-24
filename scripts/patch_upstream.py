#!/usr/bin/env python3
"""Apply reproducible security and RU/EN admin-panel changes to upstream source.

Run from the root of a checked-out ChatGPT-Mirror repository.
This is intentionally strict: fail if an expected upstream fragment changes.
The proprietary gateway/chat UI is NOT included or audited.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def edit(path: str, old: str, new: str) -> None:
    p = ROOT / path
    data = p.read_text(encoding="utf-8")
    if old not in data:
        if new in data:
            return
        raise RuntimeError("Upstream changed; cannot patch safely: " + path + " / " + old[:60])
    p.write_text(data.replace(old, new), encoding="utf-8")


def append_file(path: str, data: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(data, encoding="utf-8")


def security() -> None:
    settings = "backend/app/settings.py"
    edit(settings,
         'SECRET_KEY = "django-insecure-gw^4gif(3_2ijvc)l)ty0s-1e#2chgt@li=!+cnk#x&01nc*a)"',
         '''# Production deployments MUST supply a unique secret in the environment.
from django.core.management.utils import get_random_secret_key
_SECRET_FROM_ENV = os.environ.get("DJANGO_SECRET_KEY")
if not _SECRET_FROM_ENV and os.environ.get("DJANGO_ENV", "PRODUCTION") == "PRODUCTION":
    raise RuntimeError("DJANGO_SECRET_KEY must be set for production")
SECRET_KEY = _SECRET_FROM_ENV or get_random_secret_key()''')
    edit(settings, 'ALLOWED_HOSTS = ["*"]',
         '''ALLOWED_HOSTS = [host.strip() for host in
                 os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
                 if host.strip()]
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in
                        os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
                        if origin.strip()]''')
    edit(settings, '"rest_framework.authentication.TokenAuthentication",',
         '"app.accounts.authentication.ActiveUnexpiredTokenAuthentication",')
    edit(settings, 'LANGUAGE_CODE = "zh-hans"', 'LANGUAGE_CODE = "en-us"')
    edit(settings, 'TIME_ZONE = "Asia/Shanghai"', 'TIME_ZONE = os.environ.get("TZ", "UTC")')
    edit(settings, 'DJANGO_ENV = os.environ.get("DJANGO_ENV")',
         'DJANGO_ENV = os.environ.get("DJANGO_ENV", "PRODUCTION")')
    edit("backend/app/config/local.py", 'ADMIN_USERNAME = "dairoot"',
         'ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")')
    edit("backend/app/config/local.py", 'ADMIN_PASSWORD = "dairoot"',
         'ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")')
    edit("backend/app/config/production.py", 'os.environ.get("ALLOW_REGISTER", "true")',
         'os.environ.get("ALLOW_REGISTER", "false")')
    edit("backend/app/accounts/views/__init__.py",
         'from rest_framework.exceptions import ValidationError',
         'from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound')
    edit("backend/app/accounts/views/__init__.py",
         '''        user = User.objects.filter(id=request.GET["user_id"]).first()

        user_gpt_list''',
         '''        user_id = request.query_params.get("user_id")
        if not user_id or not user_id.isdecimal():
            raise ValidationError({"user_id": "Valid user_id is required"})
        user = User.objects.filter(id=int(user_id)).first()
        if user is None:
            raise NotFound("User not found")
        if not request.user.is_staff and user.pk != request.user.pk:
            raise PermissionDenied("Access to another user's tokens is forbidden")

        user_gpt_list''')
    edit("backend/app/chatgpt/models.py",
         '''        gptaccount = ChatgptAccount.objects
        if gptcar_list:
            gptaccount = gptaccount.filter(id__in=chatgpt_account_list)

        return gptaccount.order_by("-plan_type", "-id").all()''',
         '''        # No assigned pools means no access, NEVER all accounts.
        return cls.objects.filter(id__in=set(chatgpt_account_list)).order_by(
            "-plan_type", "-id"
        )''')
    edit("backend/app/utils/__init__.py",
         '''    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]  # 如果存在多个IP，用逗号分隔，取第一个
    else:
        ip = request.META.get('REMOTE_ADDR')  # 直接获取远程地址
    return ip''',
         '''    # X-Forwarded-For supplied by an untrusted client is spoofable.
    return request.META.get("REMOTE_ADDR") or "127.0.0.1"''')
    edit("backend/app/utils/__init__.py",
         'requests.request(method, url, headers=headers, *args, **kwargs, allow_redirects=False)',
         'requests.request(method, url, headers=headers, *args, timeout=25, **kwargs, allow_redirects=False)')
    edit("backend/app/cron.py",
         'requests.post(url, headers=headers, json={"chatgpt_token": chatgpt_token})',
         'requests.post(url, headers=headers, json={"chatgpt_token": chatgpt_token}, timeout=25)')
    edit("frontend/src/pages/login/index.vue",
         'v-html="cfg.notice"', 'v-text="cfg.notice"')
    append_file("backend/app/accounts/authentication.py",
        '''from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


class ActiveUnexpiredTokenAuthentication(TokenAuthentication):
    """Block still-valid DRF tokens for disabled or expired accounts."""

    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        if not user.is_active:
            raise AuthenticationFailed("Account disabled")
        if user.expired_date and user.expired_date <= timezone.localdate():
            raise AuthenticationFailed("Account expired")
        return user, token
''')


# Translation of user-visible strings in the editable admin frontend.
# Original Chinese strings are keys, values are (English, Russian).
WORDS = {
    "录入": ("Add token", "Добавить токен"),
    "新增": ("Add", "Добавить"),
    "新建": ("Create", "Создать"),
    "已过期": ("Expired", "Истёк"),
    "运行中": ("Active", "Работает"),
    "更新": ("Update", "Обновить"),
    "编辑": ("Edit", "Изменить"),
    "删除": ("Delete", "Удалить"),
    "确认删除": ("Confirm deletion", "Подтвердить удаление"),
    "确认删除该用户吗": ("Delete this user?", "Удалить этого пользователя?"),
    "确认删除该 号池 吗": ("Delete this account pool?", "Удалить этот пул аккаунтов?"),
    "确认删除该 ChatGPT token 吗": ("Delete this ChatGPT token?", "Удалить этот токен ChatGPT?"),
    "账号": ("Account", "Аккаунт"),
    "账号详情": ("Account details", "Данные аккаунта"),
    "状态": ("Status", "Статус"),
    "类型": ("Type", "Тип"),
    "近期用量": ("Recent usage", "Недавнее использование"),
    "过期时间": ("Expiration", "Срок действия"),
    "过期日期": ("Expiration date", "Дата окончания"),
    "创建时间": ("Created", "Создан"),
    "最近更新时间": ("Last updated", "Обновлён"),
    "注册时间": ("Registered", "Зарегистрирован"),
    "最近登录时间": ("Last login", "Последний вход"),
    "备注": ("Notes", "Примечания"),
    "备注信息": ("Notes", "Примечания"),
    "编辑 备注信息": ("Edit notes", "Изменить примечания"),
    "编辑信息": ("Edit details", "Изменить данные"),
    "操作": ("Actions", "Действия"),
    "新增成功": ("Added successfully", "Успешно добавлено"),
    "删除成功": ("Deleted successfully", "Успешно удалено"),
    "修改成功": ("Updated successfully", "Успешно изменено"),
    "更新成功": ("Updated successfully", "Успешно обновлено"),
    "不能为空": ("Cannot be empty", "Не может быть пустым"),
    "号池名称": ("Pool name", "Название пула"),
    "账号管理": ("Account management", "Управление аккаунтами"),
    "号池": ("Account pool", "Пул аккаунтов"),
    "选择": ("Select", "Выбрать"),
    "请选择 ChatGPT 账号": ("Select a ChatGPT account", "Выберите аккаунт ChatGPT"),
    "账号列表": ("Accounts", "Аккаунты"),
    "添加/编辑 用户": ("Add/edit user", "Добавить/изменить пользователя"),
    "新增 用户": ("Add user", "Добавить пользователя"),
    "用户": ("User", "Пользователь"),
    "用户名": ("Username", "Имя пользователя"),
    "密码": ("Password", "Пароль"),
    "模型限制": ("Model limits", "Ограничения моделей"),
    "批量限制模型": ("Set model limits", "Ограничить модели"),
    "限制成功": ("Limits updated", "Ограничения обновлены"),
    "独立会话": ("Separate session", "Отдельная сессия"),
    "所有账号": ("All accounts", "Все аккаунты"),
    "指定号池": ("Specific pool", "Указанный пул"),
    "是": ("Yes", "Да"),
    "否": ("No", "Нет"),
    "启用": ("Enable", "Включить"),
    "停用": ("Disable", "Отключить"),
    "访问": ("Visit", "Перейти"),
    "限制": ("Limit", "Ограничение"),
    "已绑定": ("Linked", "Привязано"),
    "个": ("items", "шт."),
    "每": ("Every", "Каждые"),
    "分钟": ("minutes", "минут"),
    "发送": ("Send", "Отправить"),
    "条": ("messages", "сообщений"),
    "消息": ("Message", "Сообщение"),
    "模型不能为空": ("Model is required", "Укажите модель"),
    "每分钟限制必须大于": ("Per-minute limit must exceed", "Лимит в минуту должен быть больше"),
    "发送条数必须大于": ("Message count must exceed", "Число сообщений должно быть больше"),
    "至少 4 个字符": ("At least 4 characters", "Минимум 4 символа"),
    "创建帐户": ("Create account", "Создать аккаунт"),
    "欢迎回来": ("Welcome back", "С возвращением"),
    "获取说明": ("How to obtain", "Как получить"),
    "手动获取": ("Get manually", "Получить вручную"),
    "自动获取": ("Get automatically", "Получить автоматически"),
    "注册": ("Register", "Регистрация"),
    "登录": ("Log in", "Войти"),
    "已经拥有帐户": ("Already have an account?", "Уже есть аккаунт?"),
    "免费体验": ("Free trial", "Попробовать бесплатно"),
    "没有帐户": ("No account?", "Нет аккаунта?"),
    "请输入用户名": ("Enter username", "Введите имя пользователя"),
    "请输入密码": ("Enter password", "Введите пароль"),
    "实时状态": ("Live status", "Текущий статус"),
    "空闲": ("Idle", "Свободен"),
    "忙碌": ("Busy", "Занят"),
    "繁忙": ("High load", "Высокая нагрузка"),
    "可用": ("Available", "Доступен"),
    "登录成功": ("Login successful", "Вход выполнен"),
    "国家/地区": ("Country/region", "Страна/регион"),
    "操作类型": ("Action type", "Тип действия"),
    "操作时间": ("Action time", "Время действия"),
    "操作设备": ("Device", "Устройство"),
    "复制": ("Copy", "Копировать"),
    "复制成功": ("Copied", "Скопировано"),
    "复制失败": ("Copy failed", "Ошибка копирования"),
    "免登链接": ("Direct sign-in link", "Ссылка для входа"),
    "用于 API, 该token不会变更": ("For API; this token stays the same", "Для API; этот токен не меняется"),
    "邀请码数量": ("Invitation count", "Число приглашений"),
    "邀请数量": ("Invitations", "Приглашения"),
    "已用数量": ("Used", "Использовано"),
    "邀请链接": ("Invitation link", "Ссылка-приглашение"),
    "创建": ("Create", "Создать"),
    "已复制": ("Copied", "Скопировано"),
    "确认删除该邀请链接吗？": ("Delete this invitation link?", "Удалить эту ссылку-приглашение?"),
    "有效期10天": ("Valid 10 days", "Действует 10 дней"),
    "有效期30天": ("Valid 30 days", "Действует 30 дней"),
    "有效期永久": ("Never expires", "Без срока действия"),
    "5 分钟": ("5 minutes", "5 минут"),
    "10 分钟": ("10 minutes", "10 минут"),
    "30 分钟": ("30 minutes", "30 минут"),
    "1 小时": ("1 hour", "1 час"),
    "6 小时": ("6 hours", "6 часов"),
    "1 天": ("1 day", "1 день"),
    "3 天": ("3 days", "3 дня"),
    "过期时间": ("Expiration time", "Время окончания"),
    "请输入 Access Token 或 Session Token 或 Refresh Token。一行一串": (
        "Enter access/session/refresh tokens, one per line", "Введите токены access/session/refresh, по одному на строку"),
    "请输入 Access Token 或 Session Token 或 Refresh Token。一行一串。": (
        "Enter access/session/refresh tokens, one per line", "Введите токены access/session/refresh, по одному на строку"),
    "多个Token请换行输入": ("Use a new line for each token", "Каждый токен вводите с новой строки"),
    "系统异常": ("System error", "Ошибка системы"),
    "服务未正常启动": ("Service did not start", "Сервис не запущен"),
}

def key_for(chinese: str) -> str:
    # ASCII key based on Unicode codepoints; deterministic, safe identifier.
    return "k" + "_".join(format(ord(char), "x") for char in chinese)


def translate_vue(source: str) -> str:
    # Only admin pages: preserve operational data and code comments.
    script_index = source.find("<script")
    if script_index < 0:
        script_index = len(source)
    template, code = source[:script_index], source[script_index:]

    def attr_repl(m):
        value = m.group("value")
        if value not in WORDS:
            return m.group(0)
        return ' :' + m.group("attr") + '="$t(\'mirror.' + key_for(value) + '\')"'

    template = re.sub(
        r'\s(?P<attr>label|placeholder|header|content|title|text)="(?P<value>[^"<>]+)"',
        attr_repl, template)

    def text_repl(m):
        original = m.group(1)
        trimmed = original.strip()
        if trimmed not in WORDS:
            return m.group(0)
        space_left = original[:len(original)-len(original.lstrip())]
        space_right = original[len(original.rstrip()):]
        return ">" + space_left + "{{ $t('mirror." + key_for(trimmed) + "') }}" + space_right + "<"

    template = re.sub(r'>([^<>]+)<', text_repl, template)

    changed_code = False
    def js_repl(m):
        nonlocal changed_code
        value = m.group("value")
        if value not in WORDS:
            return m.group(0)
        # Quotes only in script; do not alter Chinese in comments.
        line = code[:m.start()].split("\n")[-1]
        if "//" in line or "<!--" in line:
            return m.group(0)
        changed_code = True
        return "t('mirror." + key_for(value) + "')"

    code = re.sub(r'(?P<quote>["\x27])(?P<value>[^"\x27\n]+)(?P=quote)', js_repl, code)
    if changed_code and "from '@/locales'" not in code:
        code = code.replace("<script setup lang=\"ts\">",
                            "<script setup lang=\"ts\">\nimport { t } from '@/locales';", 1)
    return template + code


def localization() -> None:
    edit("frontend/src/locales/index.ts",
         "useLocalStorage(localeConfigKey, 'zh_CN').value || languages.value[0] || 'zh_CN'",
         """(() => {
    const preferred = languages.value[0]?.startsWith('ru') ? 'ru_RU' : 'en_US';
    const stored = useLocalStorage(localeConfigKey, preferred).value;
    return stored === 'en_US' || stored === 'ru_RU' ? stored : preferred;
  })()""")
    edit("frontend/src/locales/index.ts",
         "fallbackLocale: 'zh_CN'", "fallbackLocale: 'en_US'")
    edit("frontend/src/locales/useLocale.ts", "lang = 'zh_CN';", "lang = 'en_US';")
    edit("frontend/src/locales/useLocale.ts",
         "useLocalStorage(localeConfigKey, 'zh_CN').value = lang;",
         "useLocalStorage(localeConfigKey, 'en_US').value = lang;")
    edit("frontend/src/layouts/components/Header.vue",
         '''<!-- <t-dropdown trigger="click">
            <t-button theme="default" shape="square" variant="text">
              <translate-icon />
            </t-button>
            <t-dropdown-menu>
              <t-dropdown-item
                v-for="(lang, index) in langList"
                :key="index"
                :value="lang.value"
                @click="(options) => changeLang(options.value as string)"
                >{{ lang.content }}</t-dropdown-item
              ></t-dropdown-menu
            >
          </t-dropdown> -->''',
         '''<t-dropdown trigger="click">
            <t-button theme="default" variant="text">
              <translate-icon /> {{ locale === 'ru_RU' ? 'Русский' : 'English' }}
            </t-button>
            <t-dropdown-menu>
              <t-dropdown-item v-for="lang in langList" :key="String(lang.value)" @click="changeLang(String(lang.value))">
                {{ lang.content }}
              </t-dropdown-item>
            </t-dropdown-menu>
          </t-dropdown>''')
    edit("frontend/src/layouts/components/Header.vue",
         "// import { langList } from '@/locales/index';\n// import { useLocale } from '@/locales/useLocale';",
         "import { langList } from '@/locales/index';\nimport { useLocale } from '@/locales/useLocale';")
    edit("frontend/src/layouts/components/Header.vue",
         '''// const { changeLocale } = useLocale();
// const changeLang = (lang: string) => {
//   changeLocale(lang);
// };''',
         '''const { changeLocale, locale } = useLocale();
const changeLang = (lang: string) => {
  changeLocale(lang);
  // Static table column labels are evaluated at component creation.
  window.location.reload();
};''')
    # Language choice is also available before login.
    edit("frontend/src/pages/login/index.vue",
         '<div style="display: flex; flex-direction: column">',
         """<div style="display: flex; flex-direction: column">
    <div style="align-self: flex-end; width: 145px; margin: 8px 20px">
      <t-select :value="locale" :options="languageChoices" @change="changeLanguage" />
    </div>""")
    edit("frontend/src/pages/login/index.vue",
         "import { useUserStore } from '@/store';",
         """import { useUserStore } from '@/store';
import { useLocale } from '@/locales/useLocale';""")
    edit("frontend/src/pages/login/index.vue",
         "const userStore = useUserStore();",
         """const userStore = useUserStore();
const { locale, changeLocale } = useLocale();
const languageChoices = [
  { label: 'English', value: 'en_US' },
  { label: 'Русский', value: 'ru_RU' },
];
const changeLanguage = (value: any) => {
  changeLocale(String(value));
  window.location.reload();
};""")
    # Only advertise the supported languages, not the original Chinese UI.
    edit("frontend/src/locales/index.ts",
         '    langCode.push(code);\n    langModuleMap.set(code, langModules[fullPath]);',
         '''    if (code !== 'en_US' && code !== 'ru_RU') return;
    langCode.push(code);
    langModuleMap.set(code, langModules[fullPath]);''')
    for path in sorted((ROOT / "frontend/src/pages").rglob("*.vue")):
        raw = path.read_text(encoding="utf-8")
        path.write_text(translate_vue(raw), encoding="utf-8")
    # Include requests and settings UI strings where mapping exists.
    for name in ("frontend/src/api/request.ts", "frontend/src/layouts/setting.vue"):
        p = ROOT / name
        raw = p.read_text(encoding="utf-8")
        p.write_text(translate_vue(raw) if name.endswith(".vue") else raw.replace(
            "MessagePlugin.error('系统异常')", "MessagePlugin.error('System error')"
        ).replace("MessagePlugin.error('服务未正常启动')",
                  "MessagePlugin.error('Service unavailable')"), encoding="utf-8")

    values_en = ",\n".join(
        "  " + key_for(zh) + ": " + repr(en)
        for zh, (en, _) in WORDS.items())
    values_ru = ",\n".join(
        "  " + key_for(zh) + ": " + repr(ru)
        for zh, (_, ru) in WORDS.items())
    append_file("frontend/src/locales/lang/en_US/mirror.ts",
                "export default {\n" + values_en + "\n};\n")
    append_file("frontend/src/locales/lang/ru_RU/mirror.ts",
                "export default {\n" + values_ru + "\n};\n")
    edit("frontend/src/locales/lang/en_US/index.ts",
         "import pages from './pages';", "import pages from './pages';\nimport mirror from './mirror';")
    edit("frontend/src/locales/lang/en_US/index.ts",
         "  lang: 'English',", "  lang: 'English',\n  mirror,")
    append_file("frontend/src/locales/lang/ru_RU/index.ts", '''import english from '../en_US';
import mirror from './mirror';

export default {
  ...english,
  lang: 'Русский',
  mirror,
  layout: {
    ...english.layout,
    header: {
      ...english.layout.header,
      signOut: 'Выйти',
      code: 'Исходный код',
      help: 'Справка',
      setting: 'Настройки',
    },
  },
  pages: {
    ...english.pages,
    login: {
      ...english.pages.login,
      loginTitle: 'Вход',
      noAccount: 'Нет аккаунта?',
      createAccount: 'Создать аккаунт',
      remember: 'Запомнить',
      signIn: 'Войти',
      existAccount: 'Есть аккаунт?',
      refresh: 'Обновить',
      input: {
        account: 'Введите имя пользователя',
        password: 'Введите пароль',
        phone: 'Введите телефон',
        verification: 'Введите код',
      },
    },
  },
};
''')
    edit("frontend/src/router/modules/homepage.ts",
         "zh_CN: '账号管理',", "zh_CN: '账号管理',\n        ru_RU: 'Управление аккаунтами',")
    edit("frontend/src/router/modules/homepage.ts",
         "zh_CN: '用户',", "zh_CN: '用户',\n            ru_RU: 'Пользователи',")
    edit("frontend/src/router/modules/homepage.ts",
         "zh_CN: 'ChatGPT',", "zh_CN: 'ChatGPT',\n            ru_RU: 'ChatGPT',")
    edit("frontend/src/router/modules/homepage.ts",
         "zh_CN: '号池',", "zh_CN: '号池',\n            ru_RU: 'Пулы аккаунтов',")
    edit("frontend/src/router/modules/homepage.ts",
         "zh_CN: '系统管理',", "zh_CN: '系统管理',\n        ru_RU: 'Система',")
    edit("frontend/src/router/modules/homepage.ts",
         "zh_CN: '登录日志',", "zh_CN: '登录日志',\n            ru_RU: 'Журнал входов',")


if __name__ == "__main__":
    security()
    localization()
    print("Security & locale patches applied. A full gateway audit is still required.")
