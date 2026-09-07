<template>
  <div class="empty-state">
    <div class="empty-icon">{{ icon }}</div>
    <p class="empty-text">{{ message }}</p>
    <slot />
  </div>
</template>

<script setup>
defineProps({
  icon: { type: String, default: '♫' },
  message: { type: String, default: 'Nothing here yet.' }
})
</script>

<style scoped>
.empty-state {
  text-align: center;
  padding: 4rem 1rem;
}
.empty-icon {
  font-size: 2.5rem;
  opacity: 0.3;
  margin-bottom: 0.75rem;
}
.empty-text {
  color: #9a8f82;
  font-weight: 500;
  font-size: 0.88rem;
}
</style>
