<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import client from '../../../api/client'
import { usePlayer } from '../../../shared/composables/usePlayer'

const { playTrack, playFullTrack, playerState } = usePlayer()

const songs = ref([])
const loading = ref(true)
const loadingMore = ref(false)
const error = ref('')
const query = ref('')
const filter = ref('All')
const offset = ref(0)
const total = ref(0)
const pageSize = 20
const hasMore = computed(() => songs.value.length < total.value)

const moods = ['All', 'Happy', 'Chill', 'Sad', 'Energetic', 'Romantic']

// Debounced search
let searchTimeout = null
const debouncedQuery = ref('')
watch(query, (val) => {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => { debouncedQuery.value = val }, 300)
})

async function fetchSongs(reset = false) {
  if (reset) {
    offset.value = 0
    songs.value = []
    loading.value = true
  } else {
    loadingMore.value = true
  }
  try {
    const params = { offset: offset.value, limit: pageSize }
    if (filter.value !== 'All') params.mood = filter.value.toLowerCase()
    const [songsRes, countRes] = await Promise.all([
      client.get('/songs', { params }),
      client.get('/songs/count', { params: filter.value !== 'All' ? { mood: filter.value.toLowerCase() } : {} })
    ])
    if (reset) {
      songs.value = songsRes.data
    } else {
      songs.value.push(...songsRes.data)
    }
    total.value = countRes.data.count
    offset.value = songs.value.length
  } catch {
    error.value = 'Failed to load library'
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

// Filter by mood — reset and refetch
watch(filter, () => fetchSongs(true))

// Search is client-side on the loaded songs
const filteredSongs = computed(() => {
  if (!debouncedQuery.value) return songs.value
  const q = debouncedQuery.value.toLowerCase()
  return songs.value.filter(s =>
    `${s.title} ${s.artist} ${s.album || ''}`.toLowerCase().includes(q)
  )
})

async function deleteSong(id) {
  if (!confirm('Remove this song?')) return
  try {
    await client.delete(`/songs/${id}`)
    songs.value = songs.value.filter(s => s.id !== id)
    total.value--
  } catch {
    error.value = 'Failed to delete'
  }
}

function isCurrentPlaying(song) {
  return playerState.currentTrack?.id === song.id && playerState.isPlaying
}

// Infinite scroll with Intersection Observer
const sentinel = ref(null)
let observer = null

onMounted(() => {
  fetchSongs(true)
  observer = new IntersectionObserver(
    (entries) => {
      if (entries[0].isIntersecting && hasMore.value && !loading.value && !loadingMore.value) {
        fetchSongs(false)
      }
    },
    { rootMargin: '200px' }
  )
})

watch(sentinel, (el) => {
  if (el) observer?.observe(el)
  else observer?.disconnect()
})

onUnmounted(() => observer?.disconnect())
</script>

<template>
  <section class="page">
    <header class="heading">
      <div>
        <p class="eyebrow">YOUR COLLECTION</p>
        <h1>Song library</h1>
        <p>Everything you've saved, in one place.</p>
      </div>
      <span class="count">{{ total }} songs</span>
    </header>

    <div class="toolbar">
      <label class="search">
        <span>⌕</span>
        <input v-model="query" placeholder="Search your library..." aria-label="Search library">
      </label>
    </div>

    <div class="pills">
      <button v-for="mood in moods" :key="mood" type="button" :class="{ active: filter === mood }" @click="filter = mood">{{ mood }}</button>
    </div>

    <div v-if="loading" class="rows">
      <div v-for="n in 8" :key="n" class="skeleton row-skeleton"></div>
    </div>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <div v-else-if="!loading && !filteredSongs.length && !error" class="empty">
      <div>♫</div>
      <h2>Your library is empty</h2>
      <p>Import some music and it will appear here.</p>
      <router-link to="/import" class="empty-btn">Import music</router-link>
    </div>

    <div v-else class="table-wrap">
      <div class="table-head">
        <span>#</span>
        <span>Title</span>
        <span>Artist</span>
        <span>Mood</span>
        <span>Plays</span>
        <span>Skips</span>
        <span></span>
      </div>
      <button
        v-for="(song, index) in filteredSongs"
        :key="song.id"
        class="song-row"
        :class="{ playing: isCurrentPlaying(song) }"
        type="button"
        @click="playTrack(song, 'preview')"
      >
        <span>{{ String(index + 1).padStart(2, '0') }}</span>
        <span class="title">
          <span class="mini-art">{{ song.title?.charAt(0) || 'M' }}</span>
          <strong>{{ song.title }}</strong>
        </span>
        <span>{{ song.artist }}</span>
        <span><b class="badge">{{ song.mood || 'Chill' }}</b></span>
        <span>{{ song.play_count || 0 }}</span>
        <span>{{ song.skip_count || 0 }}</span>
        <span class="row-actions">
          <button type="button" :class="{ liked: song.saved }" @click.stop="playFullTrack(song)" title="Play full">🎬</button>
          <button type="button" @click.stop="deleteSong(song.id)" title="Remove">×</button>
        </span>
      </button>

      <!-- Infinite scroll sentinel -->
      <div ref="sentinel" class="sentinel"></div>

      <div v-if="loadingMore" class="loading-more">
        <div class="spinner"></div>
        <span>Loading more...</span>
      </div>

      <div v-if="!hasMore && filteredSongs.length" class="end-of-list">
        You've reached the end
      </div>
    </div>
  </section>
</template>

<style scoped>
.page{max-width:1240px;margin:auto}
.heading{display:flex;justify-content:space-between;align-items:end;margin-bottom:28px}
.eyebrow{margin:0 0 8px;color:#f5b942;font-size:10px;font-weight:800;letter-spacing:.14em}
.heading h1{margin:0;font-size:clamp(30px,5vw,44px);letter-spacing:-.055em}
.heading p:not(.eyebrow){margin:10px 0 0;color:#8e97a6;font-size:14px}
.count{color:#8e97a6;font-size:12px}
.toolbar{display:flex;gap:10px}
.search{display:flex;align-items:center;gap:10px;flex:1;padding:0 14px;border:1px solid rgba(255,255,255,.08);border-radius:10px;background:rgba(255,255,255,.035)}
.search:focus-within{border-color:#f5b942;box-shadow:0 0 0 3px rgba(245,185,66,.13)}
.search span{color:#f5b942;font-size:22px}
.search input{width:100%;height:46px;border:0;outline:0;background:transparent;color:#f4f5f7;font:inherit}
.pills{display:flex;gap:8px;margin:15px 0 25px;overflow:auto}
.pills button{flex:none;padding:8px 13px;border:1px solid rgba(255,255,255,.08);border-radius:99px;background:transparent;color:#8e97a6;font-size:11px;cursor:pointer;transition:.2s}
.pills button:hover{border-color:rgba(245,185,66,.3);color:#f5b942}
.pills button.active{border-color:#f5b942;background:rgba(245,185,66,.13);color:#f5b942}
.error-banner{margin:0 0 16px;padding:10px 14px;border:1px solid rgba(248,113,113,.3);border-radius:10px;background:rgba(248,113,113,.08);color:#f87171;font-size:12px}
.table-wrap{overflow:auto;border:1px solid rgba(255,255,255,.08);border-radius:12px}
.table-head,.song-row{min-width:750px;display:grid;grid-template-columns:40px 1.6fr 1.2fr .8fr .6fr .6fr 80px;align-items:center;gap:12px;padding:0 18px}
.table-head{height:42px;color:#687180;font-size:10px;letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid rgba(255,255,255,.08)}
.song-row{width:100%;height:67px;border:0;border-bottom:1px solid rgba(255,255,255,.06);background:transparent;color:#8e97a6;text-align:left;font-size:12px;cursor:pointer;transition:.15s}
.song-row:last-child{border-bottom:0}
.song-row:hover{background:rgba(255,255,255,.035);color:#f4f5f7}
.song-row.playing{background:rgba(245,185,66,.06)}
.song-row.playing .title strong{color:#f5b942}
.title{display:flex;align-items:center;gap:10px;min-width:0}
.title strong{overflow:hidden;color:#f4f5f7;text-overflow:ellipsis;white-space:nowrap}
.mini-art{width:35px;height:35px;display:grid;place-items:center;flex:none;border-radius:7px;background:linear-gradient(135deg,#3a4350,#bf7a37);color:#fff;font-weight:800;font-size:13px}
.badge{padding:5px 8px;border-radius:99px;background:rgba(245,185,66,.13);color:#f5b942;font-size:10px;font-weight:600}
.row-actions{display:flex;justify-content:end;gap:5px;opacity:0}
.song-row:hover .row-actions{opacity:1}
.row-actions button{border:0;background:transparent;color:#687180;font-size:18px;cursor:pointer;transition:.15s}
.row-actions button:hover,.row-actions button.liked{color:#f5b942}
.sentinel{height:1px}
.loading-more{display:flex;align-items:center;justify-content:center;gap:10px;padding:24px;color:#8e97a6;font-size:13px}
.spinner{width:18px;height:18px;border:2px solid rgba(255,255,255,.1);border-top-color:#f5b942;border-radius:50%;animation:spin .6s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.end-of-list{text-align:center;padding:20px;color:#687180;font-size:12px}
.empty{text-align:center;padding:74px 20px;border:1px dashed rgba(255,255,255,.12);border-radius:12px}
.empty>div{color:#f5b942;font-size:46px}
.empty h2{margin:12px 0 8px;font-size:19px}
.empty p{color:#8e97a6;font-size:13px}
.empty-btn{display:inline-block;margin-top:12px;padding:10px 15px;border:0;border-radius:9px;background:#f5b942;color:#17191d;font-weight:800;text-decoration:none;cursor:pointer;transition:.2s}
.empty-btn:hover{background:#ffd36d}
.skeleton{background:linear-gradient(90deg,rgba(255,255,255,.05),rgba(255,255,255,.12),rgba(255,255,255,.05));background-size:200% 100%;animation:shimmer 1.3s infinite}
@keyframes shimmer{to{background-position:-200% 0}}
.row-skeleton{height:58px;margin-bottom:1px;border-radius:7px}
@media(max-width:600px){.heading{align-items:start}.count{display:none}.toolbar{flex-direction:column}.pills{margin-bottom:18px}}
</style>
