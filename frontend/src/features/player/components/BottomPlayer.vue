<script setup>
import { computed, ref } from 'vue'
import { usePlayer } from '../../../shared/composables/usePlayer'

const { playerState, togglePlay, toggleMode, seek, toggleMute, closePlayer } = usePlayer()
const showVideo = ref(false)

function formatTime(s) {
  if (isNaN(s)) return '0:00'
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${sec < 10 ? '0' : ''}${sec}`
}

const spotifyLink = computed(() => {
  if (!playerState.currentTrack) return null
  if (playerState.currentTrack.spotify_url) return playerState.currentTrack.spotify_url
  if (playerState.currentTrack.spotify_id) return `https://open.spotify.com/track/${playerState.currentTrack.spotify_id}`
  return `https://open.spotify.com/search/${playerState.currentTrack.title} ${playerState.currentTrack.artist}`
})
</script>

<template>
  <div v-if="playerState.currentTrack" class="aurora-player">
    <!-- Progress -->
    <div v-if="playerState.mode === 'preview'" class="progress-track" @click="seek">
      <div class="progress-fill" :style="{ width: `${playerState.progress}%` }"></div>
      <div class="progress-glow" :style="{ width: `${playerState.progress}%` }"></div>
    </div>

    <!-- YouTube -->
    <div v-if="playerState.mode === 'full'" class="yt-wrap" :class="{ expanded: showVideo }">
      <div v-if="playerState.isLoadingYoutube" class="yt-loading">Finding stream...</div>
      <iframe
        v-if="playerState.youtubeVideoId"
        :src="`https://www.youtube.com/embed/${playerState.youtubeVideoId}?autoplay=1&enablejsapi=1&origin=http://localhost:5173`"
        :height="showVideo ? '200' : '60'"
        width="100%"
        frameborder="0"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowfullscreen
        class="yt-iframe"
      ></iframe>
    </div>

    <div class="container player-inner">
      <!-- Track Info -->
      <div class="track-info">
        <div class="art-wrap">
          <img v-if="playerState.currentTrack.album_art_url" :src="playerState.currentTrack.album_art_url" width="46" height="46" class="art" />
          <div v-else class="art-placeholder">♫</div>
          <div v-if="playerState.isPlaying" class="playing-bars">
            <span></span><span></span><span></span>
          </div>
        </div>
        <div class="track-text">
          <div class="track-name">{{ playerState.currentTrack.title }}</div>
          <div class="track-artist">{{ playerState.currentTrack.artist }}</div>
        </div>
      </div>

      <!-- Controls -->
      <div class="controls">
        <div class="flex-row" style="gap: 0.35rem;">
          <button :class="['btn btn-sm btn-pill', playerState.mode === 'preview' ? 'btn-primary' : 'btn-secondary']" @click="toggleMode('preview')">30s</button>
          <button :class="['btn btn-sm btn-pill', playerState.mode === 'full' ? 'btn-primary' : 'btn-secondary']" @click="toggleMode('full')">Full</button>
          <button v-if="playerState.mode === 'preview'" class="play-circle" @click="togglePlay">
            <svg v-if="!playerState.isPlaying" width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"/></svg>
          </button>
        </div>
        <div class="time-row">
          <span v-if="playerState.mode === 'preview'">{{ formatTime(playerState.currentTime) }} / {{ formatTime(playerState.duration) }}</span>
          <span v-else class="live-badge"><span class="live-dot"></span> Live</span>
        </div>
      </div>

      <!-- Actions -->
      <div class="actions">
        <button v-if="playerState.mode === 'full'" class="btn btn-sm btn-secondary" @click="showVideo = !showVideo">{{ showVideo ? 'Min' : 'Video' }}</button>
        <a v-if="spotifyLink" :href="spotifyLink" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-secondary spotify-link">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="#1DB954"><path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/></svg>
          Spotify
        </a>
        <button v-if="playerState.mode === 'preview'" class="icon-btn" @click="toggleMute">
          <svg v-if="!playerState.isMuted" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/></svg>
        </button>
        <button class="icon-btn" @click="closePlayer">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.aurora-player {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(8, 8, 15, 0.94);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border-top: 1px solid var(--border);
  z-index: 1000;
  box-shadow: 0 -4px 40px rgba(0, 0, 0, 0.6), 0 0 80px rgba(245, 158, 11, 0.03);
  animation: slideUp 0.3s var(--ease);
}

@keyframes slideUp {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}

.yt-wrap { max-width: 480px; margin: 0.5rem auto 0; padding: 0 1rem; }
.yt-loading { text-align: center; font-size: 0.8rem; color: var(--text-muted); padding: 0.5rem; }
.yt-iframe { border-radius: var(--r-md); }

.progress-track {
  width: 100%;
  height: 3px;
  background: rgba(255, 255, 255, 0.05);
  cursor: pointer;
  position: relative;
}

.progress-track:hover { height: 5px; }

.progress-fill {
  height: 100%;
  background: var(--amber);
  border-radius: 0 2px 2px 0;
  position: relative;
  z-index: 2;
}

.progress-glow {
  position: absolute;
  top: -3px;
  left: 0;
  height: 9px;
  background: var(--amber);
  opacity: 0.25;
  filter: blur(6px);
  z-index: 1;
}

.player-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.6rem 1.5rem;
  gap: 1rem;
}

.track-info {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  min-width: 180px;
  max-width: 260px;
}

.art-wrap { position: relative; flex-shrink: 0; }
.art { border-radius: var(--r-sm); box-shadow: var(--shadow-sm); }
.art-placeholder {
  width: 46px;
  height: 46px;
  border-radius: var(--r-sm);
  background: var(--amber-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.1rem;
}

.playing-bars {
  position: absolute;
  bottom: 2px;
  right: 2px;
  display: flex;
  gap: 1.5px;
  align-items: flex-end;
  height: 10px;
}

.playing-bars span {
  width: 2px;
  background: var(--amber);
  border-radius: 1px;
  animation: bars 0.6s ease-in-out infinite;
}

.playing-bars span:nth-child(1) { height: 3px; animation-delay: 0s; }
.playing-bars span:nth-child(2) { height: 7px; animation-delay: 0.15s; }
.playing-bars span:nth-child(3) { height: 5px; animation-delay: 0.3s; }

@keyframes bars {
  0%, 100% { height: 2px; }
  50% { height: 10px; }
}

.track-text { overflow: hidden; }
.track-name { font-weight: 700; font-size: 0.85rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.track-artist { font-size: 0.73rem; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.controls {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.2rem;
}

.play-circle {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: none;
  background: var(--amber);
  color: #0a0a0f;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s var(--ease);
  box-shadow: 0 2px 14px rgba(245, 158, 11, 0.4);
}

.play-circle:hover { transform: scale(1.1); box-shadow: 0 4px 24px rgba(245, 158, 11, 0.55); }

.time-row {
  font-size: 0.68rem;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.live-badge {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  color: var(--green);
  font-weight: 700;
}

.live-dot {
  width: 5px;
  height: 5px;
  background: var(--green);
  border-radius: 50%;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.actions {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.icon-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 0.35rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.icon-btn:hover { color: var(--text-primary); background: rgba(255,255,255,0.06); }

.spotify-link:hover { border-color: #1DB954 !important; }

@media (max-width: 768px) {
  .actions .spotify-link { display: none; }
  .player-inner { padding: 0.6rem 1rem; }
}
</style>
