<script setup>
import { ref, computed, onMounted } from 'vue'
import client from '../../../api/client'

const stats = ref(null)
const moodDistribution = ref(null)
const loading = ref(true)
const error = ref('')

const moodColors = {
  happy: '#fbbf24',
  chill: '#67e8f9',
  energetic: '#f87171',
  sad: '#c4b5fd',
  romantic: '#f472b6'
}

const moodLabels = {
  happy: 'Happy',
  chill: 'Chill',
  energetic: 'Energetic',
  sad: 'Sad',
  romantic: 'Romantic'
}

const totalMoodTracks = computed(() => {
  if (!moodDistribution.value) return 0
  return Object.values(moodDistribution.value).reduce((a, b) => a + b, 0)
})

const moodItems = computed(() => {
  if (!moodDistribution.value) return []
  return Object.entries(moodDistribution.value).map(([key, value]) => ({
    label: moodLabels[key] || key,
    value: Math.round((value / totalMoodTracks.value) * 100),
    color: moodColors[key] || '#78716c'
  }))
})

const donutStyle = computed(() => {
  let start = 0
  const stops = moodItems.value.map(m => {
    const a = start
    start += m.value * 3.6
    return `${m.color} ${a}deg ${start}deg`
  })
  return { background: `conic-gradient(${stops.join(',')})` }
})

const statCards = computed(() => {
  if (!stats.value) return []
  return [
    { icon: '♫', value: stats.value.total_songs, label: 'Total Songs' },
    { icon: '🥁', value: `${stats.value.avg_tempo_bpm} BPM`, label: 'Avg Tempo' },
    { icon: '⚡', value: `${stats.value.avg_energy_pct}%`, label: 'Avg Energy' }
  ]
})

async function fetchAnalytics() {
  loading.value = true
  try {
    const [s, m] = await Promise.all([
      client.get('/analytics/stats'),
      client.get('/analytics/mood-distribution')
    ])
    stats.value = s.data
    moodDistribution.value = m.data
  } catch {
    error.value = 'Failed to load analytics'
  } finally {
    loading.value = false
  }
}

onMounted(fetchAnalytics)
</script>

<template>
  <section class="page">
    <header class="heading">
      <div>
        <p class="eyebrow">LISTENING INSIGHTS</p>
        <h1>Your mood, measured.</h1>
        <p>See how your listening habits move with you.</p>
      </div>
    </header>

    <div v-if="loading" class="loading-block">
      <div class="spinner"></div>
      <p>Calculating stats...</p>
    </div>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <div v-if="stats && !loading">
      <div class="stats">
        <article v-for="stat in statCards" :key="stat.label" class="stat">
          <span class="stat-icon">{{ stat.icon }}</span>
          <div>
            <strong>{{ stat.value }}</strong>
            <p>{{ stat.label }}</p>
          </div>
        </article>
      </div>

      <div class="dashboard">
        <article class="panel distribution">
          <div class="panel-heading">
            <div>
              <p class="eyebrow">MOOD DISTRIBUTION</p>
              <h2>What you reach for</h2>
            </div>
            <span class="legend-total">{{ totalMoodTracks }} tracks</span>
          </div>
          <div v-if="moodItems.length" class="donut-wrap">
            <div class="donut" :style="donutStyle">
              <div>
                <strong>100%</strong>
                <span>your mix</span>
              </div>
            </div>
            <div class="legend">
              <div v-for="item in moodItems" :key="item.label">
                <i :style="{ background: item.color }"></i>
                <span>{{ item.label }}</span>
                <b>{{ item.value }}%</b>
              </div>
            </div>
          </div>
          <p v-else class="muted">No mood data yet. Start listening to see your distribution.</p>
        </article>

        <article class="panel recent">
          <div class="panel-heading">
            <div>
              <p class="eyebrow">TASTE PROFILE</p>
              <h2>Your listening fingerprint</h2>
            </div>
            <span class="muted">Based on your plays</span>
          </div>
          <div v-if="moodItems.length" class="taste-grid">
            <div v-for="item in moodItems" :key="item.label" class="taste-row">
              <span>{{ item.label }}</span>
              <div><i :style="{ width: `${item.value}%` }"></i></div>
              <b>{{ item.value }}%</b>
            </div>
          </div>
          <p v-else class="muted">Your taste profile will appear here once you've listened to some music.</p>
        </article>
      </div>
    </div>
  </section>
