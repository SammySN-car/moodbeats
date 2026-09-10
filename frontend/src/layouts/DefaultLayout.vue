<script setup>
import { useRouter, useRoute } from 'vue-router'
import { computed, ref, watch, onUnmounted, nextTick } from 'vue'
import { usePlayer } from '../shared/composables/usePlayer'
import BottomPlayer from '../features/player/components/BottomPlayer.vue'

const router = useRouter()
const route = useRoute()
const { playerState, togglePlay, toggleMode, skipTrack, seek, toggleMute, closePlayer, nextInQueue, sendListeningEvent } = usePlayer()

const userName = computed(() => localStorage.getItem('userName') || 'Listener')
const userInitials = computed(() => {
  return userName.value.split(' ').map(p => p[0]).slice(0, 2).join('').toUpperCase()
})

const sidebarCollapsed = ref(false)
const mobileOpen = ref(false)

const navigation = [
  {
    label: 'Listen',
    items: [
      {
        label: 'Home',
        route: '/home',
        icon: '<svg viewBox="0 0 24 24"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>'
      },
      {
        label: 'Discover',
        route: '/discover',
        icon: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/></svg>'
      },
      {
        label: 'Your Library',
        route: '/library',
        icon: '<svg viewBox="0 0 24 24"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>'
      }
    ]
  },
  {
    label: 'Insights',
    items: [
      {
        label: 'Import Music',
        route: '/import',
        icon: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>'
      },
      {
        label: 'Mood Analytics',
        route: '/analytics',
        icon: '<svg viewBox="0 0 24 24"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>'
      }
    ]
  }
]

const isActive = (path) => route.path === path

// YouTube IFrame API
const ytPlayer = ref(null)
let ytPlayerInstance = null

function loadYtApi() {
  if (window.YT && window.YT.Player) return Promise.resolve()
  return new Promise((resolve) => {
    window.onYouTubeIframeAPIReady = resolve
    const tag = document.createElement('script')
    tag.src = 'https://www.youtube.com/iframe_api'
    document.head.appendChild(tag)
  })
}

function initYtPlayer(videoId) {
  if (!videoId || !ytPlayer.value) return
  if (ytPlayerInstance) {
    try { ytPlayerInstance.destroy() } catch {}
  }
  ytPlayerInstance = new window.YT.Player(ytPlayer.value, {
    videoId,
    playerVars: { autoplay: 1, controls: 0, modestbranding: 1, rel: 0 },
    events: {
      onStateChange(e) {
        if (e.data === 0) {
          if (playerState.currentTrack?.id) {
            sendListeningEvent(playerState.currentTrack.id, 'play', 0)
          }
          playerState.isPlaying = false
          playerState.currentTime = 0
          playerState.progress = 0
          if (playerState.queue.length > 0) {
            nextInQueue()
          }
        }
      }
    }
  })
}

watch(() => playerState.youtubeVideoId, async (newId) => {
  if (newId) {
    await loadYtApi()
    await nextTick()
    initYtPlayer(newId)
  }
})

onUnmounted(() => {
  if (ytPlayerInstance) {
    try { ytPlayerInstance.destroy() } catch {}
  }
})

const pageTitle = computed(() => {
  return navigation
    .flatMap(g => g.items)
    .find(i => isActive(i.route))?.label || 'Discover'
})

function logout() {
  localStorage.removeItem('token')
  localStorage.removeItem('userName')
  router.push('/login')
}

function navigate(path) {
  router.push(path)
  mobileOpen.value = false
}

const handleSeek = (val) => {
  const fakeEvent = { currentTarget: { getBoundingClientRect: () => ({ left: 0, width: 1 }) }, clientX: val / 100 }
  seek(fakeEvent)
}
</script>

