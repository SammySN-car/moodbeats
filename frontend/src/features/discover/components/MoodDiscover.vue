<script setup>
import { ref } from 'vue'
import client from '../../../api/client'
import { usePlayer } from '../../../shared/composables/usePlayer'

const { playTrack, playFullTrack, playerState } = usePlayer()
const vibePrompt = ref('')
const isGenerating = ref(false)
const playlist = ref(null)
const error = ref('')
const addingTrack = ref({})

async function handleGenerate() {
  if (!vibePrompt.value.trim()) return
  isGenerating.value = true
  error.value = ''
  playlist.value = null
  try {
    const res = await client.post('/playlists/generate', { prompt: vibePrompt.value })
    playlist.value = res.data
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed'
  } finally {
    isGenerating.value = false
  }
}

async function addToLibrary(rec) {
  addingTrack.value[rec.title] = true
  try {
    await client.post('/songs/import-itunes', { title: rec.title, artist: rec.artist })
    addingTrack.value[rec.title] = 'done'
  } catch (err) {
    console.warn('Import failed:', err.message)
    addingTrack.value[rec.title] = false
  }
}

function isCurrentPlaying(track, mode) {
  return playerState.currentTrack?.title === track.title && playerState.mode === mode && playerState.isPlaying
}
</script>

<template>
  <div>
    <!-- Hero Search -->
    <div class="hero glass animate-in">
      <div class="hero-glow"></div>
      <div class="hero-body">
        <div class="hero-row">
          <div class="hero-icon">✦</div>
          <h2 class="hero-title">What do you want to feel?</h2>
        </div>
        <div class="search-row">
          <input v-model="vibePrompt" @keyup.enter="handleGenerate" type="text" placeholder="Describe any vibe, mood, or setting..." class="input-text search-input" />
          <button class="btn btn-primary" :disabled="isGenerating || !vibePrompt.trim()" @click="handleGenerate" style="flex-shrink:0;">
            <span v-if="isGenerating">Curating...</span>
            <span v-else>Discover</span>
          </button>
        </div>
        <div class="pills">
          <span class="pills-label">Try:</span>
          <button v-for="v in ['Drift phonk', 'Midnight rain', 'Coffee jazz', 'Workout energy', 'Synthwave drive']" :key="v" class="btn btn-secondary btn-sm btn-pill" @click="vibePrompt = v; handleGenerate()">{{ v }}</button>
        </div>
        <div v-if="error" class="alert-error mt-3">{{ error }}</div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="isGenerating" class="loading-block animate-in">
      <div class="spinner"></div>
      <p class="text-secondary">Curating your playlist...</p>
    </div>

    <!-- Results -->
    <div v-if="playlist && !isGenerating" class="animate-in">
      <div class="playlist-hero card">
        <div class="playlist-icon">♫</div>
        <div>
          <h3 class="playlist-name">{{ playlist.name }}</h3>
          <p class="playlist-desc">"{{ playlist.description }}"</p>
          <p class="taste-indicator" v-if="playlist.items?.length">🎯 Taste profile applied — results personalized to your listening history</p>
        </div>
      </div>

      <!-- Library Section -->
      <div v-if="playlist.items?.length" class="section">
        <div class="section-head">
          <h4 class="section-title">From Your Library</h4>
          <span class="section-count">{{ playlist.items.length }} tracks</span>
        </div>
        <div class="grid-cards">
          <div v-for="(item, i) in playlist.items" :key="item.id" class="song-card" :style="{ animationDelay: `${i * 0.04}s` }">
            <div class="flex-between">
              <div class="flex-row" style="min-width:0;flex:1;">
                <img v-if="item.song.album_art_url" :src="item.song.album_art_url" width="40" height="40" class="song-cover" />
                <div style="overflow:hidden;min-width:0;">
                  <div class="s-title">{{ item.song.title }}</div>
                  <div class="s-artist">{{ item.song.artist }}</div>
                </div>
              </div>
              <span :class="['badge', `badge-${item.song.mood || 'neutral'}`]">{{ item.song.mood }}</span>
            </div>
            <div class="flex-row" style="gap:0.3rem;">
              <button :class="['btn btn-sm', isCurrentPlaying(item.song, 'preview') ? 'btn-primary' : 'btn-secondary']" @click="playTrack(item.song, 'preview')">{{ isCurrentPlaying(item.song, 'preview') ? '⏸ 30s' : '🎧 30s' }}</button>
              <button :class="['btn btn-sm', isCurrentPlaying(item.song, 'full') ? 'btn-primary' : 'btn-secondary']" @click="playFullTrack(item.song)">{{ isCurrentPlaying(item.song, 'full') ? '⏸ Full' : '🎬 Full' }}</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Recommendations Section -->
      <div v-if="playlist.new_recommendations?.length" class="section">
        <div class="section-head">
          <h4 class="section-title">Recommended</h4>
          <span class="section-count">{{ playlist.new_recommendations.length }} tracks</span>
        </div>
        <div class="grid-cards">
          <div v-for="(rec, i) in playlist.new_recommendations" :key="rec.title" class="song-card" :style="{ animationDelay: `${i * 0.04}s` }">
            <div class="flex-between">
              <div class="flex-row" style="min-width:0;flex:1;">
                <img v-if="rec.album_art_url" :src="rec.album_art_url" width="40" height="40" class="song-cover" />
                <div style="overflow:hidden;min-width:0;">
                  <div class="s-title">{{ rec.title }}</div>
                  <div class="s-artist">{{ rec.artist }}</div>
                </div>
              </div>
            </div>
            <div class="flex-between" style="flex-wrap:wrap;gap:0.3rem;">
              <div class="flex-row" style="gap:0.3rem;">
                <button :class="['btn btn-sm', isCurrentPlaying(rec, 'preview') ? 'btn-primary' : 'btn-secondary']" @click="playTrack(rec, 'preview')">{{ isCurrentPlaying(rec, 'preview') ? '⏸ 30s' : '🎧 30s' }}</button>
                <button :class="['btn btn-sm', isCurrentPlaying(rec, 'full') ? 'btn-primary' : 'btn-secondary']" @click="playFullTrack(rec)">{{ isCurrentPlaying(rec, 'full') ? '⏸ Full' : '🎬 Full' }}</button>
              </div>
              <button :class="['btn btn-sm', addingTrack[rec.title] === 'done' ? 'btn-secondary' : 'btn-primary']" :disabled="addingTrack[rec.title] === true || addingTrack[rec.title] === 'done'" @click="addToLibrary(rec)">{{ addingTrack[rec.title] === 'done' ? '✓ Saved' : addingTrack[rec.title] ? '...' : '+ Save' }}</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.hero {
  position: relative;
  padding: 2rem;
  margin-bottom: 1.5rem;
  overflow: hidden;
}

