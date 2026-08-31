<script setup>
import { ref, onMounted, computed } from 'vue'
import client from '../api/client'
import { usePlayer } from '../composables/usePlayer'

const { playTrack, playFullTrack, playerState } = usePlayer()
const songs = ref([])
const loading = ref(true)
const error = ref('')
const filterMood = ref('')
const artistSearch = ref('')

const moods = [
  { key: '', label: 'All' },
  { key: 'happy', label: 'Happy' },
  { key: 'chill', label: 'Chill' },
  { key: 'sad', label: 'Sad' },
  { key: 'energetic', label: 'Energetic' },
  { key: 'romantic', label: 'Romantic' }
]

const filteredSongs = computed(() => {
  return songs.value.filter(s => {
    const mm = !filterMood.value || s.mood === filterMood.value
    const ma = !artistSearch.value.trim() || s.artist?.toLowerCase().includes(artistSearch.value.trim().toLowerCase()) || s.title?.toLowerCase().includes(artistSearch.value.trim().toLowerCase())
    return mm && ma
  })
})

async function fetchSongs() {
  loading.value = true
  try { songs.value = (await client.get('/songs')).data }
  catch { error.value = 'Failed to load library' }
  finally { loading.value = false }
}

async function deleteSong(id) {
  if (!confirm('Remove this song?')) return
  try { await client.delete(`/songs/${id}`); songs.value = songs.value.filter(s => s.id !== id) }
  catch { error.value = 'Failed to delete' }
}

function isCurrentPlaying(song, mode) {
  return playerState.currentTrack?.title === song.title && playerState.mode === mode && playerState.isPlaying
}

onMounted(fetchSongs)
</script>

<template>
  <div>
    <!-- Toolbar -->
    <div class="toolbar">
      <div class="search-wrap">
        <svg class="search-ico" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <input v-model="artistSearch" type="text" placeholder="Filter songs..." class="input-text toolbar-input" />
      </div>
      <div class="mood-pills">
        <button v-for="m in moods" :key="m.key" :class="['btn btn-sm btn-pill', filterMood === m.key ? 'btn-primary' : 'btn-secondary']" @click="filterMood = m.key">{{ m.label }}</button>
      </div>
    </div>

    <div v-if="loading" class="loading-block"><div class="spinner"></div><p class="text-secondary">Loading...</p></div>
    <div v-if="error" class="alert-error mb-3">{{ error }}</div>

    <div v-if="!loading && !filteredSongs.length && !error" class="empty">
      <div class="empty-ico">♫</div>
      <p class="empty-text">No songs match your filters.</p>
    </div>

    <div v-else class="grid-cards">
      <div v-for="(song, i) in filteredSongs" :key="song.id" class="song-card" :style="{ animationDelay: `${i * 0.03}s` }">
        <div class="flex-between">
          <div class="flex-row" style="min-width:0;flex:1;">
            <img v-if="song.album_art_url" :src="song.album_art_url" width="42" height="42" class="song-cover" />
            <div style="overflow:hidden;min-width:0;">
              <div class="s-title">{{ song.title }}</div>
              <div class="s-artist">{{ song.artist }}</div>
            </div>
          </div>
          <span :class="['badge', `badge-${song.mood || 'neutral'}`]">{{ song.mood }}</span>
        </div>
        <div class="metrics">
          <span>🥁 {{ Math.round(song.tempo) }} BPM</span>
          <span>·</span>
          <span>⚡ {{ Math.round(song.energy * 100) }}%</span>
          <span>·</span>
          <span>💃 {{ Math.round(song.danceability * 100) }}%</span>
        </div>
        <div class="flex-between" style="flex-wrap:wrap;gap:0.3rem;">
          <div class="flex-row" style="gap:0.3rem;">
            <button :class="['btn btn-sm', isCurrentPlaying(song, 'preview') ? 'btn-primary' : 'btn-secondary']" @click="playTrack(song, 'preview')">{{ isCurrentPlaying(song, 'preview') ? '⏸ 30s' : '🎧 30s' }}</button>
            <button :class="['btn btn-sm', isCurrentPlaying(song, 'full') ? 'btn-primary' : 'btn-secondary']" @click="playFullTrack(song)">{{ isCurrentPlaying(song, 'full') ? '⏸ Full' : '🎬 Full' }}</button>
          </div>
          <button class="btn btn-danger btn-sm del-btn" @click="deleteSong(song.id)" title="Remove">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.25rem;
  flex-wrap: wrap;
}

.search-wrap {
  position: relative;
  flex: 1;
  max-width: 320px;
}

.search-ico {
  position: absolute;
  left: 0.7rem;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  pointer-events: none;
}

.toolbar-input { padding-left: 2rem; }

.mood-pills { display: flex; flex-wrap: wrap; gap: 0.3rem; }

.loading-block {
  text-align: center;
  padding: 3rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
}

.spinner {
  width: 24px;
  height: 24px;
  border: 2.5px solid var(--border);
  border-top-color: var(--amber);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.empty { text-align: center; padding: 4rem 1rem; }
.empty-ico { font-size: 2.5rem; opacity: 0.3; margin-bottom: 0.75rem; }
.empty-text { color: var(--text-secondary); font-weight: 500; }

.s-title { font-weight: 600; font-size: 0.83rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.s-artist { font-size: 0.73rem; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.metrics { display: flex; gap: 0.35rem; font-size: 0.7rem; color: var(--text-muted); }

.del-btn { opacity: 0.4; transition: opacity 0.15s; }
.del-btn:hover { opacity: 1; }
</style>