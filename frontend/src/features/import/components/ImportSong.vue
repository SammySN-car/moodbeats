<script setup>
import { ref, onMounted } from 'vue'
import client from '../../../api/client'
import { usePlayer } from '../../../shared/composables/usePlayer'

const { playTrack, playFullTrack, playerState } = usePlayer()
const searchMode = ref('artist')
const searchQuery = ref('')
const searchResults = ref([])
const isSearching = ref(false)
const artistQuery = ref('')
const artistTracks = ref([])
const isSearchingArtist = ref(false)
const importingTracks = ref({})
const spotifyUrl = ref('')
const isImporting = ref(false)
const importedSong = ref(null)
const error = ref('')
const libraryTitles = ref([])
const toast = ref('')

async function loadLibrary() {
  try {
    const songs = (await client.get('/songs')).data
    libraryTitles.value = songs.map(s => (s.title + '|' + s.artist).toLowerCase())
  } catch {}
}

function isInLibrary(title, artist) {
  return libraryTitles.value.includes((title + '|' + artist).toLowerCase())
}

onMounted(loadLibrary)

async function handleSearch() {
  if (!searchQuery.value.trim()) return
  isSearching.value = true
  error.value = ''
  searchResults.value = []
  try {
    searchResults.value = (await client.get('/songs/search', { params: { q: searchQuery.value } })).data
  } catch (err) {
    error.value = err.response?.data?.detail || 'Search failed'
  } finally {
    isSearching.value = false
  }
}

async function handleArtistSearch(name) {
  const q = name || artistQuery.value
  if (!q?.trim()) return
  artistQuery.value = q
  isSearchingArtist.value = true
  error.value = ''
  artistTracks.value = []
  try {
    artistTracks.value = (await client.get('/songs/artist', { params: { name: q.trim(), limit: 50 } })).data
  } catch (err) {
    error.value = err.response?.data?.detail || 'Search failed'
  } finally {
    isSearchingArtist.value = false
  }
}

async function importiTunes(track) {
  const key = track.title
  importingTracks.value[key] = true
  error.value = ''
  try {
    await client.post('/songs/import-itunes', { title: track.title, artist: track.artist })
    importingTracks.value[key] = 'done'
    libraryTitles.value.push((track.title + '|' + track.artist).toLowerCase())
    toast.value = `"${track.title}" added to library!`
    setTimeout(() => toast.value = '', 3000)
  } catch (err) {
    importingTracks.value[key] = false
    error.value = err.response?.data?.detail || 'Import failed'
  }
}

async function importSpotifyUrl() {
  if (!spotifyUrl.value) return
  isImporting.value = true
  error.value = ''
  importedSong.value = null
  try {
    importedSong.value = (await client.post('/songs/import', { spotify_url: spotifyUrl.value })).data
    spotifyUrl.value = ''
    toast.value = `"${importedSong.value.title}" imported successfully!`
    setTimeout(() => toast.value = '', 3000)
  } catch (err) {
    error.value = err.response?.data?.detail || 'Import failed'
  } finally {
    isImporting.value = false
  }
}

function isCurrentPlaying(t, m) {
  return playerState.currentTrack?.title === t.title && playerState.mode === m && playerState.isPlaying
}
</script>

