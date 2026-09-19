import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockAudio } = vi.hoisted(() => {
  const mockAudio = {
    play: vi.fn().mockResolvedValue(undefined),
    pause: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    volume: 0.8,
    muted: false,
    src: '',
    currentTime: 0,
    duration: 30,
  }
  global.Audio = vi.fn(function () { return mockAudio })
  return { mockAudio }
})

vi.mock('../api/client', () => ({
  default: {
    get: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn().mockResolvedValue({ data: { status: 'ok' } })
  }
}))

import { usePlayer } from '../shared/composables/usePlayer'

describe('usePlayer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockAudio.play.mockResolvedValue(undefined)
    mockAudio.src = ''
    mockAudio.currentTime = 0
    mockAudio.duration = 30
    mockAudio.volume = 0.8
    mockAudio.muted = false
    const { closePlayer } = usePlayer()
    closePlayer()
  })

  it('has initial state', () => {
    const { playerState } = usePlayer()
    expect(playerState.currentTrack).toBeNull()
    expect(playerState.isPlaying).toBe(false)
    expect(playerState.mode).toBe('preview')
    expect(playerState.volume).toBe(0.8)
  })

  it('togglePlay pauses when playing', () => {
    const { playerState, togglePlay } = usePlayer()
    playerState.currentTrack = { id: 1, title: 'Test', artist: 'Artist', preview_url: 'http://test.mp3' }
    playerState.isPlaying = true

    togglePlay()
    expect(mockAudio.pause).toHaveBeenCalled()
  })

  it('toggleMute toggles mute state', () => {
    const { playerState, toggleMute } = usePlayer()
    expect(playerState.isMuted).toBe(false)

    toggleMute()
    expect(playerState.isMuted).toBe(true)
    expect(mockAudio.muted).toBe(true)
  })

  it('setVolume updates state and audio', () => {
    const { playerState, setVolume } = usePlayer()
    setVolume(0.5)
    expect(playerState.volume).toBe(0.5)
    expect(mockAudio.volume).toBe(0.5)
  })

  it('closePlayer resets state', () => {
    const { playerState, closePlayer } = usePlayer()
    playerState.currentTrack = { id: 1, title: 'Test' }
    playerState.isPlaying = true

    closePlayer()
    expect(playerState.currentTrack).toBeNull()
    expect(playerState.isPlaying).toBe(false)
  })

  it('playTrack sets current track and mode', async () => {
    const { playerState, playTrack } = usePlayer()
    const track = { id: 10, title: 'Play Me', artist: 'Artist', preview_url: 'http://test.mp3' }

    await playTrack(track)

    expect(playerState.currentTrack).toEqual(track)
    expect(playerState.mode).toBe('preview')
    expect(playerState.isPlaying).toBe(true)
    expect(mockAudio.src).toBe('http://test.mp3')
  })

  it('skipTrack pauses and resets progress', () => {
    const { playerState, skipTrack } = usePlayer()
    playerState.currentTrack = { id: 1, title: 'Test' }
    playerState.isPlaying = true
    playerState.currentTime = 15
    playerState.progress = 50

    skipTrack()
    expect(mockAudio.pause).toHaveBeenCalled()
    expect(playerState.isPlaying).toBe(false)
    expect(playerState.currentTime).toBe(0)
    expect(playerState.progress).toBe(0)
  })
})
