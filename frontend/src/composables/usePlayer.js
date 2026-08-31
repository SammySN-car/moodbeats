import { reactive } from 'vue'
import client from '../api/client'

const audio = new Audio()

const playerState = reactive({
  currentTrack: null,
  mode: 'preview', // 'preview' (30s) or 'full' (YouTube Stream)
  isPlaying: false,
  currentTime: 0,
  duration: 30,
  progress: 0,
  volume: 0.8,
  isMuted: false,
  youtubeVideoId: null,
  isLoadingYoutube: false
})

audio.volume = playerState.volume

audio.addEventListener('timeupdate', () => {
  playerState.currentTime = audio.currentTime
  playerState.duration = audio.duration || 30
  playerState.progress = (audio.currentTime / (audio.duration || 30)) * 100
})

audio.addEventListener('ended', () => {
  playerState.isPlaying = false
  playerState.currentTime = 0
  playerState.progress = 0
})

audio.addEventListener('play', () => {
  playerState.isPlaying = true
})

audio.addEventListener('pause', () => {
  playerState.isPlaying = false
})

export function usePlayer() {
  async function playTrack(track, mode = 'preview') {
    if (!track) return

    // If clicking same track with same mode, toggle play/pause
    if (
      playerState.currentTrack?.title === track.title &&
      playerState.currentTrack?.artist === track.artist &&
      playerState.mode === mode
    ) {
      togglePlay()
      return
    }

    playerState.currentTrack = track
    playerState.mode = mode
    playerState.currentTime = 0
    playerState.progress = 0

    if (mode === 'preview') {
      if (track.preview_url) {
        audio.src = track.preview_url
        audio.play().catch(e => console.warn('Preview playback error:', e))
        playerState.isPlaying = true
      } else {
        // Fallback to full YouTube mode if preview is missing
        await playFullTrack(track)
      }
    } else {
      await playFullTrack(track)
    }
  }

  async function playFullTrack(track) {
    if (!track) return
    playerState.currentTrack = track
    playerState.mode = 'full'
    playerState.isPlaying = true
    playerState.isLoadingYoutube = true
    audio.pause()

    try {
      const res = await client.get('/songs/youtube-id', {
        params: { title: track.title, artist: track.artist || '' }
      })
      if (res.data?.video_id) {
        playerState.youtubeVideoId = res.data.video_id
      }
    } catch (err) {
      console.warn('Could not fetch YouTube ID:', err)
    } finally {
      playerState.isLoadingYoutube = false
    }
  }

  function toggleMode(newMode) {
    if (!playerState.currentTrack) return
    playTrack(playerState.currentTrack, newMode)
  }

  function togglePlay() {
    if (!playerState.currentTrack) return
    if (playerState.mode === 'preview') {
      if (playerState.isPlaying) {
        audio.pause()
      } else {
        if (audio.src) {
          audio.play().catch(e => console.warn('Play error:', e))
        }
      }
    } else {
      playerState.isPlaying = !playerState.isPlaying
    }
  }

  function seek(e) {
    if (playerState.mode !== 'preview') return
    const rect = e.currentTarget.getBoundingClientRect()
    const pos = (e.clientX - rect.left) / rect.width
    const newTime = pos * (audio.duration || 30)
    audio.currentTime = newTime
    playerState.currentTime = newTime
  }

  function toggleMute() {
    playerState.isMuted = !playerState.isMuted
    audio.muted = playerState.isMuted
  }

  function closePlayer() {
    audio.pause()
    playerState.isPlaying = false
    playerState.currentTrack = null
    playerState.youtubeVideoId = null
  }

  return {
    playerState,
    playTrack,
    playFullTrack,
    toggleMode,
    togglePlay,
    seek,
    toggleMute,
    closePlayer
  }
}