<template>
  <section class="page">
    <header class="heading">
      <div>
        <p class="eyebrow">GROW YOUR LIBRARY</p>
        <h1>Import music</h1>
        <p>Bring your favorite artists into MoodBeats.</p>
      </div>
    </header>

    <div class="mode-bar">
      <button :class="{ active: searchMode === 'artist' }" type="button" @click="searchMode = 'artist'">Artist Discography</button>
      <button :class="{ active: searchMode === 'track' }" type="button" @click="searchMode = 'track'">Track & URL</button>
    </div>

    <!-- Artist Mode -->
    <div v-if="searchMode === 'artist'">
      <form class="search" @submit.prevent="handleArtistSearch()">
        <span>⌕</span>
        <input v-model="artistQuery" placeholder="Search artists or tracks..." aria-label="Search artists or tracks">
        <button type="submit" :disabled="isSearchingArtist || !artistQuery.trim()">
          <span v-if="isSearchingArtist">Searching...</span>
          <span v-else>Search</span>
        </button>
      </form>

      <div class="quick-pills">
        <span class="pills-label">Trending:</span>
        <button v-for="a in ['Justin Bieber', 'The Weeknd', 'Taylor Swift', 'Eminem', 'Kordhell']" :key="a" class="pill-btn" type="button" @click="handleArtistSearch(a)">{{ a }}</button>
      </div>

      <div v-if="error" class="error-banner">{{ error }}</div>

      <div v-if="isSearchingArtist" class="grid">
        <article v-for="n in 6" :key="n" class="skeleton card"></article>
      </div>

      <div v-else-if="!artistTracks.length && !isSearchingArtist" class="empty">
        <div>＋</div>
        <h2>Search for an artist to import their music</h2>
        <p>Find a discography and add the tracks you love.</p>
      </div>

      <div v-else class="grid">
        <article v-for="t in artistTracks" :key="t.spotify_id" class="card">
          <div class="art">
            <img v-if="t.album_art_url" :src="t.album_art_url" :alt="`${t.title} artwork`">
            <span v-else>{{ t.title?.charAt(0) || 'M' }}</span>
          </div>
          <div class="card-copy">
            <h2>{{ t.title }}</h2>
            <p>{{ t.artist }} <span v-if="t.album_name">· {{ t.album_name }}</span></p>
            <span v-if="isInLibrary(t.title, t.artist)" class="in-library">In Library</span>
          </div>
          <div class="card-actions">
            <button class="play-btn" type="button" :class="{ active: isCurrentPlaying(t, 'preview') }" @click="playTrack(t, 'preview')">{{ isCurrentPlaying(t, 'preview') ? '⏸' : '🎧' }}</button>
            <button class="play-btn" type="button" :class="{ active: isCurrentPlaying(t, 'full') }" @click="playFullTrack(t)">{{ isCurrentPlaying(t, 'full') ? '⏸' : '🎬' }}</button>
            <button class="import" type="button" :disabled="importingTracks[t.title] === true || importingTracks[t.title] === 'done'" @click="importiTunes(t)">{{ importingTracks[t.title] === 'done' ? '✓ Added' : importingTracks[t.title] ? '...' : '+ Add' }}</button>
          </div>
        </article>
      </div>
    </div>

    <!-- Track & URL Mode -->
    <div v-if="searchMode === 'track'">
      <form class="search" @submit.prevent="handleSearch">
        <span>⌕</span>
        <input v-model="searchQuery" placeholder="Search song title..." aria-label="Search song title">
        <button type="submit" :disabled="isSearching || !searchQuery.trim()">
          <span v-if="isSearching">Searching...</span>
          <span v-else>Search</span>
        </button>
      </form>

      <div v-if="error" class="error-banner">{{ error }}</div>

      <div v-if="searchResults.length" class="grid">
        <article v-for="t in searchResults" :key="t.spotify_id" class="card">
          <div class="art">
            <img v-if="t.album_art_url" :src="t.album_art_url" :alt="`${t.title} artwork`">
            <span v-else>{{ t.title?.charAt(0) || 'M' }}</span>
          </div>
          <div class="card-copy">
            <h2>{{ t.title }}</h2>
            <p>{{ t.artist }}</p>
            <span v-if="isInLibrary(t.title, t.artist)" class="in-library">In Library</span>
          </div>
          <div class="card-actions">
            <button class="play-btn" type="button" :class="{ active: isCurrentPlaying(t, 'preview') }" @click="playTrack(t, 'preview')">{{ isCurrentPlaying(t, 'preview') ? '⏸' : '🎧' }}</button>
            <button class="play-btn" type="button" :class="{ active: isCurrentPlaying(t, 'full') }" @click="playFullTrack(t)">{{ isCurrentPlaying(t, 'full') ? '⏸' : '🎬' }}</button>
            <button class="import" type="button" :disabled="importingTracks[t.title] === true || importingTracks[t.title] === 'done'" @click="importiTunes(t)">{{ importingTracks[t.title] === 'done' ? '✓ Added' : importingTracks[t.title] ? '...' : '+ Add' }}</button>
          </div>
        </article>
      </div>

      <div class="sep-line"></div>

      <div class="url-section">
        <h4 class="sub-title">Or paste a Spotify URL</h4>
        <form class="search" @submit.prevent="importSpotifyUrl()">
          <span>🔗</span>
          <input v-model="spotifyUrl" type="url" placeholder="https://open.spotify.com/track/..." aria-label="Spotify URL">
          <button type="submit" :disabled="isImporting || !spotifyUrl">
            <span v-if="isImporting">Importing...</span>
            <span v-else>Import</span>
          </button>
        </form>
      </div>

      <div v-if="importedSong" class="success-card">
        <div class="art">
          <img v-if="importedSong.album_art_url" :src="importedSong.album_art_url" :alt="`${importedSong.title} artwork`">
          <span v-else>{{ importedSong.title?.charAt(0) || 'M' }}</span>
        </div>
        <div class="card-copy">
          <h2>{{ importedSong.title }}</h2>
          <p>{{ importedSong.artist }}</p>
        </div>
        <span class="badge">{{ importedSong.mood || 'Chill' }}</span>
      </div>
    </div>

    <div v-if="toast" class="toast" role="status">{{ toast }}</div>
  </section>
</template>

