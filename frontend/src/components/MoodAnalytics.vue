<script setup>
import { ref, onMounted } from 'vue'
import { Doughnut } from 'vue-chartjs'
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js'
import client from '../api/client'

ChartJS.register(ArcElement, Tooltip, Legend)

const stats = ref(null)
const moodData = ref(null)
const loading = ref(true)
const error = ref('')

const moodColors = {
  happy: '#fbbf24',
  chill: '#67e8f9',
  energetic: '#f87171',
  sad: '#c4b5fd',
  romantic: '#f472b6'
}

async function fetchAnalytics() {
  loading.value = true
  try {
    const [s, m] = await Promise.all([client.get('/analytics/stats'), client.get('/analytics/mood-distribution')])
    stats.value = s.data
    const moods = m.data
    const labels = Object.keys(moods)
    const values = Object.values(moods)
    const colors = labels.map(k => moodColors[k] || '#78716c')
    moodData.value = {
      labels: labels.map(l => l.charAt(0).toUpperCase() + l.slice(1)),
      datasets: [{ data: values, backgroundColor: colors, borderWidth: 0, hoverBorderWidth: 2, hoverBorderColor: 'rgba(255,255,255,0.2)', spacing: 2 }]
    }
  } catch { error.value = 'Failed to load analytics' }
  finally { loading.value = false }
}

const chartOpts = {
  responsive: true,
  maintainAspectRatio: true,
  cutout: '74%',
  plugins: {
    legend: {
      position: 'bottom',
      labels: { color: '#9a8f82', padding: 14, usePointStyle: true, pointStyleWidth: 8, font: { family: "'Inter',sans-serif", size: 11, weight: '500' } }
    },
    tooltip: {
      backgroundColor: 'rgba(18,18,32,0.95)',
      borderColor: 'rgba(255,255,255,0.06)',
      borderWidth: 1,
      titleFont: { family: "'Inter',sans-serif", weight: '600' },
      bodyFont: { family: "'Inter',sans-serif" },
      padding: 10,
      cornerRadius: 8
    }
  }
}

onMounted(fetchAnalytics)
</script>

<template>
  <div>
    <div v-if="loading" class="loading-block"><div class="spinner"></div><p class="text-muted">Calculating stats...</p></div>
    <div v-if="error" class="alert-error mb-4">{{ error }}</div>

    <div v-if="stats && !loading" class="animate-in">
      <div class="stats-grid mb-4">
        <div class="stat-card">
          <div class="stat-ico stat-ico-1">♫</div>
          <div>
            <span class="stat-label">Total Songs</span>
            <h3 class="stat-val">{{ stats.total_songs }}</h3>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-ico stat-ico-2">🥁</div>
          <div>
            <span class="stat-label">Avg Tempo</span>
            <h3 class="stat-val">{{ stats.avg_tempo_bpm }} <span class="stat-unit">BPM</span></h3>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-ico stat-ico-3">⚡</div>
          <div>
            <span class="stat-label">Avg Energy</span>
            <h3 class="stat-val">{{ stats.avg_energy_pct }}<span class="stat-unit">%</span></h3>
          </div>
        </div>
      </div>

      <div v-if="moodData" class="chart-card">
        <h4 class="chart-title">Mood Distribution</h4>
        <div class="chart-wrap">
          <Doughnut :data="moodData" :options="chartOpts" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.loading-block {
  text-align: center;
  padding: 4rem;
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

.stat-card {
  background: var(--bg-overlay);
  backdrop-filter: blur(16px);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  padding: 1.25rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  transition: all 0.3s var(--ease);
}

.stat-card:hover {
  border-color: var(--border-hover);
  transform: translateY(-2px);
  box-shadow: var(--shadow-md), var(--shadow-glow);
}

.stat-ico {
  width: 46px;
  height: 46px;
  border-radius: var(--r-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.2rem;
  flex-shrink: 0;
}

.stat-ico-1 { background: var(--amber-soft); }
.stat-ico-2 { background: var(--mood-chill-soft); }
.stat-ico-3 { background: var(--mood-happy-soft); }

.stat-label {
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
}

.stat-val {
  font-size: 1.8rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  margin-top: 0.1rem;
}

.stat-unit {
  font-size: 0.85rem;
  font-weight: 500;
  opacity: 0.45;
}

.chart-card {
  background: var(--bg-overlay);
  backdrop-filter: blur(16px);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  padding: 1.5rem;
}

.chart-title {
  font-size: 1rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin-bottom: 1rem;
}

.chart-wrap {
  max-width: 340px;
  margin: 0 auto;
}
</style>