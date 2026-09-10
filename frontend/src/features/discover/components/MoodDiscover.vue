<script setup>
import { ref, computed, watch } from 'vue'
import client from '../../../api/client'
import { usePlayer } from '../../../shared/composables/usePlayer'

const { playTrack, playFullTrack, playerState, setQueue } = usePlayer()
const mood = ref('')
const isGenerating = ref(false)
const playlist = ref(null)
const error = ref('')
const addingTrack = ref({})

const userName = ref(localStorage.getItem('userName') || 'Listener')

const timeOfDay = computed(() => {
  const h = new Date().getHours()
  return h < 12 ? 'morning' : h < 18 ? 'afternoon' : 'evening'
})

const moodTags = ['Euphoric', 'Chill', 'Sad', 'Energetic']

async function handleSearch(moodText) {
  const prompt = moodText || mood.value
  if (!prompt.trim()) return
  isGenerating.value = true
  error.value = ''
  playlist.value = null
  try {
    const res = await client.post('/playlists/generate', { prompt })
    playlist.value = res.data
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to generate playlist'
  } finally {
    isGenerating.value = false
  }
}

// Fetch album art when playlist changes
watch(playlist, (val) => {
  if (val?.items) {
    val.items.forEach(item => fetchAlbumArt(item.song))
  }
  if (val?.new_recommendations) {
    val.new_recommendations.forEach(rec => fetchAlbumArt(rec))
  }
}, { deep: true })

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

function playItem(item) {
  setQueue(playlist.value.items.map(i => i.song), playlist.value.items.findIndex(i => i.song.id === item.song.id))
  playTrack(item.song, 'preview')
}

