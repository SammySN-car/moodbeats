import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('./layouts/DefaultLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: '/home' },
      { path: 'home', name: 'Home', component: () => import('./features/home/views/HomeView.vue') },
      { path: 'discover', name: 'Discover', component: () => import('./features/discover/views/DiscoverView.vue') },
      { path: 'library', name: 'Library', component: () => import('./features/library/views/LibraryView.vue') },
      { path: 'import', name: 'Import', component: () => import('./features/import/views/ImportView.vue') },
      { path: 'analytics', name: 'Analytics', component: () => import('./features/analytics/views/AnalyticsView.vue') },
    ]
  },
  {
    path: '/',
    component: () => import('./layouts/AuthLayout.vue'),
    children: [
      { path: 'login', name: 'Login', component: () => import('./features/auth/views/Login.vue') },
      { path: 'signup', name: 'Signup', component: () => import('./features/auth/views/Signup.vue') },
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    return { name: 'Login' }
  }
  if ((to.name === 'Login' || to.name === 'Signup') && token) {
    return { name: 'Discover' }
  }
})

export default router
