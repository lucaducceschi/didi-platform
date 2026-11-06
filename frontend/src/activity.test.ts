import { describe, expect, it } from 'vitest'
import type { ActivityEntry } from './api'
import { describeActivity } from './activity'

const entry = (action: string, target: string, details = {}, name: string | null = 'Anna'): ActivityEntry => ({
  id: 1,
  occurred_at: '2026-01-01T00:00:00Z',
  user: name ? { id: '1', username: 'anna', display_name: name } : null,
  action,
  target,
  details,
})

describe('describeActivity', () => {
  it('describes codebook changes in plain words', () => {
    expect(describeActivity(entry('code.merged', 'A into B'))).toBe('Anna merged A into B.')
    expect(describeActivity(entry('articles.added', '12 articles'))).toBe('Anna added 12 articles.')
  })

  it('describes system activity', () => {
    expect(describeActivity(entry('annotations.reconciled', '', { reanchored: 2, stale: 1 }, null))).toBe(
      'The system checked segments after a corpus update: 2 moved, 0 restored, 1 need review.',
    )
  })
})