<template>
  <div class="app-shell" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <aside class="sidebar" aria-label="Primary navigation">
      <div class="brand-row">
        <router-link class="brand" to="/home" aria-label="MoodBeats home">
          <span class="brand-mark" aria-hidden="true">
            <span></span><span></span><span></span>
          </span>
          <span>Mood<span class="brand-accent">Beats</span></span>
        </router-link>

        <button
          class="icon-button collapse-button"
          type="button"
          :aria-label="sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'"
          @click="sidebarCollapsed = !sidebarCollapsed"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="m15 6-6 6 6 6" />
          </svg>
        </button>
      </div>

      <nav class="nav-groups">
        <div v-for="group in navigation" :key="group.label" class="nav-group">
          <p class="nav-label">{{ group.label }}</p>

          <router-link
            v-for="item in group.items"
            :key="item.route"
            class="nav-item"
            :class="{ active: isActive(item.route) }"
            :to="item.route"
            :aria-current="isActive(item.route) ? 'page' : undefined"
            @click="mobileOpen = false"
          >
            <span class="nav-icon" v-html="item.icon" aria-hidden="true"></span>
            <span class="nav-text">{{ item.label }}</span>
          </router-link>
        </div>
      </nav>

      <div class="sidebar-footer">
        <div class="profile-card">
          <div class="avatar">{{ userInitials }}</div>

          <div class="profile-copy">
            <strong>{{ userName }}</strong>
            <span>Free listener</span>
          </div>

          <button
            class="icon-button"
            type="button"
            aria-label="Sign out"
            @click="logout"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
            </svg>
          </button>
        </div>
      </div>
    </aside>

    <div v-if="mobileOpen" class="mobile-scrim" @click="mobileOpen = false"></div>

    <div class="main-column">
      <header class="topbar">
        <button
          class="mobile-menu icon-button"
          type="button"
          aria-label="Open navigation"
          @click="mobileOpen = !mobileOpen"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 7h16M4 12h16M4 17h16" />
          </svg>
        </button>

        <div class="breadcrumb">
          <span>MoodBeats</span>
          <span class="slash">/</span>
          <strong>{{ pageTitle }}</strong>
        </div>
      </header>

      <main class="content">
        <router-view v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>

    <BottomPlayer
      v-if="playerState.currentTrack"
      :track="playerState.currentTrack"
      :is-playing="playerState.isPlaying"
      :progress="playerState.progress"
      :duration="playerState.duration"
      :current-time="playerState.currentTime"
      :volume="playerState.volume"
      :muted="playerState.isMuted"
      :mode="playerState.mode"
      @toggle-play="togglePlay"
      @next="skipTrack"
      @previous="skipTrack"
      @seek="(val) => {}"
      @toggle-mute="toggleMute"
      @close="closePlayer"
      @toggle-mode="toggleMode"
    />

    <!-- Hidden YouTube player for full song mode -->
    <div v-if="playerState.youtubeVideoId" class="yt-container">
      <div ref="ytPlayer" class="yt-iframe"></div>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  --bg: #0b0d10;
  --panel: rgba(21, 25, 31, 0.78);
  --line: rgba(255, 255, 255, 0.08);
  --muted: #8e97a6;
  --text: #f4f5f7;
  --accent: #f5b942;
  --accent-soft: rgba(245, 185, 66, 0.13);

  min-height: 100vh;
  display: flex;
  background:
    radial-gradient(circle at 70% -15%, rgba(245, 185, 66, 0.07), transparent 33%),
    var(--bg);
}

.sidebar {
  width: 252px;
  flex: 0 0 252px;
  padding: 25px 15px 18px;
  border-right: 1px solid var(--line);
  background: rgba(13, 16, 20, 0.76);
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
}

.sidebar-collapsed .sidebar {
  width: 82px;
  flex-basis: 82px;
}

.brand-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 10px 34px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text);
  font-size: 18px;
  font-weight: 750;
  letter-spacing: -0.04em;
  text-decoration: none;
}

.brand-accent {
  color: var(--accent);
}

.brand-mark {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 22px;
}

.brand-mark span {
  width: 4px;
  border-radius: 4px;
  background: var(--accent);
}

.brand-mark span:nth-child(1) { height: 11px; }
.brand-mark span:nth-child(2) { height: 19px; }
.brand-mark span:nth-child(3) { height: 14px; }