function playRec(rec) {
  setQueue(playlist.value.new_recommendations, playlist.value.new_recommendations.findIndex(r => r.id === rec.id))
  playTrack(rec, 'preview')
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
</script>

<template>
  <section class="page">
    <header class="hero">
      <div>
        <p class="eyebrow">PERSONAL DISCOVERY</p>
        <h1>Good {{ timeOfDay }}, {{ userName }}</h1>
        <p class="subcopy">Tell us what you want to feel. We'll find the sound.</p>
      </div>
      <div class="pulse" aria-hidden="true"><span></span><span></span><span></span></div>
    </header>

    <form class="mood-search" @submit.prevent="handleSearch()">
      <span class="sparkle">✨</span>
      <textarea v-model="mood" rows="2" placeholder="Describe your mood..." aria-label="Describe your mood"></textarea>
      <button type="submit" :disabled="isGenerating || !mood.trim()">
        <span v-if="isGenerating">Curating...</span>
        <span v-else>Discover</span>
      </button>
    </form>

    <div class="tags">
      <button v-for="tag in moodTags" :key="tag" type="button" :class="{ selected: mood === tag }" @click="mood = tag; handleSearch(tag)">{{ tag }}</button>
    </div>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <div v-if="playlist" class="profile-card">
      <div>
        <p class="eyebrow">YOUR PLAYLIST</p>
        <h2>{{ playlist.name }}</h2>
        <p class="subcopy">"{{ playlist.description }}"</p>
      </div>
      <div v-if="playlist.items?.length" class="bars">
        <div v-for="(item, i) in playlist.items.slice(0, 4)" :key="item.id" class="bar-row">
          <span>{{ item.song.mood || 'Chill' }}</span>
          <div><i :style="{ width: `${100 - i * 20}%` }"></i></div>
          <b>{{ 100 - i * 20 }}%</b>
        </div>
      </div>
    </div>

    <div class="section-heading">
      <div>
        <p class="eyebrow">CURATED FOR YOU</p>
        <h2>AI playlist results</h2>
      </div>
      <button class="ghost" type="button" @click="handleSearch()" :disabled="isGenerating">Refresh</button>
    </div>

    <div v-if="isGenerating" class="grid">
      <article v-for="n in 6" :key="n" class="song-card skeleton-card">
        <div class="skeleton art"></div>
        <div class="skeleton line"></div>
        <div class="skeleton short"></div>
      </article>
    </div>

    <div v-else-if="!playlist" class="empty">
      <div class="empty-icon">♫</div>
      <h2>Describe your mood to discover music</h2>
      <p>Start with a feeling, a memory, or a moment.</p>
    </div>

    <template v-else>
      <div v-if="playlist.items?.length" class="grid">
        <article v-for="item in playlist.items" :key="item.id" class="song-card">
          <div class="cover">
            <img v-if="item.song.album_art_url || getAlbumArt(item.song)" :src="item.song.album_art_url || getAlbumArt(item.song)" :alt="`${item.song.title} artwork`" loading="lazy">
            <span v-else :style="{ background: getArtGradient(item.song.title) }">{{ item.song.title?.charAt(0) || 'M' }}</span>
            <button class="play" type="button" aria-label="Play song" @click="playItem(item)">▶</button>
          </div>
          <div class="song-meta">
            <div>
              <h3>{{ item.song.title }}</h3>
              <p>{{ item.song.artist }}</p>
            </div>
          </div>
          <span class="mood-badge">{{ item.song.mood || 'Chill' }}</span>
          <div class="feedback">
            <button type="button" :class="{ active: isCurrentPlaying(item.song, 'preview') }" @click="playItem(item)">{{ isCurrentPlaying(item.song, 'preview') ? '⏸ 30s' : '🎧 30s' }}</button>
            <button type="button" :class="{ active: isCurrentPlaying(item.song, 'full') }" @click="playFullTrack(item.song)">{{ isCurrentPlaying(item.song, 'full') ? '⏸ Full' : '🎵 Full' }}</button>
          </div>
        </article>
      </div>

      <div v-if="playlist.new_recommendations?.length" class="section-heading" style="margin-top: 38px;">
        <div>
          <p class="eyebrow">RECOMMENDED</p>
          <h2>You might also like</h2>
        </div>
      </div>

      <div v-if="playlist.new_recommendations?.length" class="grid">
        <article v-for="rec in playlist.new_recommendations" :key="rec.title" class="song-card">
          <div class="cover">
            <img v-if="rec.album_art_url || getAlbumArt(rec)" :src="rec.album_art_url || getAlbumArt(rec)" :alt="`${rec.title} artwork`" loading="lazy">
            <span v-else :style="{ background: getArtGradient(rec.title) }">{{ rec.title?.charAt(0) || 'M' }}</span>
            <button class="play" type="button" aria-label="Play song" @click="playRec(rec)">▶</button>
          </div>
          <div class="song-meta">
            <div>
              <h3>{{ rec.title }}</h3>
              <p>{{ rec.artist }}</p>
            </div>
          </div>
          <span class="mood-badge">{{ rec.mood || 'Chill' }}</span>
          <div class="feedback">
            <button type="button" :class="{ active: isCurrentPlaying(rec, 'preview') }" @click="playRec(rec)">{{ isCurrentPlaying(rec, 'preview') ? '⏸ 30s' : '🎧 30s' }}</button>
            <button type="button" :class="{ active: isCurrentPlaying(rec, 'full') }" @click="playFullTrack(rec)">{{ isCurrentPlaying(rec, 'full') ? '⏸ Full' : '🎵 Full' }}</button>
            <button class="import-btn" type="button" :disabled="addingTrack[rec.title] === true || addingTrack[rec.title] === 'done'" @click="addToLibrary(rec)">{{ addingTrack[rec.title] === 'done' ? '✓ Saved' : addingTrack[rec.title] ? '...' : '+ Save' }}</button>
          </div>
        </article>
      </div>
    </template>
  </section>
</template>

<style scoped>
.page{max-width:1240px;margin:auto}
.hero{display:flex;align-items:end;justify-content:space-between;margin-bottom:30px}
.eyebrow{margin:0 0 8px;color:#f5b942;font-size:10px;font-weight:800;letter-spacing:.14em}
.hero h1{margin:0;font-size:clamp(28px,5vw,44px);letter-spacing:-.055em}
.subcopy{margin:10px 0 0;color:#8e97a6;font-size:14px}
.pulse{display:flex;align-items:center;gap:4px;height:42px}
.pulse span{width:4px;border-radius:5px;background:#f5b942;animation:pulse 1.1s infinite ease-in-out}
.pulse span:nth-child(1){height:18px}
.pulse span:nth-child(2){height:38px;animation-delay:.15s}
.pulse span:nth-child(3){height:25px;animation-delay:.3s}
@keyframes pulse{50%{opacity:.4;transform:scaleY(.55)}}
.mood-search{display:flex;align-items:center;gap:14px;padding:14px 16px;border:1px solid rgba(255,255,255,.08);border-radius:12px;background:rgba(255,255,255,.035);transition:.2s}
.mood-search:focus-within{border-color:#f5b942;box-shadow:0 0 0 3px rgba(245,185,66,.13)}
.sparkle{color:#f5b942;font-size:22px}
.mood-search textarea{min-width:0;flex:1;resize:none;border:0;outline:0;background:transparent;color:#f4f5f7;font:inherit;line-height:1.5}
.mood-search textarea::placeholder{color:#687180}
.mood-search button{padding:10px 16px;border:0;border-radius:9px;background:#f5b942;color:#17191d;font-size:12px;font-weight:800;cursor:pointer;transition:.2s}
.mood-search button:hover{background:#ffd36d}
.mood-search button:disabled{opacity:.5;cursor:wait}
.tags{display:flex;gap:8px;margin:14px 0 30px;overflow:auto}
.tags button{flex:none;padding:8px 14px;border:1px solid rgba(255,255,255,.08);border-radius:99px;background:rgba(255,255,255,.035);color:#8e97a6;font-size:12px;cursor:pointer;transition:.2s}
.tags button:hover,.tags button.selected{border-color:#f5b942;background:rgba(245,185,66,.13);color:#f5b942}
.error-banner{margin:12px 0;padding:10px 14px;border:1px solid rgba(248,113,113,.3);border-radius:10px;background:rgba(248,113,113,.08);color:#f87171;font-size:12px}
.profile-card{display:flex;justify-content:space-between;gap:28px;padding:22px;border:1px solid rgba(255,255,255,.08);border-radius:12px;background:rgba(255,255,255,.035)}
h2{margin:0;font-size:20px;letter-spacing:-.03em}
.bars{width:min(100%,480px)}
.bar-row{display:grid;grid-template-columns:72px 1fr 35px;align-items:center;gap:10px;margin:8px 0;color:#8e97a6;font-size:11px}
.bar-row>div{height:5px;overflow:hidden;border-radius:99px;background:rgba(255,255,255,.08)}
.bar-row i{display:block;height:100%;border-radius:inherit;background:#f5b942}
.bar-row b{text-align:right;color:#f4f5f7;font-size:10px}
.section-heading{display:flex;align-items:end;justify-content:space-between;margin:38px 0 17px}
.section-heading h2{font-size:24px}
.ghost{border:1px solid rgba(255,255,255,.08);padding:10px 16px;border-radius:9px;background:transparent;color:#8e97a6;font-size:12px;font-weight:800;cursor:pointer;transition:.2s}
.ghost:hover{border-color:#f5b942;color:#f5b942}
.ghost:disabled{opacity:.5;cursor:wait}
.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}
.song-card{min-width:0;padding:10px;border:1px solid rgba(255,255,255,.08);border-radius:12px;background:rgba(255,255,255,.035);transition:.2s}
.song-card:hover{transform:translateY(-3px);border-color:rgba(245,185,66,.35)}
.cover{position:relative;aspect-ratio:1;display:grid;place-items:center;overflow:hidden;border-radius:8px;background:linear-gradient(135deg,#303846,#bb793b);color:#fff;font-size:44px;font-weight:800}
.cover img{width:100%;height:100%;object-fit:cover}
.play{position:absolute;right:10px;bottom:10px;width:38px;height:38px;border:0;border-radius:50%;background:#f5b942;color:#17191d;opacity:0;cursor:pointer;transition:.2s}
.song-card:hover .play{opacity:1}
.song-meta{display:flex;justify-content:space-between;gap:8px;margin:12px 2px 8px}
.song-meta h3{margin:0;overflow:hidden;font-size:13px;text-overflow:ellipsis;white-space:nowrap}
.song-meta p{margin:5px 0 0;color:#8e97a6;font-size:11px}
.mood-badge{display:inline-block;padding:4px 8px;border-radius:99px;background:rgba(245,185,66,.13);color:#f5b942;font-size:10px}
.feedback{display:flex;gap:6px;margin-top:10px;flex-wrap:wrap}
.feedback button{padding:5px 8px;border:1px solid rgba(255,255,255,.08);border-radius:7px;background:transparent;color:#687180;font-size:10px;cursor:pointer;transition:.2s}
.feedback button.active{border-color:#f5b942;background:rgba(245,185,66,.13);color:#f5b942}
.import-btn{padding:5px 8px;border:1px solid #f5b942;border-radius:7px;background:rgba(245,185,66,.13);color:#f5b942;font-size:10px;cursor:pointer;font-weight:600}
.import-btn:disabled{opacity:.5;cursor:wait}
.empty{text-align:center;padding:70px 20px;border:1px dashed rgba(255,255,255,.12);border-radius:12px}
.empty-icon{margin:auto auto 14px;color:#f5b942;font-size:46px}
.empty h2{font-size:18px}
.empty p{color:#8e97a6;font-size:13px}
.skeleton{background:linear-gradient(90deg,rgba(255,255,255,.05),rgba(255,255,255,.12),rgba(255,255,255,.05));background-size:200% 100%;animation:shimmer 1.3s infinite}
@keyframes shimmer{to{background-position:-200% 0}}
.skeleton.art{aspect-ratio:1;border-radius:8px}
.skeleton.line{width:75%;height:13px;margin:14px 0 8px;border-radius:4px}
.skeleton.short{width:45%;height:9px;border-radius:4px}
@media(max-width:800px){.profile-card{flex-direction:column}.bars{width:100%}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:480px){.hero{align-items:start}.pulse{display:none}.mood-search{align-items:stretch;flex-wrap:wrap}.mood-search textarea{flex-basis:calc(100% - 38px)}.mood-search button{width:100%}.grid{grid-template-columns:1fr}}
</style>

