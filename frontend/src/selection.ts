/**
 * Convert browser selection offsets to Unicode code points, as the server and Python count them.
 * Browsers count UTF-16 units, so an emoji is 2 there and 1 here. This is the only place that converts.
 */

function pieceElement(node: Node, root: HTMLElement): HTMLElement | null {
  let current: Node | null = node
  while (current && current !== root) {
    if (current instanceof HTMLElement && current.dataset.start !== undefined) return current
    current = current.parentNode
  }
  return null
}

function codePointsBefore(text: string, utf16Offset: number): number {
  return Array.from(text.slice(0, utf16Offset)).length
}

function boundaryPosition(node: Node, offset: number, root: HTMLElement): number | null {
  if (node === root) {
    // The boundary sits between pieces: `offset` counts the piece elements before it.
    const pieces = Array.from(root.children) as HTMLElement[]
    if (offset < pieces.length) return Number(pieces[offset].dataset.start)
    const last = pieces[pieces.length - 1]
    return last ? Number(last.dataset.start) + Array.from(last.textContent ?? '').length : 0
  }
  const piece = pieceElement(node, root)
  if (!piece) return null
  const start = Number(piece.dataset.start)
  if (node.nodeType === Node.TEXT_NODE) return start + codePointsBefore((node as Text).data, offset)
  // The boundary is on the piece element itself: 0 means before its text, otherwise after it.
  return offset === 0 ? start : start + Array.from(piece.textContent ?? '').length
}

/** Return the selected range, or null if it is empty or doesn't lie entirely inside the reader. */
export function selectionToCodePoints(range: Range, root: HTMLElement): { start: number; end: number } | null {
  if (range.collapsed) return null
  if (!root.contains(range.startContainer) || !root.contains(range.endContainer)) return null
  const start = boundaryPosition(range.startContainer, range.startOffset, root)
  const end = boundaryPosition(range.endContainer, range.endOffset, root)
  if (start === null || end === null || start >= end) return null
  return { start, end }
}

/** Trim whitespace for display. The server repeats this and has the final word on what is saved. */
export function trimSelection(text: string, start: number, end: number): { start: number; end: number; quote: string } | null {
  const codePoints = Array.from(text)
  let from = start
  let to = end
  while (from < to && /^\s$/u.test(codePoints[from])) from += 1
  while (to > from && /^\s$/u.test(codePoints[to - 1])) to -= 1
  return from < to ? { start: from, end: to, quote: codePoints.slice(from, to).join('') } : null
}