.icon-button {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border: 1px solid transparent;
  border-radius: 11px;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  transition: 0.2s ease;
}

.icon-button:hover {
  color: var(--text);
  background: rgba(255, 255, 255, 0.06);
  border-color: var(--line);
}

.icon-button svg {
  width: 19px;
  height: 19px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.collapse-button {
  width: 30px;
  height: 30px;
}

.sidebar-collapsed .collapse-button svg {
  transform: rotate(180deg);
}

.sidebar-collapsed .brand > span:last-child,
.sidebar-collapsed .nav-label,
.sidebar-collapsed .nav-text,
.sidebar-collapsed .profile-copy,
.sidebar-collapsed .profile-card > .icon-button {
  display: none;
}

.nav-groups {
  display: flex;
  flex-direction: column;
  gap: 30px;
}

.nav-label {
  margin: 0 10px 9px;
  color: #687180;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 13px;
  min-height: 45px;
  padding: 0 11px;
  border-radius: 12px;
  color: var(--muted);
  font-size: 13px;
  text-decoration: none;
  transition: 0.2s ease;
}

.nav-item:hover {
  color: var(--text);
  background: rgba(255, 255, 255, 0.045);
}

.nav-item.active {
  color: var(--accent);
  background: var(--accent-soft);
}

.nav-icon {
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
}

.nav-icon :deep(svg) {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.sidebar-footer {
  margin-top: auto;
}

.profile-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 8px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.035);
}

.avatar {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  flex: none;
  border-radius: 50%;
  color: #17191d;
  background: var(--accent);
  font-size: 11px;
  font-weight: 800;
}

.profile-copy {
  min-width: 0;
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 3px;
}

.profile-copy strong {
  overflow: hidden;
  color: var(--text);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.profile-copy span {
  color: var(--muted);
  font-size: 10px;
}

.main-column {
  min-width: 0;
  flex: 1;
  padding-bottom: 100px;
}

.topbar {
  height: 76px;
  display: flex;
  align-items: center;
  padding: 0 32px;
  border-bottom: 1px solid var(--line);
  background: rgba(11, 13, 16, 0.4);
  backdrop-filter: blur(18px);
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 11px;
  color: #687180;
  font-size: 12px;
}

.breadcrumb strong {
  color: var(--text);
  font-weight: 600;
}

.slash {
  color: #3e4651;
}

.mobile-menu {
  display: none;
}

.content {
  min-height: calc(100vh - 76px);
  padding: 36px clamp(22px, 4vw, 58px) 30px;
}

.mobile-scrim {
  display: none;
}

.page-enter-active, .page-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}
.page-enter-from { opacity: 0; transform: translateY(6px); }
.page-leave-to { opacity: 0; transform: translateY(-6px); }

@media (max-width: 760px) {
  .sidebar {
    position: fixed;
    z-index: 50;
    top: 0;
    bottom: 0;
    left: 0;
    width: 252px;
    transform: translateX(-100%);
    box-shadow: 18px 0 50px rgba(0, 0, 0, 0.35);
  }

  .sidebar-collapsed .sidebar {
    width: 252px;
    transform: translateX(-100%);
  }

  .app-shell:has(.mobile-scrim) .sidebar {
    transform: translateX(0);
  }

  .mobile-scrim {
    position: fixed;
    z-index: 45;
    inset: 0;
    display: block;
    background: rgba(0, 0, 0, 0.58);
  }

  .mobile-menu {
    display: grid;
  }

  .topbar {
    height: 66px;
    padding: 0 17px;
  }

  .breadcrumb {
    margin-right: auto;
    margin-left: 10px;
  }

  .content {
    min-height: calc(100vh - 66px);
    padding: 25px 17px 150px;
  }
}
.yt-container {
  position: fixed;
  bottom: 90px;
  right: 20px;
  width: 320px;
  height: 180px;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 8px 32px rgba(0,0,0,0.6);
  z-index: 50;
  border: 1px solid rgba(255,255,255,0.1);
}
.yt-iframe {
  width: 100%;
  height: 100%;
  border: 0;
}
</style>
