<script setup>
import { useRouter, useRoute } from 'vue-router'
import { computed } from 'vue'
import BottomPlayer from '../features/player/components/BottomPlayer.vue'

const router = useRouter()
const route = useRoute()
const userName = localStorage.getItem('userName')

const navItems = [
  { path: '/discover', label: 'Discover', icon: 'discover' },
  { path: '/library', label: 'Library', icon: 'library' },
  { path: '/import', label: 'Import', icon: 'import' },
  { path: '/analytics', label: 'Analytics', icon: 'analytics' },
]

const isActive = (path) => route.path === path

function logout() {
  localStorage.removeItem('token')
  localStorage.removeItem('userName')
  router.push('/login')
}
</script>

<template>
  <div class="app-layout">
    <!-- Desktop Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-brand">
        <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
          <defs>
            <linearGradient id="aurora" x1="0" y1="0" x2="32" y2="32">
              <stop offset="0%" stop-color="#f59e0b"/>
              <stop offset="100%" stop-color="#f97316"/>
            </linearGradient>
          </defs>
          <rect width="32" height="32" rx="10" fill="url(#aurora)"/>
          <path d="M10 22V12L22 8V18" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" opacity="0.9"/>
          <circle cx="10" cy="22" r="3" fill="#fff" opacity="0.9"/>
          <circle cx="22" cy="18" r="3" fill="#fff" opacity="0.9"/>
        </svg>
        <span class="sidebar-brand-text">MoodBeats</span>
      </div>

      <nav class="sidebar-nav">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          :class="['sidebar-link', { active: isActive(item.path) }]"
        >
          <svg v-if="item.icon === 'discover'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/></svg>
          <svg v-else-if="item.icon === 'library'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>
          <svg v-else-if="item.icon === 'import'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
          <svg v-else-if="item.icon === 'analytics'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
          <span class="sidebar-link-label">{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <div class="sidebar-user">
          <div class="sidebar-avatar">{{ userName?.charAt(0)?.toUpperCase() || '?' }}</div>
          <span class="sidebar-username">{{ userName }}</span>
        </div>
        <button class="sidebar-logout" @click="logout" title="Sign out">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
        </button>
      </div>
    </aside>

    <!-- Main Content -->
    <div class="main-area">
      <!-- Mobile Header -->
      <header class="mobile-header">
        <div class="mobile-brand">
          <svg width="24" height="24" viewBox="0 0 32 32" fill="none">
            <rect width="32" height="32" rx="10" fill="url(#aurora)"/>
            <path d="M10 22V12L22 8V18" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" opacity="0.9"/>
            <circle cx="10" cy="22" r="3" fill="#fff" opacity="0.9"/>
            <circle cx="22" cy="18" r="3" fill="#fff" opacity="0.9"/>
          </svg>
          <span class="mobile-brand-name">MoodBeats</span>
        </div>
        <button class="mobile-logout" @click="logout">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
        </button>
      </header>

      <main class="main-content">
        <router-view v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>

    <!-- Mobile Bottom Nav -->
    <nav class="bottom-nav">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        :class="['bottom-nav-item', { active: isActive(item.path) }]"
      >
        <svg v-if="item.icon === 'discover'" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/></svg>
        <svg v-else-if="item.icon === 'library'" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>
        <svg v-else-if="item.icon === 'import'" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
        <svg v-else-if="item.icon === 'analytics'" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
        <span>{{ item.label }}</span>
      </router-link>
    </nav>

    <!-- Bottom Player -->
    <BottomPlayer />
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
}

/* Desktop Sidebar */
.sidebar {
  width: 240px;
  background: rgba(8, 8, 15, 0.95);
  border-right: 1px solid rgba(255,255,255,0.06);
  display: flex;
  flex-direction: column;
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  z-index: 50;
  padding: 1.25rem 0.75rem;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0 0.75rem;
  margin-bottom: 2rem;
}

.sidebar-brand-text {
  font-size: 1.05rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  background: linear-gradient(135deg, #f59e0b, #f97316);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.sidebar-link {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.6rem 0.75rem;
  border-radius: 8px;
  color: #5c554b;
  text-decoration: none;
  font-size: 0.84rem;
  font-weight: 500;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.sidebar-link:hover {
  color: #9a8f82;
  background: rgba(255,255,255,0.04);
}

.sidebar-link.active {
  color: #faf5ef;
  background: rgba(245,158,11,0.1);
}

.sidebar-link.active svg {
  stroke: #f59e0b;
}

.sidebar-footer {
  margin-top: auto;
  padding: 0.75rem;
  border-top: 1px solid rgba(255,255,255,0.06);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sidebar-user {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.sidebar-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, #f59e0b, #f97316);
  color: #0a0a0f;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  font-weight: 800;
}

.sidebar-username {
  font-size: 0.78rem;
  color: #9a8f82;
  font-weight: 500;
}

.sidebar-logout {
  background: none;
  border: none;
  color: #5c554b;
  cursor: pointer;
  padding: 0.35rem;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.sidebar-logout:hover {
  color: #f87171;
  background: rgba(248,113,113,0.1);
}

/* Main Area */
.main-area {
  flex: 1;
  margin-left: 240px;
  padding-bottom: 5rem;
}

.main-content {
  padding: 1.5rem 2rem;
  max-width: 1200px;
}

/* Mobile Header */
.mobile-header {
  display: none;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  background: rgba(8, 8, 15, 0.9);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(255,255,255,0.06);
  position: sticky;
  top: 0;
  z-index: 40;
}

.mobile-brand {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.mobile-brand-name {
  font-size: 0.95rem;
  font-weight: 800;
  background: linear-gradient(135deg, #f59e0b, #f97316);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.mobile-logout {
  background: none;
  border: none;
  color: #5c554b;
  cursor: pointer;
  padding: 0.3rem;
}

/* Mobile Bottom Nav */
.bottom-nav {
  display: none;
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(8, 8, 15, 0.95);
  backdrop-filter: blur(20px);
  border-top: 1px solid rgba(255,255,255,0.06);
  z-index: 900;
  padding: 0.4rem 0;
  padding-bottom: env(safe-area-inset-bottom, 0.4rem);
}

.bottom-nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.15rem;
  padding: 0.3rem 0;
  color: #5c554b;
  text-decoration: none;
  font-size: 0.6rem;
  font-weight: 500;
  transition: color 0.15s;
}

.bottom-nav-item.active {
  color: #f59e0b;
}

.bottom-nav-item.active svg {
  stroke: #f59e0b;
}

/* Page Transitions */
.page-enter-active, .page-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}
.page-enter-from { opacity: 0; transform: translateY(6px); }
.page-leave-to { opacity: 0; transform: translateY(-6px); }

/* Responsive */
@media (max-width: 768px) {
  .sidebar { display: none; }
  .main-area { margin-left: 0; }
  .mobile-header { display: flex; }
  .bottom-nav {
    display: flex;
    justify-content: space-around;
  }
  .main-content { padding: 1rem; padding-bottom: 6rem; }
}

@media (min-width: 769px) {
  .bottom-nav { display: none !important; }
}
</style>
