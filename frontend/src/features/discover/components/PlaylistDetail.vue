<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import client from '../../../api/client'
import { usePlayer } from '../../../shared/composables/usePlayer'
import { useAlbumArt } from '../../../shared/composables/useAlbumArt'

const route = useRoute()
const router = useRouter()
const { playTrack, setQueue, playerState } = usePlayer()
const { getAlbumArt } = useAlbumArt()

const playlist = ref(null)
const loading = ref(true)
const error = ref('')
const deleting = ref(false)

function formatDuration(sec) {
  if (!sec) return ''
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function formatRelativeTime(dateStr) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  return new Date(dateStr).toLocaleDateString()
}

const totalDuration = computed(() => {
  if (!playlist.value?.items) return 0
  return playlist.value.items.reduce((sum, item) => sum + (item.song?.duration_sec || 0), 0)
})

function formatTotalDuration(sec) {
  if (!sec) return '0:00'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

function isCurrentTrack(song) {
  return playerState.currentTrack?.id === song?.id
}

function playSong(song, index) {
  if (!song) return
  const tracks = playlist.value.items.map(i => i.song).filter(Boolean)
  setQueue(tracks, index)
  playTrack(song, playerState.mode || 'preview')
}

function playAll() {
  const tracks = playlist.value.items.map(i => i.song).filter(Boolean)
  if (tracks.length) {
    setQueue(tracks, 0)
    playTrack(tracks[0], playerState.mode || 'preview')
  }
}

async function deletePlaylist() {
  if (!confirm(`Delete "${playlist.value.name}"? This cannot be undone.`)) return
  deleting.value = true
  try {
    await client.delete(`/playlists/${playlist.value.id}`)
    router.push('/playlists')
  } catch {
    error.value = 'Failed to delete playlist'
    deleting.value = false
  }
}

async function fetchPlaylist() {
  loading.value = true
  try {
    const res = await client.get(`/playlists/${route.params.id}`)
    playlist.value = res.data
  } catch {
    error.value = 'Failed to load playlist'
  } finally {
    loading.value = false
  }
}

onMounted(fetchPlaylist)
</script>

<template>
  <section class="page">
    <div v-if="loading" class="loading-state">
      <div class="skeleton-header"></div>
      <div v-for="n in 8" :key="n" class="skeleton-row"></div>
    </div>

    <div v-else-if="error" class="error-banner">{{ error }}</div>

    <div v-else-if="playlist">
      <header class="pl-header">
        <button class="back-btn" @click="router.push('/playlists')">&larr; Playlists</button>
        <div class="pl-main">
          <div class="pl-info">
            <h1>{{ playlist.name }}</h1>
            <p v-if="playlist.description" class="desc">{{ playlist.description }}</p>
            <div class="meta">
              <span>{{ playlist.items?.length || 0 }} tracks</span>
              <span class="dot">&middot;</span>
              <span>{{ formatTotalDuration(totalDuration) }}</span>
              <span class="dot">&middot;</span>
              <span>{{ formatRelativeTime(playlist.created_at) }}</span>
            </div>
          </div>
          <div class="pl-actions">
            <button class="play-all-btn" @click="playAll" :disabled="!playlist.items?.length">
              &#9654; Play All
            </button>
            <button class="delete-btn" @click="deletePlaylist" :disabled="deleting">
              {{ deleting ? '...' : 'Delete' }}
            </button>
          </div>
        </div>
      </header>

      <div v-if="!playlist.items?.length" class="empty-tracks">
        <p>No tracks in this playlist.</p>
      </div>

      <ol v-else class="track-list">
        <li
          v-for="(item, idx) in playlist.items"
          :key="item.id"
          class="track-row"
          :class="{ active: isCurrentTrack(item.song) }"
          @click="playSong(item.song, idx)"
        >
          <span class="track-num">{{ idx + 1 }}</span>
          <img
            v-if="item.song"
            :src="getAlbumArt(item.song)"
            class="track-art"
            loading="lazy"
          />
          <div class="track-info">
            <span class="track-title">{{ item.song?.title || 'Unknown' }}</span>
            <span class="track-artist">{{ item.song?.artist || '' }}</span>
          </div>
          <span class="track-genre" v-if="item.song?.genre">{{ item.song.genre }}</span>
          <span class="track-duration">{{ formatDuration(item.song?.duration_sec) }}</span>
        </li>
      </ol>
    </div>
  </section>
</template>

<style scoped>
.page { max-width: 1180px; margin: auto; }

.loading-state { padding: 20px 0; }
.skeleton-header { height: 80px; border-radius: 12px; background: rgba(255,255,255,.04); margin-bottom: 20px; animation: pulse 1.5s ease-in-out infinite; }
.skeleton-row { height: 56px; border-radius: 8px; background: rgba(255,255,255,.03); margin-bottom: 4px; animation: pulse 1.5s ease-in-out infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.5} }

