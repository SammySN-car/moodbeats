<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import client from '../../../api/client'

const router = useRouter()
const playlists = ref([])
const loading = ref(true)
const error = ref('')
const deleteError = ref('')

const visiblePlaylists = computed(() => {
  return playlists.value.filter(pl => (pl.items?.length || 0) > 0)
})

function formatRelativeTime(dateStr) {
  if (!dateStr) return ''
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  const diff = now - then
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  return new Date(dateStr).toLocaleDateString()
}

async function fetchPlaylists() {
  loading.value = true
  try {
    const res = await client.get('/playlists', { params: { limit: 50 } })
    playlists.value = res.data
  } catch {
    error.value = 'Failed to load playlists'
  } finally {
    loading.value = false
  }
}

async function deletePlaylist(pl, e) {
  e.stopPropagation()
  if (!confirm(`Delete "${pl.name}"?`)) return
  try {
    await client.delete(`/playlists/${pl.id}`)
    playlists.value = playlists.value.filter(p => p.id !== pl.id)
  } catch {
    deleteError.value = 'Failed to delete'
    setTimeout(() => deleteError.value = '', 3000)
  }
}

function openPlaylist(pl) {
  router.push(`/playlists/${pl.id}`)
}

onMounted(fetchPlaylists)
</script>

<template>
  <section class="page">
    <header class="heading">
      <div>
        <p class="eyebrow">YOUR HISTORY</p>
        <h1>Playlists</h1>
        <p>Playlists you've generated or imported.</p>
      </div>
    </header>

    <div v-if="deleteError" class="error-banner">{{ deleteError }}</div>

    <div v-if="loading" class="grid">
      <div v-for="n in 4" :key="n" class="skeleton-card">
        <div class="skeleton-line w60"></div>
        <div class="skeleton-line w80"></div>
        <div class="skeleton-line w40"></div>
      </div>
    </div>

    <div v-else-if="error" class="error-banner">{{ error }}</div>

    <div v-else-if="!visiblePlaylists.length" class="empty">
      <div class="empty-icon">&#127925;</div>
      <h2>No playlists yet</h2>
      <p>Generate your first playlist on the Discover page.</p>
      <router-link to="/discover" class="empty-btn">Go to Discover</router-link>
    </div>

    <div v-else class="grid">
      <article
        v-for="pl in visiblePlaylists"
        :key="pl.id"
        class="playlist-card"
        @click="openPlaylist(pl)"
      >
        <div class="card-top">
          <h3>{{ pl.name }}</h3>
          <button class="card-delete" @click="deletePlaylist(pl, $event)" title="Delete playlist">&times;</button>
        </div>
        <p class="desc">"{{ pl.description }}"</p>
        <div class="meta">
          <span>{{ pl.items?.length || 0 }} tracks</span>
          <span>{{ formatRelativeTime(pl.created_at) }}</span>
        </div>
        <p v-if="pl.source_prompt" class="prompt">Prompt: "{{ pl.source_prompt }}"</p>
      </article>
    </div>
  </section>
</template>

<style scoped>
.page{max-width:1180px;margin:auto}
.heading{display:flex;justify-content:space-between;align-items:end;margin-bottom:28px}
.eyebrow{margin:0 0 8px;color:#f5b942;font-size:10px;font-weight:800;letter-spacing:.14em}
.heading h1{margin:0;font-size:clamp(30px,5vw,44px);letter-spacing:-.055em}
.heading p:not(.eyebrow){margin:10px 0 0;color:#8e97a6;font-size:14px}
.error-banner{margin:0 0 16px;padding:10px 14px;border:1px solid rgba(248,113,113,.3);border-radius:10px;background:rgba(248,113,113,.08);color:#f87171;font-size:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px}
.skeleton-card{padding:22px;border:1px solid rgba(255,255,255,.08);border-radius:12px;background:rgba(255,255,255,.035);animation:pulse 1.5s ease-in-out infinite}
.skeleton-line{height:12px;border-radius:6px;background:rgba(255,255,255,.08);margin-bottom:10px}
.w60{width:60%}.w80{width:80%}.w40{width:40%}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
.empty{display:flex;flex-direction:column;align-items:center;text-align:center;padding:80px 20px}
.empty-icon{font-size:48px;margin-bottom:16px}
.empty h2{margin:0 0 8px;font-size:22px}
.empty p{margin:0 0 20px;color:#8e97a6;font-size:14px}
.empty-btn{padding:10px 24px;border-radius:10px;background:#f5b942;color:#17191d;font-weight:700;font-size:13px;text-decoration:none;transition:.2s}
.empty-btn:hover{background:#e5a932}
.playlist-card{padding:22px;border:1px solid rgba(255,255,255,.08);border-radius:12px;background:rgba(255,255,255,.035);transition:.2s;cursor:pointer}
.playlist-card:hover{border-color:rgba(245,185,66,.3);background:rgba(255,255,255,.05)}
.card-top{display:flex;justify-content:space-between;align-items:start}
.card-top h3{margin:0 0 6px;font-size:17px;letter-spacing:-.02em;flex:1;min-width:0}
.card-delete{
  background:none;border:none;color:#687180;font-size:20px;cursor:pointer;
  padding:0 4px;line-height:1;transition:.2s;flex-shrink:0;
}
.card-delete:hover{color:#f87171}
.desc{margin:0 0 12px;color:#8e97a6;font-size:13px;font-style:italic}
.meta{display:flex;justify-content:space-between;color:#8e97a6;font-size:11px}
.prompt{margin:12px 0 0;color:#687180;font-size:11px;font-style:italic}
@media(max-width:480px){.grid{grid-template-columns:1fr}.heading{align-items:start;flex-direction:column}}
</style>
