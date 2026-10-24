import Cookies from 'js-cookie';
import { defineStore } from 'pinia';
import { MessagePlugin } from 'tdesign-vue-next';

import { usePermissionStore } from '@/store';
import { i18n } from '@/locales';
import type { UserInfo } from '@/types/interface';

const InitUserInfo: UserInfo = {
  name: '', // 用户名，用于展示在页面右上角头像处
  roles: [], // 前端权限模型使用 如果使用请配置modules/permission-fe.ts使用
};

export const useUserStore = defineStore('user', {
  state: () => ({
    token: '', // Require a real Django login token; never treat placeholder as authenticated
    is_admin: false,
    userInfo: { ...InitUserInfo },
  }),
  getters: {
    roles: (state) => {
      return state.userInfo?.roles;
    },
  },
  actions: {
    async login(url: string, userInfo: Record<string, unknown>) {
      const ru = i18n.global.locale.value === 'ru_RU';
      try {
        const response = await fetch(url, {
          method: 'POST',
          body: JSON.stringify(userInfo),
          headers: { 'Content-Type': 'application/json' },
        });
        if (!response.ok) {
          // The original Django API sometimes replies in Chinese. Show a
          // localized, actionable error instead of untrusted raw server text.
          const message = response.status === 400 || response.status === 401
            ? (ru ? 'Неверный логин или пароль либо учётная запись недоступна.' : 'Wrong username or password, or account unavailable.')
            : (ru ? `Ошибка входа (HTTP ${response.status}). Проверьте сервер.` : `Sign-in failed (HTTP ${response.status}). Check the server.`);
          MessagePlugin.error(message);
          return null;
        }
        const data = await response.json();
        if (!data || typeof data.admin_token !== 'string') {
          MessagePlugin.error(ru ? 'Сервер вернул неверный ответ.' : 'Invalid response from server.');
          return null;
        }
        this.token = data.admin_token;
        this.is_admin = !!data.is_admin;
        Cookies.set('user_token', data.admin_token, { expires: 7 });
        MessagePlugin.success(ru ? 'Вход выполнен' : 'Signed in');
        return data;
      } catch (_error) {
        MessagePlugin.error(ru ? 'Нет связи с сервером. Проверьте Docker и адрес сайта.' : 'Cannot connect to server. Check Docker and site address.');
        return null;
      }
    },

    async logout() {
      this.token = '';
      this.userInfo = { ...InitUserInfo };
    },
  },
  persist: {
    afterRestore: () => {
      const permissionStore = usePermissionStore();
      permissionStore.initRoutes();
    },
    key: 'user',
    paths: ['token'],
  },
});
