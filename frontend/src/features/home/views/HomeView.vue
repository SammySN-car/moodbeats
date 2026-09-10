<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import client from '../../../api/client'
import { usePlayer } from '../../../shared/composables/usePlayer'

const router = useRouter()
const { playTrack, playFullTrack, playerState, setQueue } = usePlayer()

const recentlyPlayed = ref([])
const topMoods = ref([])
const recommendations = ref([])
const loading = ref(true)

const userName = computed(() => localStorage.getItem('userName') || 'Listener')

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning'
  if (h < 17) return 'Good afternoon'
  return 'Good evening'
})

const timeEmoji = computed(() => {
  const h = new Date().getHours()
  if (h < 12) return '☀️'
  if (h < 17) return '🌤️'
  return '🌙'
})

const moodCards = [
  { mood: 'euphoric', label: 'Euphoric', emoji: '🔥', gradient: 'linear-gradient(135deg, #f5576c 0%, #ff6a88 100%)', desc: 'High energy, positive vibes' },
  { mood: 'chill', label: 'Chill', emoji: '🌊', gradient: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)', desc: 'Relax, study, lo-fi beats' },
  { mood: 'sad', label: 'Sad', emoji: '🌧️', gradient: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', desc: 'Melancholic, emotional' },
  { mood: 'energetic', label: 'Energetic', emoji: '⚡', gradient: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)', desc: 'Workout, party, hype' },
]

const gradients = [
  'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
  'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
  'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
  'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
]

function getArtGradient(title) {
  if (!title) return gradients[0]
  let hash = 0
  for (let i = 0; i < title.length; i++) {
    hash = title.charCodeAt(i) + ((hash << 5) - hash)
  }
  return gradients[Math.abs(hash) % gradients.length]
}

// Album art cache
const albumArtCache = ref({})

async function fetchAlbumArt(song) {
  const key = `${song.title}-${song.artist}`
  if (albumArtCache.value[key] !== undefined) return
  albumArtCache.value[key] = null
  try {
    const res = await client.get('/songs/album-art', {
      params: { title: song.title, artist: song.artist || '' }
    })
    albumArtCache.value[key] = res.data?.album_art_url || null
  } catch {
    albumArtCache.value[key] = null
  }
}

function getAlbumArt(song) {
  const key = `${song.title}-${song.artist}`
  return albumArtCache.value[key]
}

async function loadHome() {
  loading.value = true
  try {
    // Load recently played
    const recentRes = await client.get('/listening/history', { params: { limit: 8 } })
    recentlyPlayed.value = recentRes.data.map(h => h.song || h).slice(0, 8)
    recentlyPlayed.value.forEach(s => fetchAlbumArt(s))

    // Load top moods from library
    const moodsRes = await client.get('/songs', { params: { limit: 4 } })
    topMoods.value = moodsRes.data

    // Load recommendations
    const recRes = await client.post('/playlists/generate', { prompt: 'upbeat happy vibes' })
    if (recRes.data?.items) {
      recommendations.value = recRes.data.items.slice(0, 4).map(i => i.song)
      recommendations.value.forEach(s => fetchAlbumArt(s))
    }
  } catch (e) {
    console.warn('Home load error:', e)
  } finally {
    loading.value = false
  }
}

function playMood(mood) {
  router.push({ path: '/discover', query: { mood } })
}

function isCurrentPlaying(song) {
  return playerState.currentTrack?.id === song.id && playerState.isPlaying
}

onMounted(loadHome)
</script>

<template>
  <section class="home">
    <!-- Hero Greeting -->
    <header class="hero">
      <div class="hero-text">
        <p class="eyebrow">{{ timeEmoji }} MOODBEATS</p>
        <h1>{{ greeting }}, {{ userName }}</h1>
        <p class="subcopy">What vibe are you feeling today?</p>
      </div>
      <div class="hero-visual" v-if="playerState.currentTrack">
        <div class="now-playing-mini" @click="router.push('/discover')">
          <div class="mini-art" :style="{ background: getArtGradient(playerState.currentTrack.title) }">
            <img v-if="getAlbumArt(playerState.currentTrack)" :src="getAlbumArt(playerState.currentTrack)" alt="">
            <span v-else>{{ playerState.currentTrack.title?.charAt(0) || '♪' }}</span>
          </div>
          <div class="mini-info">
            <strong>{{ playerState.currentTrack.title }}</strong>
            <span>{{ playerState.currentTrack.artist }}</span>
          </div>
          <div class="mini-eq">
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>
    </header>

    <!-- Mood Discovery Cards -->
    <section class="mood-section">
      <h2>Discover by Mood</h2>
      <div class="mood-grid">
        <button
          v-for="card in moodCards"
          :key="card.mood"
          class="mood-card"
          :style="{ background: card.gradient }"
          @click="playMood(card.mood)"
        >
          <span class="mood-emoji">{{ card.emoji }}</span>
          <div>
            <strong>{{ card.label }}</strong>
            <p>{{ card.desc }}</p>
          </div>
        </button>
      </div>
    </section>

    <!-- Recently Played -->
    <section v-if="recentlyPlayed.length" class="section">
      <div class="section-header">
        <h2>Recently Played</h2>
        <button class="ghost" @click="router.push('/library')">See all</button>
      </div>
      <div class="scroll-row">
        <article
          v-for="(song, idx) in recentlyPlayed"
          :key="song.id"
          class="recent-card"
          @click="setQueue(recentlyPlayed, idx); playTrack(song, 'preview')"
        >
          <div class="cover" :class="{ playing: isCurrentPlaying(song) }">
            <img v-if="getAlbumArt(song)" :src="getAlbumArt(song)" :alt="song.title" loading="lazy">
            <div v-else class="cover-fallback" :style="{ background: getArtGradient(song.title) }">
              {{ song.title?.charAt(0) || '♪' }}
            </div>
            <span class="play-overlay">▶</span>
          </div>
          <strong>{{ song.title }}</strong>
          <span>{{ song.artist }}</span>
        </article>
      </div>
    </section>

    <!-- Quick Play Suggestions -->
    <section class="section">
      <div class="section-header">
        <h2>Quick Play</h2>
      </div>
      <div class="quick-grid">
        <button
          v-for="(card, i) in moodCards"
          :key="'qp-' + i"
          class="quick-btn"
          :style="{ background: card.gradient }"
          @click="playMood(card.mood)"
        >
          <span>{{ card.emoji }}</span>
          <span>{{ card.label }}</span>
        </button>
      </div>
    </section>

    <!-- Loading skeleton -->
    <div v-if="loading" class="skeleton-grid">
      <div v-for="n in 4" :key="n" class="skeleton-card">
        <div class="skeleton art"></div>
        <div class="skeleton line"></div>
        <div class="skeleton short"></div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.home { max-width: 1240px; margin: auto; }

.hero { display: flex; align-items: center; justify-content: space-between; margin-bottom: 36px; gap: 24px; }
.hero-text { flex: 1; }
.eyebrow { margin: 0 0 8px; color: #f5b942; font-size: 11px; font-weight: 800; letter-spacing: .14em; }
.hero h1 { margin: 0; font-size: clamp(28px, 5vw, 44px); letter-spacing: -.055em; }
.subcopy { margin: 10px 0 0; color: #8e97a6; font-size: 14px; }

.now-playing-mini { display: flex; align-items: center; gap: 12px; padding: 12px 16px; border-radius: 12px; background: rgba(255,255,255,.06); cursor: pointer; transition: .2s; }
.now-playing-mini:hover { background: rgba(255,255,255,.1); }
.mini-art { width: 48px; height: 48px; border-radius: 8px; display: grid; place-items: center; overflow: hidden; color: #fff; font-weight: 800; font-size: 18px; flex: none; }
.mini-art img { width: 100%; height: 100%; object-fit: cover; }
.mini-info { display: flex; flex-direction: column; gap: 2px; }
.mini-info strong { color: #f4f5f7; font-size: 13px; }
.mini-info span { color: #8e97a6; font-size: 11px; }
.mini-eq { display: flex; align-items: end; gap: 2px; height: 20px; }
.mini-eq span { width: 3px; background: #f5b942; border-radius: 2px; animation: eq 0.8s ease-in-out infinite alternate; }
.mini-eq span:nth-child(1) { height: 60%; animation-delay: 0s; }
.mini-eq span:nth-child(2) { height: 100%; animation-delay: 0.2s; }
.mini-eq span:nth-child(3) { height: 40%; animation-delay: 0.4s; }
@keyframes eq { from { height: 20%; } to { height: 100%; } }

.mood-section { margin-bottom: 40px; }
.mood-section h2, .section h2 { margin: 0 0 16px; font-size: 20px; letter-spacing: -.03em; }
.mood-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.mood-card { display: flex; align-items: center; gap: 14px; padding: 18px; border: 0; border-radius: 14px; color: #fff; text-align: left; cursor: pointer; transition: transform .2s, box-shadow .2s; }
.mood-card:hover { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(0,0,0,.3); }
.mood-emoji { font-size: 32px; }
.mood-card strong { display: block; font-size: 16px; margin: 0; }
.mood-card p { margin: 4px 0 0; font-size: 12px; opacity: .85; }

.section { margin-bottom: 40px; }
.section-header { display: flex; justify-content: space-between; align-items: end; margin-bottom: 16px; }
.ghost { border: 1px solid rgba(255,255,255,.08); padding: 6px 14px; border-radius: 8px; background: transparent; color: #8e97a6; font-size: 12px; cursor: pointer; transition: .2s; }
.ghost:hover { border-color: #f5b942; color: #f5b942; }

.scroll-row { display: flex; gap: 14px; overflow-x: auto; padding-bottom: 8px; }
.scroll-row::-webkit-scrollbar { height: 4px; }
.scroll-row::-webkit-scrollbar-thumb { background: rgba(255,255,255,.1); border-radius: 4px; }
.recent-card { flex: 0 0 160px; cursor: pointer; transition: .2s; }
.recent-card:hover { transform: translateY(-2px); }
.recent-card .cover { position: relative; aspect-ratio: 1; border-radius: 10px; overflow: hidden; margin-bottom: 8px; }
.recent-card .cover img, .recent-card .cover-fallback { width: 100%; height: 100%; object-fit: cover; }
.recent-card .cover-fallback { display: grid; place-items: center; color: #fff; font-size: 36px; font-weight: 800; }
.recent-card .cover.playing { outline: 2px solid #f5b942; }
.play-overlay { position: absolute; inset: 0; display: grid; place-items: center; background: rgba(0,0,0,.4); color: #fff; font-size: 24px; opacity: 0; transition: .2s; }
.recent-card:hover .play-overlay { opacity: 1; }
.recent-card strong { display: block; overflow: hidden; font-size: 12px; color: #f4f5f7; text-overflow: ellipsis; white-space: nowrap; }
.recent-card span { font-size: 11px; color: #8e97a6; }

.quick-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.quick-btn { display: flex; align-items: center; gap: 10px; padding: 14px 16px; border: 0; border-radius: 10px; color: #fff; font-size: 13px; font-weight: 600; cursor: pointer; transition: .2s; }
.quick-btn:hover { transform: scale(1.02); }
.quick-btn span:first-child { font-size: 20px; }

.skeleton-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.skeleton-card { padding: 10px; }
.skeleton { background: linear-gradient(90deg, rgba(255,255,255,.05), rgba(255,255,255,.12), rgba(255,255,255,.05)); background-size: 200% 100%; animation: shimmer 1.3s infinite; border-radius: 8px; }
.skeleton.art { aspect-ratio: 1; border-radius: 10px; }
.skeleton.line { width: 80%; height: 12px; margin: 10px 0 6px; }
.skeleton.short { width: 50%; height: 10px; }
@keyframes shimmer { to { background-position: -200% 0; } }

@media (max-width: 800px) {
  .mood-grid, .quick-grid, .skeleton-grid { grid-template-columns: repeat(2, 1fr); }
  .hero { flex-direction: column; align-items: start; }
}
@media (max-width: 480px) {
  .mood-grid, .quick-grid { grid-template-columns: 1fr 1fr; }
}
</style>
