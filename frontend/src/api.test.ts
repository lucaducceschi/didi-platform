import { describe, expect, it } from 'vitest'
import { searchPath } from './api'

describe('searchPath', () => {
  it('encodes the query and repeats list filters', () => {
    const path = searchPath({ q: ' Gherdëina "ie" ', sources: ['salto', 'trail'], languages: ['de'], page: 2 })
    const params = new URL(path, 'http://localhost').searchParams
    expect(params.get('q')).toBe('Gherdëina "ie"')
    expect(params.getAll('source')).toEqual(['salto', 'trail'])
    expect(params.getAll('language')).toEqual(['de'])
    expect(params.get('page')).toBe('2')
  })

  it('leaves out an empty query', () => {
    expect(searchPath({ q: '   ', sources: [], languages: [], page: 1 })).toBe('/api/articles/search?page=1')
  })
})
