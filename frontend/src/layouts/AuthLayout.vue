<template>
  <div class="auth-layout">
    <div class="auth-glow"></div>
    <div class="auth-card">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </div>
  </div>
</template>

<style scoped>
.auth-layout {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  position: relative;
  overflow: hidden;
}
.auth-glow {
  position: absolute;
  top: -40%;
  left: 50%;
  transform: translateX(-50%);
  width: 80%;
  height: 80%;
  background: radial-gradient(ellipse, rgba(245,158,11,0.06) 0%, transparent 60%);
  pointer-events: none;
}
.auth-card {
  width: 100%;
  max-width: 400px;
  position: relative;
  z-index: 1;
}
.page-enter-active, .page-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}
.page-enter-from { opacity: 0; transform: translateY(6px); }
.page-leave-to { opacity: 0; transform: translateY(-6px); }
</style>
