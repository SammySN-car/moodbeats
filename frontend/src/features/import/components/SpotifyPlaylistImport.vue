<script setup>
import { ref } from 'vue'
import client from '../../../api/client'

const playlistUrl = ref('')
const importing = ref(false)
const result = ref(null)
const error = ref('')

async function importPlaylist() {
  if (!playlistUrl.value.trim()) return
  importing.value = true
  error.value = ''
  result.value = null
  try {
    const res = await client.post('/playlists/import-spotify', {
      spotify_url: playlistUrl.value.trim()
    })
    result.value = res.data
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to import playlist'
  } finally {
    importing.value = false
  }
}
</script>

<template>
  <section class="page">
    <header class="heading">
      <div>
        <p class="eyebrow">IMPORT PLAYLIST</p>
        <h1>Spotify Playlist</h1>
        <p>Paste a Spotify playlist URL to import all matching tracks.</p>
      </div>
    </header>

    <form class="url-form" @submit.prevent="importPlaylist">
      <input
        v-model="playlistUrl"
        type="url"
        placeholder="https://open.spotify.com/playlist/..."
        aria-label="Spotify playlist URL"
      />
      <button type="submit" :disabled="importing || !playlistUrl.trim()">
        {{ importing ? 'Importing...' : 'Import' }}
      </button>
    </form>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <div v-if="result" class="result-card">
      <h3>{{ result.playlist_name }}</h3>
      <div class="stats">
        <div class="stat">
          <span class="stat-num">{{ result.total_tracks }}</span>
          <span class="stat-label">Total tracks</span>
        </div>
        <div class="stat matched">
          <span class="stat-num">{{ result.matched_tracks }}</span>
          <span class="stat-label">Matched</span>
        </div>
        <div class="stat unmatched">
          <span class="stat-num">{{ result.unmatched_tracks }}</span>
          <span class="stat-label">Not in library</span>
        </div>
      </div>
      <div v-if="result.unmatched_samples?.length" class="unmatched">
        <p>Tracks not in your library:</p>
        <ul>
          <li v-for="(track, i) in result.unmatched_samples" :key="i">{{ track }}</li>
        </ul>
      </div>
      <router-link to="/playlists" class="view-btn">View Playlists →</router-link>
    </div>
  </section>
</template>

<style scoped>
.page { max-width: 800px; margin: auto; }
.heading { margin-bottom: 28px; }
.eyebrow { margin: 0 0 8px; color: #f5b942; font-size: 10px; font-weight: 800; letter-spacing: .14em; }
.heading h1 { margin: 0; font-size: clamp(30px, 5vw, 44px); letter-spacing: -.055em; }
.heading p { margin: 10px 0 0; color: #8e97a6; font-size: 14px; }

.url-form {
  display: flex; gap: 12px; padding: 16px;
  border: 1px solid rgba(255,255,255,.08); border-radius: 12px;
  background: rgba(255,255,255,.035);
}
.url-form:focus-within { border-color: #f5b942; box-shadow: 0 0 0 3px rgba(245,185,66,.13); }
.url-form input {
  flex: 1; height: 46px; border: 0; outline: 0; background: transparent;
  color: #f4f5f7; font: inherit; font-size: 14px;
}
.url-form input::placeholder { color: #687180; }
.url-form button {
  padding: 10px 20px; border: 0; border-radius: 9px;
  background: #f5b942; color: #17191d; font-size: 13px; font-weight: 800;
  cursor: pointer; transition: .2s;
}
.url-form button:hover { background: #ffd36d; }
.url-form button:disabled { opacity: .5; cursor: wait; }

.error-banner {
  margin: 16px 0; padding: 10px 14px;
  border: 1px solid rgba(248,113,113,.3); border-radius: 10px;
  background: rgba(248,113,113,.08); color: #f87171; font-size: 12px;
}

.result-card {
  margin-top: 24px; padding: 24px;
  border: 1px solid rgba(52,211,153,.3); border-radius: 12px;
  background: rgba(52,211,153,.06);
}
.result-card h3 { margin: 0 0 16px; font-size: 18px; }

.stats { display: flex; gap: 20px; margin-bottom: 16px; }
.stat { text-align: center; }
.stat-num { display: block; font-size: 28px; font-weight: 800; color: #f4f5f7; }
.stat-label { font-size: 11px; color: #8e97a6; }
.stat.matched .stat-num { color: #34d399; }
.stat.unmatched .stat-num { color: #f87171; }

.unmatched { margin-top: 12px; }
.unmatched p { color: #8e97a6; font-size: 12px; margin: 0 0 8px; }
.unmatched ul { list-style: none; padding: 0; margin: 0; }
.unmatched li { padding: 4px 0; color: #687180; font-size: 12px; border-bottom: 1px solid rgba(255,255,255,.05); }

.view-btn {
  display: inline-block; margin-top: 16px; padding: 10px 16px;
  border: 1px solid #f5b942; border-radius: 9px;
  background: rgba(245,185,66,.13); color: #f5b942;
  font-size: 12px; font-weight: 800; text-decoration: none; transition: .2s;
}
.view-btn:hover { background: rgba(245,185,66,.25); }
</style>
