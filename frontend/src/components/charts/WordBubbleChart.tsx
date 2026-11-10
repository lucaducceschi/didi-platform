import { useMemo, useState } from 'react'
import type { WordBubbleItem } from '../../api'

interface WordBubbleChartProps {
  data: WordBubbleItem[]
  onSelectWord: (item: WordBubbleItem) => void
  selectedId?: string | null
  width?: number
  height?: number
}

interface PlacedBubble {
  item: WordBubbleItem
  x: number
  y: number
  r: number
}

export function WordBubbleChart({
  data,
  onSelectWord,
  selectedId,
  width = 820,
  height = 360,
}: WordBubbleChartProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null)

  // Fast deterministic circle packing with iterative relaxation
  const placedBubbles = useMemo<PlacedBubble[]>(() => {
    if (!data || data.length === 0) return []

    const cx = width / 2
    const cy = height / 2

    // Sort descending by salience so the most prominent bubbles anchor the center
    const sorted = [...data].sort((a, b) => b.salience - a.salience)

    // Compute radii proportional to salience (range: 26px to 54px)
    const bubbles: PlacedBubble[] = sorted.map((item, idx) => {
      const r = Math.round(26 + item.salience * 28)
      // Initial positioning along a Fermat golden spiral
      const theta = idx * 2.39996 // Golden angle in radians
      const dist = (idx === 0 ? 0 : 38 + Math.sqrt(idx) * 58)
      const x = cx + dist * Math.cos(theta)
      const y = cy + dist * Math.sin(theta)
      return { item, x, y, r }
    })

    // Relaxation steps to eliminate overlap and gently pull toward center
    const iterations = 80
    const padding = 6

    for (let it = 0; it < iterations; it++) {
      // 1. Resolve pairwise overlaps
      for (let i = 0; i < bubbles.length; i++) {
        for (let j = i + 1; j < bubbles.length; j++) {
          const b1 = bubbles[i]
          const b2 = bubbles[j]
          const dx = b2.x - b1.x
          const dy = b2.y - b1.y
          const dist = Math.hypot(dx, dy) || 0.001
          const minDist = b1.r + b2.r + padding

          if (dist < minDist) {
            const overlap = (minDist - dist) / dist
            const pushX = dx * overlap * 0.42
            const pushY = dy * overlap * 0.42
            b1.x -= pushX
            b1.y -= pushY
            b2.x += pushX
            b2.y += pushY
          }
        }
      }

      // 2. Center attraction
      for (const b of bubbles) {
        b.x += (cx - b.x) * 0.035
        b.y += (cy - b.y) * 0.035

        // 3. Keep within canvas bounds
        b.x = Math.max(b.r + 10, Math.min(width - b.r - 10, b.x))
        b.y = Math.max(b.r + 10, Math.min(height - b.r - 10, b.y))
      }
    }

    return bubbles
  }, [data, width, height])

  const activeBubble = placedBubbles.find(
    (b) => b.item.id === (hoveredId || selectedId)
  )?.item

  return (
    <div style={{ position: 'relative', width: '100%', userSelect: 'none' }}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        style={{
          width: '100%',
          height: 'auto',
          maxHeight: '400px',
          display: 'block',
          overflow: 'visible',
        }}
      >
        <defs>
          <radialGradient id="bubble-glow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="rgba(255,255,255,0.4)" />
            <stop offset="100%" stopColor="rgba(255,255,255,0)" />
          </radialGradient>
        </defs>

        {/* Ambient background guide rings */}
        <circle
          cx={width / 2}
          cy={height / 2}
          r={height * 0.44}
          fill="none"
          stroke="var(--border)"
          strokeDasharray="4 6"
          strokeOpacity={0.4}
        />
        <circle
          cx={width / 2}
          cy={height / 2}
          r={height * 0.22}
          fill="none"
          stroke="var(--border)"
          strokeDasharray="2 4"
          strokeOpacity={0.3}
        />

        {/* Bubbles */}
        {placedBubbles.map((b) => {
          const isSelected = selectedId === b.item.id
          const isHovered = hoveredId === b.item.id
          const isHighlighted = isSelected || isHovered
          const fontSize = Math.max(11, Math.min(15, Math.round(b.r * 0.32)))

          return (
            <g
              key={b.item.id}
              role="button"
              tabIndex={0}
              aria-label={`${b.item.term}: ${b.item.count} articles`}
              onClick={() => onSelectWord(b.item)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onSelectWord(b.item)
                }
              }}
              onMouseEnter={() => setHoveredId(b.item.id)}
              onMouseLeave={() => setHoveredId(null)}
              style={{
                cursor: 'pointer',
                transition: 'transform 0.15s ease-out',
                transformOrigin: `${b.x}px ${b.y}px`,
                transform: isHighlighted ? 'scale(1.08)' : 'scale(1)',
              }}
            >
              <title>{`${b.item.term} (${b.item.category}) · ${b.item.count.toLocaleString()} articles · Click for lexical dossier`}</title>

              {/* Selection Halo */}
              {isSelected && (
                <circle
                  cx={b.x}
                  cy={b.y}
                  r={b.r + 5}
                  fill="none"
                  stroke={b.item.category_color}
                  strokeWidth="2.5"
                  strokeDasharray="3 3"
                />
              )}

              {/* Main Bubble Circle */}
              <circle
                cx={b.x}
                cy={b.y}
                r={b.r}
                fill={b.item.category_color}
                fillOpacity={isHighlighted ? 0.38 : 0.18}
                stroke={b.item.category_color}
                strokeWidth={isHighlighted ? 2.5 : 1.5}
                style={{
                  filter: isHighlighted
                    ? 'drop-shadow(0 4px 10px rgba(0,0,0,0.18))'
                    : 'none',
                  transition: 'all 0.15s ease-out',
                }}
              />

              {/* Inner highlight sheen */}
              <circle
                cx={b.x - b.r * 0.25}
                cy={b.y - b.r * 0.25}
                r={b.r * 0.55}
                fill="url(#bubble-glow)"
                pointerEvents="none"
              />

              {/* Term text label */}
              <text
                x={b.x}
                y={b.r >= 38 ? b.y - 3 : b.y + 4}
                textAnchor="middle"
                fontSize={fontSize}
                fontWeight="600"
                fill="var(--text)"
                style={{ pointerEvents: 'none' }}
              >
                {b.item.term}
              </text>

              {/* Sub-label: Article count or twin term */}
              {b.r >= 38 && (
                <text
                  x={b.x}
                  y={b.y + fontSize + 2}
                  textAnchor="middle"
                  fontSize="10"
                  fill="var(--muted)"
                  style={{ pointerEvents: 'none', fontWeight: 500 }}
                >
                  {b.item.count > 1000
                    ? `${(b.item.count / 1000).toFixed(1)}k art.`
                    : `${b.item.count} art.`}
                </text>
              )}
            </g>
          )
        })}
      </svg>

      {/* Floating Info Footnote / Live Hint */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '8px',
          padding: '8px 12px',
          background: 'var(--canvas-subtle, rgba(0,0,0,0.02))',
          border: '1px solid var(--border)',
          borderRadius: '6px',
          fontSize: '12px',
          color: 'var(--muted)',
          minHeight: '36px',
        }}
      >
        {activeBubble ? (
          <>
            <div>
              <strong style={{ color: 'var(--text)' }}>{activeBubble.term}</strong>
              {activeBubble.twin_term && activeBubble.twin_term !== activeBubble.term && (
                <span style={{ marginLeft: '4px' }}>
                  / <em>{activeBubble.twin_term}</em>
                </span>
              )}
              <span
                style={{
                  marginLeft: '8px',
                  padding: '1px 6px',
                  borderRadius: '10px',
                  backgroundColor: activeBubble.category_color + '22',
                  color: activeBubble.category_color,
                  fontWeight: 600,
                  fontSize: '11px',
                }}
              >
                {activeBubble.category}
              </span>
            </div>
            <div style={{ display: 'flex', gap: '14px', alignItems: 'center' }}>
              <span>
                <strong>{activeBubble.count.toLocaleString()}</strong> articles
              </span>
              <span>
                🇩🇪 {Math.round(activeBubble.de_ratio * 100)}% · 🇮🇹 {Math.round(activeBubble.it_ratio * 100)}%
              </span>
              <span style={{ color: 'var(--accent)', fontWeight: 600 }}>
                Click to open dossier &rarr;
              </span>
            </div>
          </>
        ) : (
          <div style={{ textAlign: 'center', width: '100%' }}>
            <span>💡 Bubble size reflects corpus salience. Click any term to inspect its longitudinal trend, collocations, and cross-linguistic balance.</span>
          </div>
        )}
      </div>
    </div>
  )
}

