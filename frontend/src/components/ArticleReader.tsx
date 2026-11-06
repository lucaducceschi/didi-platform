import { useMemo } from 'react'
import { segmentText } from '../segments'

export interface Highlight {
  id: string
  start: number
  end: number
  color: string
  label: string
  mine: boolean
}

export function ArticleReader({ text, highlights, selectedIds, onSelect }: {
  text: string
  highlights: Highlight[]
  selectedIds: string[]
  onSelect: (ids: string[]) => void
}) {
  const byId = useMemo(() => new Map(highlights.map((highlight) => [highlight.id, highlight])), [highlights])
  const pieces = useMemo(() => segmentText(text, highlights), [text, highlights])

  // Text is always rendered as React text children, so markup in scraped articles stays literal.
  return (
    <div className="didi-reader" data-testid="article-text">
      {pieces.map((piece) => {
        if (piece.ids.length === 0) return <span key={piece.start} data-start={piece.start}>{piece.text}</span>
        const covering = piece.ids.map((id) => byId.get(id)!)
        const main = covering.find((highlight) => highlight.mine) ?? covering[0]
        const className = [
          'hl',
          main.mine ? 'hl-mine' : 'hl-other',
          covering.length > 1 && 'hl-overlap',
          piece.ids.some((id) => selectedIds.includes(id)) && 'hl-selected',
        ].filter(Boolean).join(' ')
        return (
          <span
            key={piece.start}
            data-start={piece.start}
            data-segments={piece.ids.join(' ')}
            className={className}
            style={{ '--hl': main.color } as React.CSSProperties}
            title={covering.map((highlight) => highlight.label).join('\n')}
            onClick={() => onSelect(piece.ids)}
          >
            {piece.text}
          </span>
        )
      })}
    </div>
  )
}
