import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../api/client', () => ({
  default: {
    get: vi.fn()
  }
}))

import client from '../api/client'
import { useAlbumArt } from '../shared/composables/useAlbumArt'

describe('useAlbumArt', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    const { cache } = useAlbumArt()
    Object.keys(cache).forEach(k => delete cache[k])
  })

  it('fetches album art from API', async () => {
    client.get.mockResolvedValue({ data: { album_art_url: 'https://example.com/art.jpg' } })
    const { fetchAlbumArt, getAlbumArt } = useAlbumArt()

    const song = { title: 'Test Song', artist: 'Test Artist' }
    await fetchAlbumArt(song)

    expect(getAlbumArt(song)).toBe('https://example.com/art.jpg')
    expect(client.get).toHaveBeenCalledWith('/songs/album-art', {
      params: { title: 'Test Song', artist: 'Test Artist' }
    })
  })

  it('returns null on API failure', async () => {
    client.get.mockRejectedValue(new Error('Network error'))
    const { fetchAlbumArt, getAlbumArt } = useAlbumArt()

    const song = { title: 'Fail Song', artist: 'Fail Artist' }
    await fetchAlbumArt(song)

    expect(getAlbumArt(song)).toBeNull()
  })

  it('caches results and does not re-fetch', async () => {
    client.get.mockResolvedValue({ data: { album_art_url: 'https://example.com/cached.jpg' } })
    const { fetchAlbumArt } = useAlbumArt()

    const song = { title: 'Cached Song', artist: 'Cached Artist' }
    await fetchAlbumArt(song)
    await fetchAlbumArt(song)

    expect(client.get).toHaveBeenCalledTimes(1)
  })

  it('returns gradient fallback for missing titles', () => {
    const { getArtFallback } = useAlbumArt()

    const gradient = getArtFallback('Some Title')
    expect(gradient).toContain('linear-gradient')
  })

  it('fetches batch of songs', async () => {
    client.get.mockResolvedValue({ data: { album_art_url: 'https://example.com/batch.jpg' } })
    const { fetchBatch } = useAlbumArt()

    const songs = [
      { title: 'Song 1', artist: 'Artist 1' },
      { title: 'Song 2', artist: 'Artist 2' }
    ]
    fetchBatch(songs)

    await new Promise(r => setTimeout(r, 10))

    expect(client.get).toHaveBeenCalledTimes(2)
  })

  it('returns null for song without title', async () => {
    const { fetchAlbumArt, getAlbumArt } = useAlbumArt()
    const result = await fetchAlbumArt({ artist: 'No Title' })
    expect(result).toBeNull()
  })
})