<style scoped>
.page{max-width:1100px;margin:auto}
.heading{display:flex;align-items:end;justify-content:space-between;gap:18px;margin-bottom:28px}
.eyebrow{margin:0 0 8px;color:#f5b942;font-size:10px;font-weight:800;letter-spacing:.14em}
.heading h1{margin:0;font-size:clamp(30px,5vw,44px);letter-spacing:-.055em}
.heading p:not(.eyebrow){margin:10px 0 0;color:#8e97a6;font-size:14px}
.mode-bar{display:flex;gap:8px;margin-bottom:22px}
.mode-bar button{padding:10px 16px;border:1px solid rgba(255,255,255,.08);border-radius:9px;background:rgba(255,255,255,.035);color:#8e97a6;font-size:12px;font-weight:600;cursor:pointer;transition:.2s}
.mode-bar button.active{border-color:#f5b942;background:rgba(245,185,66,.13);color:#f5b942}
.search{display:flex;align-items:center;gap:12px;padding:5px 6px 5px 15px;border:1px solid rgba(255,255,255,.08);border-radius:10px;background:rgba(255,255,255,.035);transition:.2s}
.search:focus-within{border-color:#f5b942;box-shadow:0 0 0 3px rgba(245,185,66,.13)}
.search span{color:#f5b942;font-size:22px}
.search input{min-width:0;flex:1;height:42px;border:0;outline:0;background:transparent;color:#f4f5f7;font:inherit}
.search button{border:0;border-radius:9px;padding:11px 17px;background:#f5b942;color:#17191d;font-weight:800;cursor:pointer;transition:.2s}
.search button:hover{background:#ffd36d}
.search button:disabled{opacity:.45;cursor:not-allowed}
.quick-pills{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin-top:14px}
.pills-label{font-size:10px;color:#687180;text-transform:uppercase;letter-spacing:.08em;font-weight:600}
.pill-btn{flex:none;padding:7px 12px;border:1px solid rgba(255,255,255,.08);border-radius:99px;background:transparent;color:#8e97a6;font-size:11px;cursor:pointer;transition:.2s}
.pill-btn:hover{border-color:#f5b942;color:#f5b942}
.error-banner{margin:12px 0;padding:10px 14px;border:1px solid rgba(248,113,113,.3);border-radius:10px;background:rgba(248,113,113,.08);color:#f87171;font-size:12px}
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin-top:25px}
.card{position:relative;display:flex;align-items:center;gap:14px;padding:12px;border:1px solid rgba(255,255,255,.08);border-radius:12px;background:rgba(255,255,255,.035);transition:.2s}
.card:hover{transform:translateY(-3px);border-color:rgba(245,185,66,.35)}
.art{width:70px;height:70px;display:grid;place-items:center;flex:none;overflow:hidden;border-radius:8px;background:linear-gradient(135deg,#354052,#bd7939);font-size:25px;font-weight:800;color:#fff}
.art img{width:100%;height:100%;object-fit:cover}
.card-copy{min-width:0;flex:1}
.card-copy h2{margin:0;overflow:hidden;font-size:13px;text-overflow:ellipsis;white-space:nowrap}
.card-copy p{margin:7px 0;color:#8e97a6;font-size:11px}
.in-library{display:inline-block;color:#34d399;font-size:10px;font-weight:600}
.card-actions{display:flex;gap:6px;align-items:center}
.play-btn{border:0;border-radius:7px;padding:6px 8px;background:rgba(255,255,255,.06);color:#8e97a6;font-size:11px;cursor:pointer;transition:.2s}
.play-btn.active{background:rgba(245,185,66,.13);color:#f5b942}
.import{border:0;border-radius:9px;padding:8px 11px;background:#f5b942;color:#17191d;font-size:11px;font-weight:800;cursor:pointer;transition:.2s}
.import:hover{background:#ffd36d}
.import:disabled{opacity:.45;cursor:not-allowed}
.sep-line{height:1px;background:rgba(255,255,255,.08);margin:28px 0}
.url-section{display:flex;flex-direction:column;gap:12px}
.sub-title{font-size:13px;font-weight:600;color:#8e97a6;margin:0}
.success-card{display:flex;align-items:center;gap:14px;padding:14px;margin-top:20px;border:1px solid rgba(52,211,153,.2);border-radius:12px;background:rgba(52,211,153,.06)}
.badge{padding:5px 8px;border-radius:99px;background:rgba(245,185,66,.13);color:#f5b942;font-size:10px;font-weight:600}
.empty{text-align:center;padding:76px 20px;border:1px dashed rgba(255,255,255,.12);border-radius:12px}
.empty>div{color:#f5b942;font-size:44px}
.empty h2{margin:12px 0 8px;font-size:18px}
.empty p{margin:0;color:#8e97a6;font-size:13px}
.toast{position:fixed;right:24px;bottom:24px;padding:13px 17px;border:1px solid rgba(52,211,153,.3);border-radius:10px;background:rgba(13,16,20,.94);color:#34d399;font-size:12px;z-index:100}
.skeleton{background:linear-gradient(90deg,rgba(255,255,255,.05),rgba(255,255,255,.12),rgba(255,255,255,.05));background-size:200% 100%;animation:shimmer 1.3s infinite}
@keyframes shimmer{to{background-position:-200% 0}}
.skeleton.card{height:96px}
@media(max-width:720px){.heading{align-items:start;flex-direction:column}.grid{grid-template-columns:1fr}.mode-bar{flex-wrap:wrap}}
</style>
