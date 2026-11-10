import { useEffect, useMemo, useRef } from 'react'
import { segmentText } from '../segments'
import { selectionToCodePoints } from '../selection'

export interface Highlight {
  id: string
  start: number
  end: number
  color: string
  label: string
  mine: boolean
}

export interface PendingSelection {
  start: number
  end: number
}

const PENDING_ID = 'pending-selection'

export function ArticleReader({ text, highlights, selectedIds, pending, popover, onSelect, onTextSelected, onCancelSelection }: {
  text: string
  highlights: Highlight[]
  selectedIds: string[]
  pending?: PendingSelection | null
  popover?: React.ReactNode
  onSelect: (ids: string[]) => void
  /** Left out when this person can't code here, which turns selection off. */
  onTextSelected?: (selection: PendingSelection, coords?: { top: number; left: number }) => void
  onCancelSelection?: () => void
}) {
  const root = useRef<HTMLDivElement>(null)
  const byId = useMemo(() => new Map(highlights.map((highlight) => [highlight.id, highlight])), [highlights])
  const spans = useMemo(() => (pending ? [...highlights, { id: PENDING_ID, ...pending }] : highlights), [highlights, pending])
  const pieces = useMemo(() => segmentText(text, spans), [text, spans])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        const selection = window.getSelection()
        if (selection && !selection.isCollapsed) {
          selection.removeAllRanges()
        }
        if (pending && onCancelSelection) {
          onCancelSelection()
        }
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [pending, onCancelSelection])

  const finishSelection = () => {
    if (!onTextSelected || !root.current) return
    const selection = window.getSelection()
    if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return
    const range = selection.getRangeAt(0)
    const positions = selectionToCodePoints(range, root.current)
    if (!positions) return

    // Calculate relative coordinates for popover
    const rangeRect = range.getBoundingClientRect()
    const rootRect = root.current.getBoundingClientRect()
    const coords = {
      top: rangeRect.bottom - rootRect.top + 8,
      left: Math.max(8, Math.min(rangeRect.left - rootRect.left, rootRect.width - 330)),
    }

    selection.removeAllRanges()
    onTextSelected(positions, coords)
  }

  // Text is always rendered as React text children, so markup in scraped articles stays literal.
  return (
    <div ref={root} className="didi-reader" style={{ position: 'relative' }} data-testid="article-text" onMouseUp={finishSelection} onTouchEnd={finishSelection}>
      {pieces.map((piece) => {
        const isPending = piece.ids.includes(PENDING_ID)
        const ids = piece.ids.filter((id) => id !== PENDING_ID)
        if (ids.length === 0) {
          return <span key={piece.start} data-start={piece.start} className={isPending ? 'hl-pending' : undefined}>{piece.text}</span>
        }
        const covering = ids.map((id) => byId.get(id)!)
        const main = covering.find((highlight) => highlight.mine) ?? covering[0]
        const className = [
          'hl',
          main.mine ? 'hl-mine' : 'hl-other',
          covering.length > 1 && 'hl-overlap',
          ids.some((id) => selectedIds.includes(id)) && 'hl-selected',
          isPending && 'hl-pending',
        ].filter(Boolean).join(' ')
        return (
          <span
            key={piece.start}
            data-start={piece.start}
            data-segments={ids.join(' ')}
            className={className}
            style={{ '--hl': main.color } as React.CSSProperties}
            title={covering.map((highlight) => highlight.label).join('\n')}
            onClick={() => {
              // A drag that ends on a highlight is a selection, handled on mouse up.
              if (window.getSelection()?.isCollapsed !== false) onSelect(ids)
            }}
          >
            {piece.text}
          </span>
        )
      })}
      {popover}
    </div>
  )
}
