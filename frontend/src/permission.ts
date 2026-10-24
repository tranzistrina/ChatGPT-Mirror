import 'nprogress/nprogress.css';

import NProgress from 'nprogress';
import { MessagePlugin } from 'tdesign-vue-next';

import router from '@/router';
import { getPermissionStore, useUserStore } from '@/store';

NProgress.configure({ showSpinner: false });

// All routes in this fork are registered statically in router/index.ts.
// The upstream guard repeatedly tried to install an empty asyncRoutes list,
// which could send a successful login into an infinite router redirect.
router.beforeEach(async (to) => {
  NProgress.start();

  const permissionStore = getPermissionStore();
  const userStore = useUserStore();
  const publicRoutes = permissionStore.whiteListRouters;

  // Sign-in must remain reachable, regardless of persisted account state.
  if (to.path === '/login') return true;

  if (!userStore.token) {
    if (publicRoutes.includes(to.path)) return true;
    return {
      path: '/login',
      query: { redirect: encodeURIComponent(to.fullPath) },
    };
  }

  try {
    // Generate the menu once when needed, but never redirect back to the same
    // route just because no dynamic routes are available.
    if (permissionStore.routers.length === 0) {
      await permissionStore.initRoutes();
    }
    return true;
  } catch (_error) {
    MessagePlugin.error('Failed to initialize local navigation.');
    return { path: '/login' };
  }
});

router.afterEach((to) => {
  if (to.path === '/login') {
    const userStore = useUserStore();
    const permissionStore = getPermissionStore();
    userStore.logout();
    permissionStore.restoreRoutes();
  }
  NProgress.done();
});
