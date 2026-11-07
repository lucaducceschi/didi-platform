// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest'
import { selectionToCodePoints, trimSelection } from './selection'
import { segmentText } from './segments'

function render(text: string, spans: { id: string; start: number; end: number }[] = []) {
  const root = document.createElement('div')
  for (const piece of segmentText(text, spans)) {
    const span = document.createElement('span')
    span.dataset.start = String(piece.start)
    span.textContent = piece.text
    root.append(span)
  }
  document.body.append(root)
  return root
}

/** Select `target` as a browser would, using UTF-16 offsets across however many pieces it spans. */
function rangeFor(root: HTMLElement, target: string): Range {
  const whole = root.textContent!
  const from = whole.indexOf(target)
  const to = from + target.length
  const range = document.createRange()
  let seen = 0
  for (const span of Array.from(root.children)) {
    const node = span.firstChild as Text
    const next = seen + node.length
    if (from >= seen && from < next) range.setStart(node, from - seen)
    if (to > seen && to <= next) range.setEnd(node, to - seen)
    seen = next
  }
  return range
}

const slice = (text: string, start: number, end: number) => Array.from(text).slice(start, end).join('')

afterEach(() => { document.body.innerHTML = '' })

describe('selectionToCodePoints', () => {
  it.each([
    ['plain text', 'The quick brown fox', 'brown'],
    ['after emoji', 'Emoji 🙂🙂🙂 then target ends', 'target'],
    ['containing emoji', 'Before 🙂 middle 🙂 after', '🙂 middle 🙂'],
    ['after combining characters', 'Gherdëina ëë target end', 'target'],
    ['after CRLF', 'Line one\r\nLine two\r\ntarget end', 'target'],
    ['across a line break', 'First line\n\nSecond line', 'line\n\nSecond'],
  ])('matches Python-style slicing %s', (_, text, target) => {
    const root = render(text)
    const position = selectionToCodePoints(rangeFor(root, target), root)!
    expect(slice(text, position.start, position.end)).toBe(target)
  })

  it('works across existing highlights', () => {
    const text = 'Emoji 🙂 one two three four'
    const root = render(text, [{ id: 'a', start: 8, end: 11 }, { id: 'b', start: 12, end: 15 }])
    expect(root.children.length).toBeGreaterThan(3)
    const position = selectionToCodePoints(rangeFor(root, 'one two three'), root)!
    expect(slice(text, position.start, position.end)).toBe('one two three')
  })

  it('handles boundaries on elements rather than text', () => {
    const text = 'one two three'
    const root = render(text, [{ id: 'a', start: 4, end: 7 }])
    const range = document.createRange()
    range.setStart(root.children[1], 0)
    range.setEnd(root, 2)
    expect(selectionToCodePoints(range, root)).toEqual({ start: 4, end: 7 })
  })

  it('ignores a collapsed selection', () => {
    const root = render('some text')
    const range = document.createRange()
    range.setStart(root.children[0].firstChild!, 2)
    range.collapse(true)
    expect(selectionToCodePoints(range, root)).toBeNull()
  })

  it('ignores a selection that begins or ends outside the reader', () => {
    const outside = document.createElement('p')
    outside.textContent = 'outside text'
    document.body.append(outside)
    const root = render('inside text')
    const inside = root.children[0].firstChild!

    const begins = document.createRange()
    begins.setStart(outside.firstChild!, 2)
    begins.setEnd(inside, 3)
    expect(selectionToCodePoints(begins, root)).toBeNull()

    const ends = document.createRange()
    ends.setStart(inside, 2)
    const after = document.createElement('p')
    after.textContent = 'after text'
    document.body.append(after)
    ends.setEnd(after.firstChild!, 3)
    expect(selectionToCodePoints(ends, root)).toBeNull()
  })
})

describe('trimSelection', () => {
  it('trims whitespace and counts code points', () => {
    expect(trimSelection('a🙂  word \n b', 2, 10)).toEqual({ start: 4, end: 8, quote: 'word' })
  })

  it('returns null for whitespace only', () => {
    expect(trimSelection('a \n b', 1, 4)).toBeNull()
  })
})
