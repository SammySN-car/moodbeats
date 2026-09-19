<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import client from '../../../api/client'
import { usePlayer } from '../../../shared/composables/usePlayer'

const route = useRoute()
const { playTrack, toggleSave } = usePlayer()

const song = ref(null)
const loading = ref(true)
const error = ref('')
const albumArt = ref(null)

function formatDuration(sec) {
  if (!sec) return ''
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

async function fetchSong() {
  try {
    const res = await client.get(`/songs/${route.params.id}`)
    song.value = res.data
  } catch {
    error.value = 'Failed to load song'
  } finally {
    loading.value = false
  }
}

async function fetchAlbumArt() {
  if (!song.value) return
  try {
    const res = await client.get('/songs/album-art', {
      params: { title: song.value.title, artist: song.value.artist || '' }
    })
    albumArt.value = res.data?.album_art_url || null
  } catch {
    albumArt.value = null
  }
}

async function handleSave() {
  if (!song.value) return
  const res = await toggleSave(song.value)
  if (res) {
    song.value.saved = !song.value.saved
  }
}

const gradients = [
  'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
  'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
  'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
  'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
  'linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%)',
  'linear-gradient(135deg, #fccb90 0%, #d57eeb 100%)',
  'linear-gradient(135deg, #e0c3fc 0%, #8ec5fc 100%)',
  'linear-gradient(135deg, #f5576c 0%, #ff6a88 100%)',
  'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
]

function getArtGradient(title) {
  if (!title) return gradients[0]
  let hash = 0
  for (let i = 0; i < title.length; i++) {
    hash = title.charCodeAt(i) + ((hash << 5) - hash)
  }
  return gradients[Math.abs(hash) % gradients.length]
}

onMounted(async () => {
  await fetchSong()
  await fetchAlbumArt()
})
</script>

<template>
  <section class="song-detail">
    <button class="back-btn" @click="$router.back()">← Back to Library</button>

    <div v-if="loading" class="detail-loading">
      <div class="spinner"></div>
    </div>

    <div v-else-if="error" class="error-banner">{{ error }}</div>

    <div v-else-if="song" class="detail-grid">
      <div class="art-section">
        <div class="art-container">
          <img v-if="albumArt" :src="albumArt" :alt="song.title" class="album-art">
          <div v-else class="art-fallback" :style="{ background: getArtGradient(song.title) }">
            {{ song.title?.charAt(0) || 'M' }}
          </div>
        </div>
        <div class="play-actions">
          <button class="play-btn preview-btn" @click="playTrack(song, 'preview')">🎧 Preview</button>
          <button class="play-btn full-btn" @click="playTrack(song, 'full')">🎵 Full Song</button>
          <button class="play-btn save-btn" :class="{ saved: song.saved }" @click="handleSave">
            {{ song.saved ? '♥ Saved' : '♡ Save' }}
          </button>
        </div>
      </div>

      <div class="info-section">
        <h1>{{ song.title }}</h1>
        <p class="artist">{{ song.artist }}</p>

        <div class="metadata-grid">
          <div class="meta-card">
            <span class="meta-label">Mood</span>
            <span class="meta-value"><b class="badge">{{ song.mood || 'Unknown' }}</b></span>
          </div>
          <div class="meta-card">
            <span class="meta-label">Genre</span>
            <span class="meta-value">{{ song.genre || '—' }}</span>
          </div>
          <div class="meta-card">
            <span class="meta-label">Duration</span>
            <span class="meta-value">{{ formatDuration(song.duration_sec) }}</span>
          </div>
          <div class="meta-card">
            <span class="meta-label">Tempo</span>
            <span class="meta-value">{{ song.tempo || '—' }} BPM</span>
          </div>
          <div class="meta-card">
            <span class="meta-label">Energy</span>
            <span class="meta-value">{{ song.energy != null ? (song.energy * 100).toFixed(0) : '—' }}%</span>
          </div>
          <div class="meta-card">
            <span class="meta-label">Danceability</span>
            <span class="meta-value">{{ song.danceability != null ? (song.danceability * 100).toFixed(0) : '—' }}%</span>
          </div>
          <div class="meta-card">
            <span class="meta-label">Valence</span>
            <span class="meta-value">{{ song.valence != null ? (song.valence * 100).toFixed(0) : '—' }}%</span>
          </div>
          <div class="meta-card">
            <span class="meta-label">Acousticness</span>
            <span class="meta-value">{{ song.acousticness != null ? (song.acousticness * 100).toFixed(0) : '—' }}%</span>
          </div>
          <div class="meta-card">
            <span class="meta-label">Instrumentalness</span>
            <span class="meta-value">{{ song.instrumentalness != null ? (song.instrumentalness * 100).toFixed(0) : '—' }}%</span>
          </div>
          <div class="meta-card">
            <span class="meta-label">Speechiness</span>
            <span class="meta-value">{{ song.speechiness != null ? (song.speechiness * 100).toFixed(0) : '—' }}%</span>
          </div>
          <div class="meta-card">
            <span class="meta-label">Liveness</span>
            <span class="meta-value">{{ song.liveness != null ? (song.liveness * 100).toFixed(0) : '—' }}%</span>
          </div>
          <div class="meta-card">
            <span class="meta-label">Mood Confidence</span>
            <span class="meta-value">{{ song.mood_confidence != null ? (song.mood_confidence * 100).toFixed(0) : '—' }}%</span>
          </div>
          <div class="meta-card">
            <span class="meta-label">Lyrics Sentiment</span>
            <span class="meta-value">{{ song.lyrics_sentiment != null ? ((song.lyrics_sentiment > 0 ? '+' : '') + (song.lyrics_sentiment * 100).toFixed(0) + '%') : '—' }}</span>
          </div>
        </div>

        <div class="stats-row">
          <div class="stat">
            <span class="stat-value">{{ song.play_count || 0 }}</span>
            <span class="stat-label">Plays</span>
          </div>
          <div class="stat">
            <span class="stat-value">{{ song.skip_count || 0 }}</span>
            <span class="stat-label">Skips</span>
          </div>
          <div class="stat">
            <span class="stat-value">{{ formatDuration(song.total_listen_sec) }}</span>
            <span class="stat-label">Listened</span>
          </div>
          <div v-if="song.last_played_at" class="stat">
            <span class="stat-value">{{ new Date(song.last_played_at).toLocaleDateString() }}</span>
            <span class="stat-label">Last Played</span>
          </div>
        </div>

        <a v-if="song.spotify_url" :href="song.spotify_url" target="_blank" rel="noopener" class="spotify-link">
          Open in Spotify →
        </a>
      </div>
    </div>
  </section>
</template>

<style scoped>
.song-detail { max-width: 1100px; margin: auto; padding: 0 0 40px; }

.back-btn {
  background: transparent;
  border: 1px solid rgba(255,255,255,.08);
  border-radius: 8px;
  padding: 8px 16px;
  color: #8e97a6;
  font-size: 13px;
  cursor: pointer;
  transition: .2s;
  margin-bottom: 32px;
}
.back-btn:hover { border-color: #f5b942; color: #f5b942; }

.detail-loading { display: grid; place-items: center; padding: 120px 0; }
.spinner { width: 28px; height: 28px; border: 2px solid rgba(255,255,255,.1); border-top-color: #f5b942; border-radius: 50%; animation: spin .6s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.error-banner { padding: 10px 14px; border: 1px solid rgba(248,113,113,.3); border-radius: 10px; background: rgba(248,113,113,.08); color: #f87171; font-size: 12px; }

.detail-grid { display: grid; grid-template-columns: 340px 1fr; gap: 48px; align-items: start; }

.art-section { position: sticky; top: 24px; }
.art-container { width: 100%; aspect-ratio: 1; border-radius: 16px; overflow: hidden; margin-bottom: 20px; }
.album-art { width: 100%; height: 100%; object-fit: cover; }
.art-fallback {
  width: 100%; height: 100%;
  display: grid; place-items: center;
  color: #fff; font-size: 80px; font-weight: 800;
}

.play-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.play-btn {
  flex: 1;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,.08);
  background: rgba(255,255,255,.04);
  color: #f4f5f7;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: .2s;
}
.play-btn:hover { background: rgba(255,255,255,.08); }
.preview-btn:hover { border-color: #f5b942; color: #f5b942; }
.full-btn:hover { border-color: #43e97b; color: #43e97b; }
.save-btn:hover { border-color: #f87171; color: #f87171; }
.save-btn.saved { color: #f5b942; border-color: #f5b942; }

.info-section h1 { margin: 0; font-size: clamp(26px, 4vw, 38px); letter-spacing: -.04em; color: #f4f5f7; }
.artist { margin: 6px 0 28px; color: #8e97a6; font-size: 16px; }

.metadata-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 10px; margin-bottom: 28px; }
.meta-card {
  padding: 12px 14px;
  border: 1px solid rgba(255,255,255,.06);
  border-radius: 10px;
  background: rgba(255,255,255,.03);
}
.meta-label { display: block; color: #687180; font-size: 10px; letter-spacing: .06em; text-transform: uppercase; margin-bottom: 4px; }
.meta-value { display: block; color: #f4f5f7; font-size: 14px; font-weight: 600; }
.badge { padding: 3px 8px; border-radius: 99px; background: rgba(245,185,66,.13); color: #f5b942; font-size: 11px; font-weight: 600; }

.stats-row { display: flex; gap: 20px; padding: 20px 0; border-top: 1px solid rgba(255,255,255,.06); margin-bottom: 20px; }
.stat { display: flex; flex-direction: column; gap: 2px; }
.stat-value { color: #f4f5f7; font-size: 18px; font-weight: 700; }
.stat-label { color: #687180; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; }

.spotify-link {
  display: inline-block;
  padding: 12px 20px;
  border-radius: 10px;
  background: #1db954;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  text-decoration: none;
  transition: .2s;
}
.spotify-link:hover { background: #1ed760; }

@media (max-width: 768px) {
  .detail-grid { grid-template-columns: 1fr; gap: 32px; }
  .art-section { position: static; }
  .art-container { max-width: 320px; margin: 0 auto 20px; }
  .play-actions { justify-content: center; }
  .metadata-grid { grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); }
}
</style>