.hero-glow {
  position: absolute;
  top: -60%;
  left: -20%;
  width: 140%;
  height: 120%;
  background: radial-gradient(ellipse, rgba(245, 158, 11, 0.05) 0%, transparent 60%);
  pointer-events: none;
}

.hero-body { position: relative; z-index: 1; }

.hero-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 1rem;
}

.hero-icon {
  font-size: 1.2rem;
  color: var(--amber);
}

.hero-title {
  font-size: 1.15rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.search-row {
  display: flex;
  gap: 0.6rem;
}

.search-input { flex: 1; padding: 0.7rem 1rem; font-size: 0.88rem; }

.pills {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-top: 0.85rem;
}

.pills-label {
  font-size: 0.7rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 600;
}

.loading-block {
  text-align: center;
  padding: 3rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
}

.spinner {
  width: 28px;
  height: 28px;
  border: 2.5px solid var(--border);
  border-top-color: var(--amber);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.playlist-hero {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  margin-bottom: 1.5rem;
}

.playlist-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--r-md);
  background: var(--amber-gradient);
  color: #0a0a0f;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.2rem;
  flex-shrink: 0;
}

.playlist-name { font-size: 1.1rem; font-weight: 800; letter-spacing: -0.02em; }
.playlist-desc { font-size: 0.8rem; color: var(--text-muted); font-style: italic; margin-top: 0.1rem; }
.taste-indicator { font-size: 0.7rem; color: var(--amber); margin-top: 0.3rem; opacity: 0.8; }

.section { margin-bottom: 1.5rem; }

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.8rem;
}

.section-title { font-size: 0.9rem; font-weight: 700; }
.section-count { font-size: 0.72rem; color: var(--text-muted); font-weight: 500; }

.s-title { font-weight: 600; font-size: 0.83rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.s-artist { font-size: 0.73rem; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
