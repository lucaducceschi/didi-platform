import { describe, expect, it } from 'vitest'
import { type Span, segmentText } from './segments'

const span = (id: string, start: number, end: number): Span => ({ id, start, end })
const covered = (pieces: ReturnType<typeof segmentText>, id: string) => pieces.filter((piece) => piece.ids.includes(id)).map((piece) => piece.text).join('')
const joined = (pieces: ReturnType<typeof segmentText>) => pieces.map((piece) => piece.text).join('')

describe('segmentText', () => {
  const text = 'The quick brown fox jumps'

  it('returns one piece when nothing is highlighted', () => {
    expect(segmentText(text, [])).toEqual([{ start: 0, text, ids: [] }])
  })

  it('handles empty text', () => {
    expect(segmentText('', [])).toEqual([])
  })

  it.each([
    ['separate', [span('a', 0, 3), span('b', 4, 9)]],
    ['touching', [span('a', 0, 4), span('b', 4, 9)]],
    ['overlapping', [span('a', 0, 9), span('b', 4, 15)]],
    ['nested', [span('a', 0, 19), span('b', 4, 9)]],
    ['identical', [span('a', 4, 9), span('b', 4, 9)]],
    ['sharing a start', [span('a', 4, 9), span('b', 4, 15)]],
    ['sharing an end', [span('a', 4, 15), span('b', 10, 15)]],
    ['covering everything', [span('a', 0, 25)]],
  ])('keeps the text exact and each span complete when %s', (_, spans) => {
    const pieces = segmentText(text, spans)
    expect(joined(pieces)).toBe(text)
    for (const item of spans) expect(covered(pieces, item.id)).toBe(text.slice(item.start, item.end))
  })

  it('marks both spans where they overlap', () => {
    const pieces = segmentText(text, [span('a', 0, 9), span('b', 4, 15)])
    expect(pieces.map((piece) => [piece.text, piece.ids])).toEqual([
      ['The ', ['a']],
      ['quick', ['a', 'b']],
      [' brown', ['b']],
      [' fox jumps', []],
    ])
  })

  it('counts emoji as one position, as Python does', () => {
    const emoji = 'a🙂🙂 target end'
    const pieces = segmentText(emoji, [span('a', 4, 10)])
    expect(covered(pieces, 'a')).toBe('target')
    expect(joined(pieces)).toBe(emoji)
    expect(pieces[1].start).toBe(4)
  })

  it('never splits or changes combining characters or line endings', () => {
    const nfd = 'Gherdëina\r\nnext'
    const pieces = segmentText(nfd, [span('a', 0, 6), span('b', 7, 10)])
    expect(joined(pieces)).toBe(nfd)
    expect(covered(pieces, 'a')).toBe('Gherde')
    expect(pieces.every((piece) => piece.text.normalize('NFD') === piece.text)).toBe(true)
  })

  it('ignores spans outside the text instead of corrupting it', () => {
    const pieces = segmentText('short', [span('a', 3, 99), span('b', -1, 2), span('c', 4, 4)])
    expect(pieces).toEqual([{ start: 0, text: 'short', ids: [] }])
  })
})
