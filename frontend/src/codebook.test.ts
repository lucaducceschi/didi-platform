import { describe, expect, it } from 'vitest'
import type { Code } from './api'
import { allowedParents, flattenCodeTree } from './codebook'

const code = (id: string, parent_id: string | null = null): Code => ({
  id,
  name: id.toUpperCase(),
  parent_id,
  definition: '',
  color: '#000000',
  sort_order: 0,
  revision: 1,
  segment_count: 0,
  coder_count: 0,
})

describe('flattenCodeTree', () => {
  it('puts children after their parent with full paths', () => {
    const nodes = flattenCodeTree([code('c', 'b'), code('a'), code('b', 'a'), code('d')])
    expect(nodes.map((node) => [node.code.id, node.depth, node.path])).toEqual([
      ['a', 0, 'A'],
      ['b', 1, 'A > B'],
      ['c', 2, 'A > B > C'],
      ['d', 0, 'D'],
    ])
  })

  it('keeps a code visible if its parent is missing from the list', () => {
    expect(flattenCodeTree([code('x', 'gone')]).map((node) => node.depth)).toEqual([0])
  })
})

describe('allowedParents', () => {
  it('leaves out the code and all its descendants', () => {
    const codes = [code('a'), code('b', 'a'), code('c', 'b'), code('d')]
    expect(allowedParents(codes, 'a').map((item) => item.id)).toEqual(['d'])
    expect(allowedParents(codes, 'c').map((item) => item.id)).toEqual(['a', 'b', 'd'])
  })
})
