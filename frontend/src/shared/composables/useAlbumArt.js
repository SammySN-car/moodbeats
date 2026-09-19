import { reactive } from 'vue'
import client from '../../api/client'

const cache = reactive({})

const gradients = [
  'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
  'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
  'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
  'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
  'linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%)',
  'linear-gradient(135deg, #fccb90 0%, #d57eeb 100%)',
  'linear-gradient(135deg, #e0c3fc 0%, #8ec5fc 100%)',
  'linear-gradient(135deg, #f5576c 0%, #ff6a88 100%)',
  'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
]

function getArtGradient(title) {
  if (!title) return gradients[0]
  let hash = 0
  for (let i = 0; i < title.length; i++) {
    hash = title.charCodeAt(i) + ((hash << 5) - hash)
  }
  return gradients[Math.abs(hash) % gradients.length]
}

function getCacheKey(song) {
  return `${song.title}__${song.artist || ''}`
}

export function useAlbumArt() {
  async function fetchAlbumArt(song) {
    if (!song?.title) return null
    const key = getCacheKey(song)
    if (cache[key] !== undefined) return cache[key]
    cache[key] = null
    try {
      const res = await client.get('/songs/album-art', {
        params: { title: song.title, artist: song.artist || '' }
      })
      cache[key] = res.data?.album_art_url || null
    } catch {
      cache[key] = null
    }
    return cache[key]
  }

  function getAlbumArt(song) {
    if (!song?.title) return null
    return cache[getCacheKey(song)]
  }

  function getArtFallback(title) {
    return getArtGradient(title)
  }

  function fetchBatch(songs) {
    songs.forEach(s => fetchAlbumArt(s))
  }

  return { fetchAlbumArt, getAlbumArt, getArtFallback, fetchBatch, cache }
}
