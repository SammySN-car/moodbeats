<script setup>
import { ref, computed } from 'vue'
import ImportSong from '../components/ImportSong.vue'
import SongLibrary from '../components/SongLibrary.vue'
import MoodDiscover from '../components/MoodDiscover.vue'
import MoodAnalytics from '../components/MoodAnalytics.vue'

const activeTab = ref('discover')

const tabs = [
  { key: 'discover', label: 'Discover', icon: '✦' },
  { key: 'library', label: 'Library', icon: '♫' },
  { key: 'import', label: 'Import', icon: '⊕' },
  { key: 'analytics', label: 'Analytics', icon: '◎' }
]

const componentMap = {
  discover: MoodDiscover,
  library: SongLibrary,
  import: ImportSong,
  analytics: MoodAnalytics
}

const activeComponent = computed(() => componentMap[activeTab.value])
</script>

<template>
  <div class="animate-in">
    <nav class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="['tab-btn', { active: activeTab === tab.key }]"
        @click="activeTab = tab.key"
      >
        <span class="tab-icon">{{ tab.icon }}</span>
        {{ tab.label }}
      </button>
    </nav>

    <transition name="view" mode="out-in">
      <component :is="activeComponent" :key="activeTab" />
    </transition>
  </div>
</template>

<style scoped>
.tab-icon { font-size: 0.85rem; }

.view-enter-active, .view-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}
.view-enter-from { opacity: 0; transform: translateY(4px); }
.view-leave-to { opacity: 0; transform: translateY(-4px); }
</style>