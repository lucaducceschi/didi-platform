import { useState } from 'react'
import type { RadarLanguageData } from '../../api'

const CATEGORIES: Array<{ key: keyof RadarLanguageData['foundations']; label: string }> = [
  { key: 'care', label: 'Care' },
  { key: 'fairness', label: 'Fairness' },
  { key: 'loyalty', label: 'Loyalty' },
  { key: 'authority', label: 'Authority' },
  { key: 'sanctity', label: 'Sanctity' },
]

const LANG_COLORS: Record<string, string> = {
  de: '#1f77b4',
  it: '#2ca02c',
  lld_gherd: '#ff7f0e',
  lld_badia: '#d62728',
  lld_fascia: '#9467bd',
}

interface RadarChartProps {
  data: RadarLanguageData[]
  size?: number
}

export function RadarChart({ data, size = 440 }: RadarChartProps) {
  const [hoveredPoint, setHoveredPoint] = useState<{
    lang: string
    category: string
    value: number
    x: number
    y: number
  } | null>(null)

  const cx = size / 2
  const cy = size / 2
  const radius = size * 0.36
  const numAxes = CATEGORIES.length

  // Find max value across all data to scale axes
  let maxVal = 10.0
  data.forEach((d) => {
    CATEGORIES.forEach(({ key }) => {
      const val = d.foundations[key] || 0
      if (val > maxVal) maxVal = val
    })
  })
  maxVal = Math.ceil(maxVal * 1.15)

  // Compute angles for 5 vertices (-PI/2 puts first vertex at 12 o'clock)
  const angles = CATEGORIES.map((_, i) => -Math.PI / 2 + (i * 2 * Math.PI) / numAxes)

  // Guide rings at 25%, 50%, 75%, 100%
  const rings = [0.25, 0.5, 0.75, 1.0]

  return (
    <div style={{ position: 'relative', display: 'inline-block' }}>
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        style={{ overflow: 'visible', maxWidth: '100%', height: 'auto' }}
        role="img"
        aria-label="Moral Foundations Framing Radar"
      >
        {/* Background concentric guide circles & labels */}
        {rings.map((rFrac) => {
          const r = radius * rFrac
          const pts = angles
            .map((angle) => `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`)
            .join(' ')
          return (
            <g key={rFrac}>
              <polygon
                points={pts}
                fill="none"
                stroke="var(--border, #dcdde0)"
                strokeDasharray={rFrac === 1 ? 'none' : '3 3'}
                strokeWidth={rFrac === 1 ? 1.5 : 1}
              />
              <text
                x={cx + 6}
                y={cy - r + 12}
                fontSize={10}
                fill="var(--muted, #666)"
                textAnchor="start"
              >
                {(maxVal * rFrac).toFixed(1)}
              </text>
            </g>
          )
        })}

        {/* Spoke lines & category labels */}
        {angles.map((angle, i) => {
          const cat = CATEGORIES[i]
          const x2 = cx + radius * Math.cos(angle)
          const y2 = cy + radius * Math.sin(angle)
          const lx = cx + (radius + 28) * Math.cos(angle)
          const ly = cy + (radius + 28) * Math.sin(angle)
          const anchor = Math.abs(Math.cos(angle)) < 0.2 ? 'middle' : Math.cos(angle) > 0 ? 'start' : 'end'

          return (
            <g key={cat.key}>
              <line
                x1={cx}
                y1={cy}
                x2={x2}
                y2={y2}
                stroke="var(--border, #dcdde0)"
                strokeWidth={1}
              />
              <text
                x={lx}
                y={ly + 4}
                textAnchor={anchor}
                fontSize={13}
                fontWeight={600}
                fill="var(--text, #1f2328)"
              >
                {cat.label}
              </text>
            </g>
          )
        })}

        {/* Polygons for each language */}
        {data.map((langData) => {
          const color = LANG_COLORS[langData.language] || '#636efa'
          const ptsArray = angles.map((angle, i) => {
            const cat = CATEGORIES[i]
            const val = langData.foundations[cat.key] || 0
            const r = (val / maxVal) * radius
            return {
              x: cx + r * Math.cos(angle),
              y: cy + r * Math.sin(angle),
              val,
              cat: cat.label,
            }
          })
          const pointsStr = ptsArray.map((p) => `${p.x},${p.y}`).join(' ')

          return (
            <g key={langData.language}>
              <polygon
                points={pointsStr}
                fill={color}
                fillOpacity={0.28}
                stroke={color}
                strokeWidth={2.5}
              />
              {ptsArray.map((p, i) => (
                <circle
                  key={i}
                  cx={p.x}
                  cy={p.y}
                  r={5}
                  fill={color}
                  stroke="var(--surface, #fff)"
                  strokeWidth={1.5}
                  style={{ cursor: 'pointer' }}
                  onMouseEnter={() =>
                    setHoveredPoint({
                      lang: langData.language_label,
                      category: p.cat,
                      value: p.val,
                      x: p.x,
                      y: p.y,
                    })
                  }
                  onMouseLeave={() => setHoveredPoint(null)}
                />
              ))}
            </g>
          )
        })}
      </svg>

      {/* Floating tooltip */}
      {hoveredPoint && (
        <div
          style={{
            position: 'absolute',
            left: hoveredPoint.x + 10,
            top: hoveredPoint.y - 30,
            background: 'var(--surface, #ffffff)',
            color: 'var(--text, #1f2328)',
            border: '1px solid var(--border, #dcdde0)',
            borderRadius: '6px',
            padding: '4px 8px',
            fontSize: '12px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
            pointerEvents: 'none',
            whiteSpace: 'nowrap',
            zIndex: 10,
          }}
        >
          <strong>{hoveredPoint.lang}</strong> — {hoveredPoint.category}: {hoveredPoint.value.toFixed(2)}/1k
        </div>
      )}

      {/* Chart Legend */}
      <div style={{ display: 'flex', justifyContent: 'center', gap: '16px', marginTop: '12px' }}>
        {data.map((d) => (
          <div key={d.language} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px' }}>
            <span
              style={{
                display: 'inline-block',
                width: '14px',
                height: '14px',
                borderRadius: '3px',
                backgroundColor: LANG_COLORS[d.language] || '#636efa',
              }}
            />
            <span>
              <strong>{d.language_label}</strong> ({d.article_count.toLocaleString()} articles)
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