</template>

<style scoped>
.page{max-width:1180px;margin:auto}
.heading{display:flex;justify-content:space-between;align-items:end;margin-bottom:28px}
.eyebrow{margin:0 0 8px;color:#f5b942;font-size:10px;font-weight:800;letter-spacing:.14em}
.heading h1{margin:0;font-size:clamp(30px,5vw,44px);letter-spacing:-.055em}
.heading p:not(.eyebrow){margin:10px 0 0;color:#8e97a6;font-size:14px}
.loading-block{display:flex;flex-direction:column;align-items:center;gap:12px;padding:70px 0}
.spinner{width:28px;height:28px;border:2.5px solid rgba(255,255,255,.08);border-top-color:#f5b942;border-radius:50%;animation:spin .7s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.loading-block p{color:#8e97a6;font-size:13px}
.error-banner{margin:0 0 16px;padding:10px 14px;border:1px solid rgba(248,113,113,.3);border-radius:10px;background:rgba(248,113,113,.08);color:#f87171;font-size:12px}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.stat{display:flex;align-items:center;gap:14px;padding:19px;border:1px solid rgba(245,185,66,.22);border-radius:12px;background:linear-gradient(135deg,rgba(255,255,255,.05),rgba(245,185,66,.04))}
.stat-icon{width:38px;height:38px;display:grid;place-items:center;border-radius:10px;background:rgba(245,185,66,.13);color:#f5b942;font-size:20px}
.stat strong{font-size:25px;letter-spacing:-.04em}
.stat p{margin:4px 0 0;color:#8e97a6;font-size:11px}
.dashboard{display:grid;grid-template-columns:1.1fr .9fr;gap:16px;margin-top:16px}
.panel{padding:22px;border:1px solid rgba(255,255,255,.08);border-radius:12px;background:rgba(255,255,255,.035)}
.panel-heading{display:flex;align-items:start;justify-content:space-between;gap:14px}
.panel-heading h2{margin:0;font-size:20px;letter-spacing:-.03em}
.legend-total,.muted{color:#8e97a6;font-size:11px}
.donut-wrap{display:flex;align-items:center;justify-content:center;gap:35px;margin-top:28px}
.donut{width:170px;height:170px;display:grid;place-items:center;border-radius:50%;position:relative}
.donut:after{content:'';position:absolute;width:112px;height:112px;border-radius:50%;background:#15191e}
.donut>div{position:relative;z-index:1;display:flex;flex-direction:column;align-items:center}
.donut strong{font-size:24px}
.donut span{color:#8e97a6;font-size:10px}
.legend{min-width:145px}
.legend div{display:grid;grid-template-columns:10px 1fr 35px;align-items:center;gap:8px;margin:12px 0;font-size:11px}
.legend i{width:8px;height:8px;border-radius:50%}
.legend span{color:#8e97a6}
.legend b{font-size:10px;text-align:right}
.taste-grid{display:grid;grid-template-columns:repeat(2,1fr);column-gap:40px;margin-top:20px}
.taste-row{display:grid;grid-template-columns:76px 1fr 35px;align-items:center;gap:10px;margin:12px 0;font-size:11px;color:#8e97a6}
.taste-row>div{height:6px;overflow:hidden;border-radius:99px;background:rgba(255,255,255,.08)}
.taste-row i{display:block;height:100%;border-radius:inherit;background:#f5b942}
.taste-row b{font-size:10px;text-align:right;color:#f4f5f7}
@media(max-width:760px){.stats{grid-template-columns:1fr}.dashboard{grid-template-columns:1fr}.donut-wrap{gap:15px}.taste-grid{grid-template-columns:1fr}}
@media(max-width:460px){.heading{align-items:start;flex-direction:column}.donut-wrap{justify-content:space-between}.donut{width:140px;height:140px}.donut:after{width:92px;height:92px}}
</style>
