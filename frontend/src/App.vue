<script setup>
import { useRouter } from 'vue-router'
import BottomPlayer from './components/BottomPlayer.vue'

const router = useRouter()
const userName = localStorage.getItem('userName')

function logout() {
  localStorage.removeItem('token')
  localStorage.removeItem('userName')
  router.push('/login')
}
</script>

<template>
  <div id="app">
    <!-- Aurora Header -->
    <header v-if="$route.meta.requiresAuth" class="aurora-header">
      <div class="container flex-between">
        <div class="brand">
          <div class="brand-mark">
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
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
          </div>
          <div>
            <h1 class="brand-name">MoodBeats</h1>
            <p class="brand-tag">AI Music Discovery</p>
          </div>
        </div>

        <div class="flex-row" style="gap: 0.75rem;">
          <div class="user-pill">
            <div class="user-avatar">{{ userName?.charAt(0)?.toUpperCase() || '?' }}</div>
            <span class="user-label">{{ userName }}</span>
          </div>
          <button class="btn btn-secondary btn-sm" @click="logout">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
            Sign out
          </button>
        </div>
      </div>
    </header>

    <main class="container" style="padding-bottom: 7rem;">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <BottomPlayer />
  </div>
</template>

<style scoped>
.aurora-header {
  position: sticky;
  top: 0;
  z-index: 100;
  padding: 0.85rem 0;
  background: rgba(8, 8, 15, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border);
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.brand-mark {
  flex-shrink: 0;
}

.brand-name {
  font-size: 1.1rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  background: var(--amber-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  line-height: 1.2;
}

.brand-tag {
  font-size: 0.62rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
}

.user-pill {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.25rem 0.75rem 0.25rem 0.25rem;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border);
  border-radius: var(--r-full);
}

.user-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--amber-gradient);
  color: #0a0a0f;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.68rem;
  font-weight: 800;
}

.user-label {
  font-size: 0.78rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.page-enter-active, .page-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}
.page-enter-from { opacity: 0; transform: translateY(6px); }
.page-leave-to { opacity: 0; transform: translateY(-6px); }
</style>