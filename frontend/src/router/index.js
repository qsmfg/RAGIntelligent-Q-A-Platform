import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录 - 小A智能问答系统' }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/Register.vue'),
    meta: { title: '注册 - 小A智能问答系统' }
  },
  {
    path: '/chat',
    name: 'Chat',
    component: () => import('@/views/Chat.vue'),
    meta: { title: '小A智能问答系统', requiresAuth: true }
  },
  {
    path: '/admin',
    name: 'Admin',
    component: () => import('@/views/Admin.vue'),
    meta: { title: '后台管理 - 小A智能问答系统', requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('@/views/Profile.vue'),
    meta: { title: '个人信息 - 小A智能问答系统', requiresAuth: true }
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/login'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫：未登录重定向到登录页
router.beforeEach((to, from, next) => {
  document.title = to.meta.title || '小A智能问答系统'
  if (to.meta.requiresAuth) {
    const token = localStorage.getItem('token')
    if (!token) {
      next('/login')
      return
    }
  }
  // 管理员页面校验
  if (to.meta.requiresAdmin) {
    const role = localStorage.getItem('role')
    if (role !== 'admin') {
      next('/chat')
      return
    }
  }
  // 已登录用户访问登录/注册页，重定向到聊天页
  if ((to.path === '/login' || to.path === '/register') && localStorage.getItem('token')) {
    next('/chat')
    return
  }
  next()
})

export default router