.error-banner { padding: 10px 14px; border: 1px solid rgba(248,113,113,.3); border-radius: 10px; background: rgba(248,113,113,.08); color: #f87171; font-size: 13px; }

.back-btn {
  background: none; border: none; color: #8e97a6; font-size: 13px; cursor: pointer;
  padding: 0; margin-bottom: 16px; transition: .2s;
}
.back-btn:hover { color: #f5b942; }

.pl-header { margin-bottom: 24px; }

.pl-main { display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; }

.pl-info h1 { margin: 0 0 6px; font-size: clamp(26px, 4vw, 36px); letter-spacing: -.04em; }
.desc { margin: 0 0 10px; color: #8e97a6; font-size: 14px; font-style: italic; }
.meta { display: flex; align-items: center; gap: 6px; color: #687180; font-size: 12px; }
.dot { color: #3a3f4b; }

.pl-actions { display: flex; gap: 10px; flex-shrink: 0; }
.play-all-btn {
  padding: 10px 24px; border-radius: 10px; border: none;
  background: #f5b942; color: #17191d; font-weight: 700; font-size: 13px;
  cursor: pointer; transition: .2s; white-space: nowrap;
}
.play-all-btn:hover { background: #e5a932; }
.play-all-btn:disabled { opacity: .4; cursor: default; }

.delete-btn {
  padding: 10px 18px; border-radius: 10px; border: 1px solid rgba(248,113,113,.3);
  background: rgba(248,113,113,.08); color: #f87171; font-size: 13px;
  cursor: pointer; transition: .2s; white-space: nowrap;
}
.delete-btn:hover { background: rgba(248,113,113,.15); }
.delete-btn:disabled { opacity: .4; cursor: default; }

.empty-tracks { text-align: center; padding: 60px 20px; color: #687180; font-size: 14px; }

.track-list { list-style: none; padding: 0; margin: 0; }

.track-row {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 12px; border-radius: 8px; cursor: pointer; transition: .15s;
}
.track-row:hover { background: rgba(255,255,255,.04); }
.track-row.active { background: rgba(245,185,66,.08); }

.track-num { width: 28px; text-align: right; color: #687180; font-size: 13px; font-variant-numeric: tabular-nums; }
.track-row.active .track-num { color: #f5b942; }

.track-art { width: 40px; height: 40px; border-radius: 6px; object-fit: cover; background: rgba(255,255,255,.05); flex-shrink: 0; }

.track-info { flex: 1; min-width: 0; }
.track-title { display: block; font-size: 14px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.track-row.active .track-title { color: #f5b942; }
.track-artist { display: block; font-size: 12px; color: #8e97a6; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.track-genre {
  font-size: 11px; color: #687180; background: rgba(255,255,255,.05);
  padding: 2px 8px; border-radius: 10px; white-space: nowrap;
}

.track-duration { font-size: 12px; color: #687180; font-variant-numeric: tabular-nums; width: 40px; text-align: right; }

@media(max-width: 600px) {
  .pl-main { flex-direction: column; }
  .track-genre { display: none; }
}
</style>
