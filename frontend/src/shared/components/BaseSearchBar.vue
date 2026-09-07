<template>
  <div class="search-bar">
    <svg class="search-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>
    <input
      :value="modelValue"
      @input="$emit('update:modelValue', $event.target.value)"
      @keyup.enter="$emit('search')"
      type="text"
      :placeholder="placeholder"
      class="search-input"
    />
    <button v-if="modelValue" class="search-clear" @click="$emit('update:modelValue', '')">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
      </svg>
    </button>
  </div>
</template>

<script setup>
defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: 'Search...' }
})
defineEmits(['update:modelValue', 'search'])
</script>

<style scoped>
.search-bar {
  position: relative;
  flex: 1;
}
.search-icon {
  position: absolute;
  left: 0.8rem;
  top: 50%;
  transform: translateY(-50%);
  color: #5c554b;
  pointer-events: none;
}
.search-input {
  width: 100%;
  padding: 0.6rem 2.2rem 0.6rem 2.4rem;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 10px;
  color: #faf5ef;
  font-family: 'Inter', -apple-system, sans-serif;
  font-size: 0.84rem;
  outline: none;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.search-input::placeholder { color: #5c554b; }
.search-input:focus {
  background: rgba(255,255,255,0.06);
  border-color: #f59e0b;
  box-shadow: 0 0 0 3px rgba(245,158,11,0.12);
}
.search-clear {
  position: absolute;
  right: 0.5rem;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: #5c554b;
  cursor: pointer;
  padding: 0.2rem;
  border-radius: 50%;
  display: flex;
  transition: color 0.15s;
}
.search-clear:hover { color: #9a8f82; }
</style>
