import { describe, it, expect } from 'vitest'
import { parseLocalDate } from './date'

describe('parseLocalDate (issue #30)', () => {
  it('parses "YYYY-MM-DD" as local midnight (no UTC shift)', () => {
    const d = parseLocalDate('2026-06-12')
    expect(d.getFullYear()).toBe(2026)
    expect(d.getMonth()).toBe(5) // 0-indexed June
    expect(d.getDate()).toBe(12)
    expect(d.getHours()).toBe(0)
  })

  it('matches a locally-constructed Date for the same day', () => {
    const d = parseLocalDate('2026-01-01')
    expect(d.getTime()).toBe(new Date(2026, 0, 1).getTime())
  })

  it('takes the date part of an ISO datetime string', () => {
    const d = parseLocalDate('2026-06-12T15:30:00Z')
    expect(d.getFullYear()).toBe(2026)
    expect(d.getMonth()).toBe(5)
    expect(d.getDate()).toBe(12)
  })
})
