/** Text positions here are Unicode code points, matching the server and Python, not UTF-16 units. */

export interface Span {
  id: string
  start: number
  end: number
}

export interface Piece {
  start: number
  text: string
  ids: string[]
}

/**
 * Split text at span boundaries, so each piece is covered by one unchanging set of spans.
 * Joining every piece's text always gives back the input exactly.
 */
export function segmentText(text: string, spans: Span[]): Piece[] {
  const codePoints = Array.from(text)
  const length = codePoints.length
  const valid = spans.filter((span) => span.start >= 0 && span.end <= length && span.start < span.end)
  const boundaries = [...new Set([0, length, ...valid.flatMap((span) => [span.start, span.end])])].sort((a, b) => a - b)

  const pieces: Piece[] = []
  for (let index = 0; index < boundaries.length - 1; index += 1) {
    const start = boundaries[index]
    const end = boundaries[index + 1]
    pieces.push({
      start,
      text: codePoints.slice(start, end).join(''),
      ids: valid.filter((span) => span.start <= start && span.end >= end).map((span) => span.id),
    })
  }
  return pieces
}
