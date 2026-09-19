import { describe, it, expect } from 'vitest'

function formatDuration(sec) {
  if (sec === null || sec === undefined) return ''
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

describe('formatDuration', () => {
  it('formats 0 seconds', () => {
    expect(formatDuration(0)).toBe('0:00')
  })

  it('formats 30 seconds', () => {
    expect(formatDuration(30)).toBe('0:30')
  })

  it('formats 60 seconds', () => {
    expect(formatDuration(60)).toBe('1:00')
  })

  it('formats 180 seconds', () => {
    expect(formatDuration(180)).toBe('3:00')
  })

  it('formats 90 seconds', () => {
    expect(formatDuration(90)).toBe('1:30')
  })

  it('returns empty string for null/undefined', () => {
    expect(formatDuration(null)).toBe('')
    expect(formatDuration(undefined)).toBe('')
  })

  it('handles decimal seconds', () => {
    expect(formatDuration(65.7)).toBe('1:05')
  })
})
