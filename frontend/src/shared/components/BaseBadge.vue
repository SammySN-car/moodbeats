<template>
  <span :class="['badge', `badge-${mood}`]">{{ mood }}</span>
</template>

<script setup>
defineProps({
  mood: { type: String, default: 'neutral' }
})
</script>

<style scoped>
.badge {
  display: inline-flex;
  align-items: center;
  padding: 0.2rem 0.6rem;
  border-radius: 9999px;
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.badge-happy { background: rgba(251,191,36,0.12); color: #fbbf24; }
.badge-chill { background: rgba(103,232,249,0.12); color: #67e8f9; }
.badge-sad { background: rgba(196,181,253,0.12); color: #c4b5fd; }
.badge-energetic { background: rgba(248,113,113,0.12); color: #f87171; }
.badge-romantic { background: rgba(244,114,182,0.12); color: #f472b6; }
.badge-neutral { background: rgba(120,113,108,0.12); color: #78716c; }
</style>
