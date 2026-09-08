<template>
  <section v-if="track" class="player" aria-label="Now playing">
    <div class="player-inner">
      <div class="track-info">
        <button
          class="art-button"
          type="button"
          aria-label="Open track details"
        >
          <img
            v-if="track.album_art || track.artwork || track.cover"
            :src="track.album_art || track.artwork || track.cover"
            :alt="`${track.title || 'Track'} artwork`"
          />

          <span v-else class="art-fallback" aria-hidden="true">
            {{ track.title?.charAt(0) || 'M' }}
          </span>

          <span class="art-overlay" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path d="m9 6 8 6-8 6V6Z" />
            </svg>
          </span>
        </button>

        <div class="track-copy">
          <strong>{{ track.title || 'Untitled track' }}</strong>
          <span>{{ track.artist || 'Unknown artist' }}</span>
        </div>
      </div>

      <div class="transport">
        <div class="transport-buttons">
          <button
            class="control-button"
            type="button"
            aria-label="Previous track"
            @click="emit('previous')"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="m19 5-9 7 9 7V5ZM5 5v14" />
            </svg>
          </button>

          <button
            class="play-button"
            type="button"
            :aria-label="isPlaying ? 'Pause' : 'Play'"
            @click="emit('toggle-play')"
          >
            <svg v-if="isPlaying" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M8 5v14M16 5v14" />
            </svg>

            <svg v-else viewBox="0 0 24 24" aria-hidden="true">
              <path d="m9 5 10 7-10 7V5Z" />
            </svg>
          </button>

          <button
            class="control-button"
            type="button"
            aria-label="Next track"
            @click="emit('next')"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="m5 5 9 7-9 7V5Zm14 0v14" />
            </svg>
          </button>
        </div>

        <div class="progress-row">
          <time>{{ formatTime(currentTime) }}</time>

          <input
            class="progress"
            type="range"
            min="0"
            max="100"
            :value="progress"
            aria-label="Track progress"
            @input="emit('seek', Number($event.target.value))"
          />

          <time>{{ formatTime(duration) }}</time>
        </div>
      </div>

      <div class="player-actions">
        <button
          class="control-button volume-button"
          type="button"
          :aria-label="muted ? 'Unmute' : 'Mute'"
          @click="emit('toggle-mute')"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 10v4h4l5 4V6l-5 4H4Zm12.5-2a5.5 5.5 0 0 1 0 8M16 5a9 9 0 0 1 0 14" />
          </svg>
        </button>

        <input
          class="volume"
          type="range"
          min="0"
          max="100"
          :value="muted ? 0 : Math.round(volume * 100)"
          aria-label="Volume"
          @input="emit('update:volume', Number($event.target.value) / 100)"
        />

        <button
          class="control-button close-button"
          type="button"
          aria-label="Close player"
          @click="emit('close')"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="m6 6 12 12M18 6 6 18" />
          </svg>
        </button>
      </div>
    </div>
  </section>
</template>

<script setup>
const props = defineProps({
  track: { type: Object, default: null },
  isPlaying: { type: Boolean, default: false },
  progress: { type: Number, default: 0 },
  duration: { type: Number, default: 30 },
  currentTime: { type: Number, default: 0 },
  volume: { type: Number, default: 0.8 },
  muted: { type: Boolean, default: false }
})

const emit = defineEmits([
  'toggle-play',
  'previous',
  'next',
  'seek',
  'toggle-mute',
  'close',
  'update:volume'
])

const formatTime = (seconds) => {
  const value = Number(seconds) || 0
  return `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, '0')}`
}
</script>

<style scoped>
.player {
  position: fixed;
  z-index: 40;
  right: 0;
  bottom: 0;
  left: 0;
  padding: 12px 22px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.11);
  background: rgba(17, 20, 25, 0.84);
  box-shadow: 0 -18px 55px rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
}

.player-inner {
  max-width: 1440px;
  min-height: 64px;
  margin: auto;
  display: grid;
  grid-template-columns:
    minmax(220px, 1fr)
    minmax(300px, 1.25fr)
    minmax(220px, 1fr);
  align-items: center;
  gap: 26px;
}

.track-info {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 12px;
}

.art-button {
  position: relative;
  width: 52px;
  height: 52px;
  flex: none;
  padding: 0;
  overflow: hidden;
  border: 0;
  border-radius: 10px;
  background: linear-gradient(145deg, #424d5d, #d18b41);
  color: #fff;
  cursor: pointer;
}

.art-button img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}

.art-fallback {
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  font-size: 20px;
  font-weight: 800;
}

.art-overlay {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: rgba(0, 0, 0, 0.45);
  opacity: 0;
  transition: opacity 0.2s;
}

.art-button:hover .art-overlay {
  opacity: 1;
}

.art-overlay svg {
  width: 20px;
  fill: #fff;
  stroke: none;
}

.track-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.track-copy strong,
.track-copy span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.track-copy strong {
  color: #f4f5f7;
  font-size: 13px;
  font-weight: 650;
}

.track-copy span {
  color: #8e97a6;
  font-size: 11px;
}

.control-button {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: #8e97a6;
  cursor: pointer;
  transition: 0.2s ease;
}

.control-button:hover {
  color: #f4f5f7;
  background: rgba(255, 255, 255, 0.07);
}

.control-button svg,
.play-button svg {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.transport {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.transport-buttons {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.play-button {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border: 0;
  border-radius: 50%;
  background: #f5b942;
  color: #17191d;
  cursor: pointer;
  transition: transform 0.2s, background 0.2s;
}

.play-button:hover {
  background: #ffd36d;
  transform: scale(1.06);
}

.play-button svg {
  width: 17px;
  height: 17px;
  stroke-width: 2.1;
}

.progress-row {
  display: flex;
  align-items: center;
  gap: 9px;
  color: #77808e;
  font-size: 10px;
}

.progress,
.volume {
  height: 4px;
  flex: 1;
  accent-color: #f5b942;
  cursor: pointer;
}

.player-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 7px;
}

.volume {
  max-width: 90px;
}

@media (max-width: 760px) {
  .player {
    padding: 10px 14px 13px;
  }

  .player-inner {
    display: flex;
    flex-wrap: wrap;
    gap: 10px 14px;
  }

  .track-info {
    width: 100%;
  }

  .transport {
    min-width: 185px;
    flex: 1;
  }

  .player-actions {
    flex: 0 0 auto;
  }

  .volume-button,
  .volume {
    display: none;
  }
}

@media (max-width: 420px) {
  .progress-row {
    gap: 5px;
  }

  .player-actions {
    display: none;
  }

  .transport {
    width: 100%;
  }
}
</style>
