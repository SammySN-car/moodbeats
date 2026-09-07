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
  try { searchResults.value = (await client.get('/songs/search', { params: { q: searchQuery.value } })).data }
  catch (err) { error.value = err.response?.data?.detail || 'Search failed' }
  finally { isSearching.value = false }
}

async function handleArtistSearch(name) {
  const q = name || artistQuery.value
  if (!q?.trim()) return
  artistQuery.value = q
  isSearchingArtist.value = true
  error.value = ''
  artistTracks.value = []
  try { artistTracks.value = (await client.get('/songs/artist', { params: { name: q.trim(), limit: 50 } })).data }
  catch (err) { error.value = err.response?.data?.detail || 'Search failed' }
  finally { isSearchingArtist.value = false }
}

async function importiTunes(track) {
  const key = track.title
  importingTracks.value[key] = true
  error.value = ''
  try {
    await client.post('/songs/import-itunes', { title: track.title, artist: track.artist })
    importingTracks.value[key] = 'done'
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
  } catch (err) {
    error.value = err.response?.data?.detail || 'Import failed'
  } finally { isImporting.value = false }
}

function isCurrentPlaying(t, m) {
  return playerState.currentTrack?.title === t.title && playerState.mode === m && playerState.isPlaying
}
</script>

<template>
  <div>
    <!-- Mode Switcher -->
    <div class="mode-bar">
      <button :class="['btn btn-sm btn-pill', searchMode === 'artist' ? 'btn-primary' : 'btn-secondary']" @click="searchMode = 'artist'">Artist Discography</button>
      <button :class="['btn btn-sm btn-pill', searchMode === 'track' ? 'btn-primary' : 'btn-secondary']" @click="searchMode = 'track'">Track & URL</button>
    </div>

    <!-- Artist Mode -->
    <div v-if="searchMode === 'artist'" class="panel animate-in">
      <div class="search-row">
        <div class="search-wrap">
          <svg class="search-ico" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input v-model="artistQuery" @keyup.enter="handleArtistSearch()" type="text" placeholder="Search any artist..." class="input-text search-input" />
        </div>
        <button class="btn btn-primary" :disabled="isSearchingArtist || !artistQuery.trim()" @click="handleArtistSearch()" style="flex-shrink:0;">
          <span v-if="isSearchingArtist">Searching...</span>
          <span v-else>Explore</span>
        </button>
      </div>

      <div class="quick-pills">
        <span class="pills-label">Trending:</span>
        <button v-for="a in ['Justin Bieber', 'The Weeknd', 'Taylor Swift', 'Eminem', 'Kordhell']" :key="a" class="btn btn-secondary btn-sm btn-pill" @click="handleArtistSearch(a)">{{ a }}</button>
      </div>

      <div v-if="error" class="alert-error mt-3">{{ error }}</div>

      <div v-if="artistTracks.length" class="results-section">
        <div class="section-head">
          <span class="section-title">{{ artistQuery }}</span>
          <span class="section-count">{{ artistTracks.length }} tracks</span>
        </div>
        <div class="grid-cards">
          <div v-for="(t, i) in artistTracks" :key="t.spotify_id" class="song-card" :style="{ animationDelay: `${i * 0.03}s` }">
            <div class="flex-between">
              <div class="flex-row" style="min-width:0;flex:1;">
                <img v-if="t.album_art_url" :src="t.album_art_url" width="40" height="40" class="song-cover" />
                <div style="overflow:hidden;min-width:0;">
                  <div class="s-title">{{ t.title }}</div>
                  <div class="s-artist">{{ t.artist }} <span v-if="t.album_name">· {{ t.album_name }}</span></div>
                </div>
              </div>
            </div>
            <div v-if="isInLibrary(t.title, t.artist)" class="in-library-badge">✓ In Library</div>
            <div class="flex-between" style="flex-wrap:wrap;gap:0.3rem;">
              <div class="flex-row" style="gap:0.3rem;">
                <button :class="['btn btn-sm', isCurrentPlaying(t, 'preview') ? 'btn-primary' : 'btn-secondary']" @click="playTrack(t, 'preview')">{{ isCurrentPlaying(t, 'preview') ? '⏸ 30s' : '🎧 30s' }}</button>
                <button :class="['btn btn-sm', isCurrentPlaying(t, 'full') ? 'btn-primary' : 'btn-secondary']" @click="playFullTrack(t)">{{ isCurrentPlaying(t, 'full') ? '⏸ Full' : '🎬 Full' }}</button>
              </div>
              <button :class="['btn btn-sm', importingTracks[t.title] === 'done' ? 'btn-secondary' : 'btn-primary']" :disabled="importingTracks[t.title] === true || importingTracks[t.title] === 'done'" @click="importiTunes(t)">{{ importingTracks[t.title] === 'done' ? '✓ Added' : importingTracks[t.title] ? '...' : '+ Add' }}</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Track Mode -->
    <div v-if="searchMode === 'track'" class="panel animate-in">
      <div class="search-row">
        <div class="search-wrap">
          <svg class="search-ico" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input v-model="searchQuery" @keyup.enter="handleSearch" type="text" placeholder="Search song title..." class="input-text search-input" />
        </div>
        <button class="btn btn-primary" :disabled="isSearching || !searchQuery.trim()" @click="handleSearch" style="flex-shrink:0;">
          <span v-if="isSearching">Searching...</span>
          <span v-else>Search</span>
        </button>
      </div>

      <div v-if="searchResults.length" class="results-list">
        <div v-for="(t, i) in searchResults" :key="t.spotify_id" class="result-row" :style="{ animationDelay: `${i * 0.03}s` }">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:1rem;width:100%;">
            <div class="flex-row" style="min-width:0;flex:1;">
              <img v-if="t.album_art_url" :src="t.album_art_url" width="38" height="38" class="song-cover" />
              <div style="overflow:hidden;min-width:0;">
                <div class="s-title">{{ t.title }}</div>
                <div class="s-artist">{{ t.artist }}</div>
              </div>
            </div>
            <div class="flex-row" style="gap:0.3rem;flex-shrink:0;">
              <button :class="['btn btn-sm', isCurrentPlaying(t, 'preview') ? 'btn-primary' : 'btn-secondary']" @click="playTrack(t, 'preview')">{{ isCurrentPlaying(t, 'preview') ? '⏸' : '🎧' }}</button>
              <button :class="['btn btn-sm', isCurrentPlaying(t, 'full') ? 'btn-primary' : 'btn-secondary']" @click="playFullTrack(t)">{{ isCurrentPlaying(t, 'full') ? '⏸' : '🎬' }}</button>
              <button class="btn btn-primary btn-sm" :disabled="isImporting" @click="importiTunes(t)">{{ isImporting ? '...' : '+ Add' }}</button>
            </div>
          </div>
          <div v-if="isInLibrary(t.title, t.artist)" class="in-library-badge">✓ In Library</div>
        </div>
      </div>

      <div class="sep-line"></div>

      <div class="url-section">
        <h4 class="sub-title">Or paste a Spotify URL</h4>
        <div class="search-row">
          <div class="search-wrap">
            <svg class="search-ico" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
            <input v-model="spotifyUrl" type="url" placeholder="https://open.spotify.com/track/..." class="input-text search-input" />
          </div>
          <button class="btn btn-primary" :disabled="isImporting || !spotifyUrl" @click="importSpotifyUrl()" style="flex-shrink:0;">
            <span v-if="isImporting">Importing...</span>
            <span v-else>Import</span>
          </button>
        </div>
      </div>

      <div v-if="error" class="alert-error mt-3">{{ error }}</div>

      <div v-if="importedSong" class="success-card mt-3 animate-in">
        <div class="flex-between">
          <div class="flex-row" style="min-width:0;flex:1;">
            <img v-if="importedSong.album_art_url" :src="importedSong.album_art_url" width="42" height="42" class="song-cover" />
            <div style="overflow:hidden;min-width:0;">
              <div style="font-weight:600;">{{ importedSong.title }}</div>
              <div class="text-secondary">{{ importedSong.artist }}</div>
            </div>
          </div>
          <span :class="['badge', `badge-${importedSong.mood || 'neutral'}`]">{{ importedSong.mood }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mode-bar { display: flex; gap: 0.4rem; margin-bottom: 1.25rem; }

.panel {
  background: var(--bg-overlay);
  backdrop-filter: blur(16px);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  padding: 1.5rem;
}

.search-row { display: flex; gap: 0.6rem; }

.search-wrap {
  flex: 1;
  position: relative;
}

.search-ico {
  position: absolute;
  left: 0.7rem;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  pointer-events: none;
  z-index: 1;
}

.search-input { padding-left: 2rem; }

.quick-pills {
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

.results-section { margin-top: 1.25rem; }

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.8rem;
}

.section-title { font-weight: 700; font-size: 0.88rem; }
.section-count { font-size: 0.72rem; color: var(--text-muted); }

.results-list { display: flex; flex-direction: column; gap: 0.5rem; margin-top: 1rem; }

.result-row {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.4rem;
  padding: 0.6rem 0.85rem;
  border-radius: var(--r-md);
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border);
  transition: all 0.2s;
}

.result-row:hover { border-color: var(--border-hover); background: rgba(255, 255, 255, 0.04); }

.sep-line { height: 1px; background: var(--border); margin: 1.5rem 0; }

.url-section { display: flex; flex-direction: column; gap: 0.75rem; }
.sub-title { font-size: 0.82rem; font-weight: 600; color: var(--text-secondary); }

.s-title { font-weight: 600; font-size: 0.83rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.s-artist { font-size: 0.73rem; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.success-card {
  background: rgba(52, 211, 153, 0.06);
  border: 1px solid rgba(52, 211, 153, 0.2);
  border-radius: var(--r-md);
  padding: 0.85rem 1rem;
}
.in-library-badge { font-size: 0.68rem; color: #34d399; font-weight: 600; margin-top: 0.3rem; }
</style>
