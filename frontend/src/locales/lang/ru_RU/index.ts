import english from '../en_US';
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
