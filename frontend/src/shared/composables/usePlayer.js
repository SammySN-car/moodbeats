import { reactive } from 'vue'
import client from '../../api/client'

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
  isLoadingYoutube: false,
  queue: [],
  queueIndex: -1
})

audio.volume = playerState.volume

// --- Feedback Loop: track play start time for skip detection ---
let playStartedAt = null
let lastEventSongId = null

/**
 * Send a listening event to the backend.
 * Fires and forgets -- we don't block the UI on analytics.
 */
async function sendListeningEvent(songId, eventType, durationListened = 0) {
  try {
    await client.post('/listening/event', {
      song_id: songId,
      event_type: eventType,
      duration_listened: durationListened
    })
  } catch (err) {
    // Silently fail -- analytics should never break playback
    console.warn('[Feedback] Event failed:', err.message)
  }
}

/**
 * Determine if the user listened long enough to count as a "play".
 * If they skip before 30% of the track, it's a skip.
 */
function getEffectiveDuration() {
  if (!playStartedAt) return 0
  return (Date.now() - playStartedAt) / 1000
}

audio.addEventListener('timeupdate', () => {
  playerState.currentTime = audio.currentTime
  playerState.duration = audio.duration || 30
  playerState.progress = (audio.currentTime / (audio.duration || 30)) * 100
})

audio.addEventListener('play', () => {
  playerState.isPlaying = true
  // Record when play started for skip detection
  if (!playStartedAt) {
    playStartedAt = Date.now()
  }
})

audio.addEventListener('pause', () => {
  playerState.isPlaying = false
})

export function usePlayer() {
  // Auto-play next track when current ends (only register once)
  if (!audio._autoPlayRegistered) {
    audio._autoPlayRegistered = true
    audio.addEventListener('ended', () => {
      // Send play event for the completed track
      if (playerState.currentTrack?.id && lastEventSongId !== playerState.currentTrack.id) {
        const duration = getEffectiveDuration()
        sendListeningEvent(playerState.currentTrack.id, 'play', duration)
        lastEventSongId = playerState.currentTrack.id
      }
      playStartedAt = null
      playerState.isPlaying = false
      playerState.currentTime = 0
      playerState.progress = 0

      // Advance to next in queue
      if (playerState.queue.length > 0) {
        nextInQueue()
      }
    })
  }

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

    // --- Send skip event for the previous track if it was playing ---
    if (playerState.currentTrack?.id && lastEventSongId !== playerState.currentTrack.id) {
      const duration = getEffectiveDuration()
      if (duration > 1) {
        sendListeningEvent(playerState.currentTrack.id, 'skip', duration)
      }
    }

    // Reset tracking for the new track
    lastEventSongId = null
    playStartedAt = null

    playerState.currentTrack = track
    // Update queue index if track is in queue
    const qIdx = playerState.queue.findIndex(t => t.id === track.id)
    if (qIdx !== -1) playerState.queueIndex = qIdx
    playerState.mode = mode
    playerState.currentTime = 0
    playerState.progress = 0

    if (mode === 'preview') {
      let previewUrl = track.preview_url
      
      // Fetch from iTunes on-demand if preview_url is missing
      if (!previewUrl) {
        try {
          const res = await client.get('/songs/preview-url', {
            params: { title: track.title, artist: track.artist || '' }
          })
          previewUrl = res.data?.preview_url
        } catch (e) {
          console.warn('Could not fetch preview URL:', e)
        }
      }
      
      if (previewUrl) {
        audio.src = previewUrl
        audio.play().catch(e => console.warn('Preview playback error:', e))
        playerState.isPlaying = true
        playStartedAt = Date.now()
        sendListeningEvent(track.id, 'play', 0)
        lastEventSongId = track.id
      } else {
        // Fallback to full YouTube mode if no preview available
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

    // Send play event for full mode too
    playStartedAt = Date.now()
    sendListeningEvent(track.id, 'play', 0)
    lastEventSongId = track.id

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

  /**
   * Skip to the next track -- sends a skip event with duration listened.
   */
  function skipTrack() {
    if (!playerState.currentTrack) return
    const duration = getEffectiveDuration()
    if (duration > 1 && playerState.currentTrack.id) {
      sendListeningEvent(playerState.currentTrack.id, 'skip', duration)
    }
    lastEventSongId = null
    playStartedAt = null
    audio.pause()
    audio.currentTime = 0
    playerState.isPlaying = false
    playerState.currentTime = 0
    playerState.progress = 0
    nextInQueue()
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
    // Send skip event if track was playing
    if (playerState.currentTrack?.id && lastEventSongId !== playerState.currentTrack.id) {
      const duration = getEffectiveDuration()
      if (duration > 1) {
        sendListeningEvent(playerState.currentTrack.id, 'skip', duration)
      }
    }
    lastEventSongId = null
    playStartedAt = null
    audio.pause()
    playerState.isPlaying = false
    playerState.currentTrack = null
    playerState.youtubeVideoId = null
  }

  function setQueue(tracks, startIndex = 0) {
    playerState.queue = tracks
    playerState.queueIndex = startIndex
  }

  function nextInQueue() {
    if (playerState.queue.length === 0) return
    const nextIdx = playerState.queueIndex + 1
    if (nextIdx < playerState.queue.length) {
      playerState.queueIndex = nextIdx
      playTrack(playerState.queue[nextIdx], playerState.mode)
    }
  }

  function prevInQueue() {
    if (playerState.queue.length === 0) return
    const prevIdx = playerState.queueIndex - 1
    if (prevIdx >= 0) {
      playerState.queueIndex = prevIdx
      playTrack(playerState.queue[prevIdx], playerState.mode)
    }
  }

  /**
   * Save/unsave the current track.
   */
  async function toggleSave(track) {
    if (!track?.id) return
    try {
      const res = await client.post('/listening/event', {
        song_id: track.id,
        event_type: 'save',
        duration_listened: 0
      })
      return res.data
    } catch (err) {
      console.warn('[Feedback] Save event failed:', err.message)
    }
  }

  return {
    playerState,
    playTrack,
    playFullTrack,
    skipTrack,
    toggleMode,
    togglePlay,
    seek,
    toggleMute,
    closePlayer,
    toggleSave,
    sendListeningEvent,
    setQueue,
    nextInQueue,
    prevInQueue
  }
}

