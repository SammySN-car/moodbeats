<template>
  <div class="spinner-wrap">
    <div class="spinner"></div>
    <p v-if="label" class="spinner-label">{{ label }}</p>
  </div>
</template>

<script setup>
defineProps({
  label: { type: String, default: '' }
})
</script>

<style scoped>
.spinner-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  padding: 3rem;
  text-align: center;
}
.spinner {
  width: 28px;
  height: 28px;
  border: 2.5px solid rgba(255,255,255,0.06);
  border-top-color: #f59e0b;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
.spinner-label { color: #5c554b; font-size: 0.82rem; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
