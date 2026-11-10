import { type PointerEvent, useState } from 'react'
import type { TopicTimelineSeries } from '../api'

/** Color follows the source type, never its rank (palette slots 1 and 2, validated in both themes). */
const SERIES: Record<string, { label: string; color: string }> = {
  journalism: { label: 'Journalism', color: 'var(--series-1)' },
  official_press: { label: 'Official press', color: 'var(--series-2)' },
}
const seriesOf = (type: string) => SERIES[type] ?? { label: type, color: 'var(--muted)' }

const W = 640
const H = 240
const M = { top: 12, right: 140, bottom: 28, left: 44 }
const pct = (x: number) => `${(x * 100).toFixed(1)}%`

interface TopicShareChartProps {
  series: TopicTimelineSeries[]
  smallSampleArticles: number
}

export function TopicShareChart({ series, smallSampleArticles }: TopicShareChartProps) {
  const [hover, setHover] = useState<number | null>(null)
  const periods = Array.from(new Set(series.flatMap((s) => s.points.map((p) => p.period)))).sort()
  if (periods.length === 0) return <p className="hint">No dated articles for this topic.</p>

  const maxShare = Math.max(0.01, ...series.flatMap((s) => s.points.map((p) => p.share)))
  const step = maxShare > 0.2 ? 0.05 : maxShare > 0.08 ? 0.02 : 0.01
  const yMax = Math.ceil(maxShare / step) * step
  const ticks = Array.from({ length: Math.round(yMax / step) + 1 }, (_, i) => i * step)
  const innerW = W - M.left - M.right
  const innerH = H - M.top - M.bottom
  const x = (i: number) => M.left + (periods.length === 1 ? innerW / 2 : (i / (periods.length - 1)) * innerW)
  const y = (v: number) => M.top + innerH - (v / yMax) * innerH
  const labelEvery = Math.max(1, Math.ceil(periods.length / 12))

  const onMove = (e: PointerEvent<SVGRectElement>) => {
    const box = e.currentTarget.getBoundingClientRect()
    const svgX = M.left + ((e.clientX - box.left) / box.width) * innerW
    let best = 0
    periods.forEach((_, i) => {
      if (Math.abs(x(i) - svgX) < Math.abs(x(best) - svgX)) best = i
    })
    setHover(best)
  }

  // End labels sit in one column right of the plot, nudged apart so they never overlap.
  const endLabels = series
    .filter((s) => s.points.length > 0)
    .map((s) => {
      const last = s.points[s.points.length - 1]
      const { label, color } = seriesOf(s.source_type)
      return { key: s.source_type, color, text: `${label} ${pct(last.share)}`, y: y(last.share) }
    })
    .sort((a, b) => a.y - b.y)
  for (let i = 1; i < endLabels.length; i++) {
    endLabels[i].y = Math.max(endLabels[i].y, endLabels[i - 1].y + 14)
  }

  const hovered = hover === null ? null : periods[hover]
  const hasSmall = series.some((s) => s.points.some((p) => p.small_sample))

  return (
    <div className="share-chart">
      <p className="term-legend hint">
        {series.map((s) => (
          <span key={s.source_type} className="share-key">
            <span className="share-key-line" style={{ background: seriesOf(s.source_type).color }} aria-hidden="true" />
            {seriesOf(s.source_type).label}
          </span>
        ))}
        {hasSmall && (
          <span className="share-key">
            <svg width="12" height="12" aria-hidden="true">
              <circle cx="6" cy="6" r="4" fill="var(--surface)" stroke="var(--muted)" strokeWidth="2" />
            </svg>
            fewer than {smallSampleArticles} articles
          </span>
        )}
      </p>
      <div style={{ position: 'relative' }}>
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Topic share of words over time by source type">
          {ticks.map((t) => (
            <g key={t}>
              <line x1={M.left} x2={M.left + innerW} y1={y(t)} y2={y(t)} stroke="var(--border)" strokeWidth={1} />
              <text x={M.left - 6} y={y(t) + 4} textAnchor="end" fontSize="11" fill="var(--muted)">
                {Math.round(t * 100)}%
              </text>
            </g>
          ))}
          {periods.map((p, i) =>
            i % labelEvery === 0 ? (
              <text key={p} x={x(i)} y={H - 8} textAnchor="middle" fontSize="11" fill="var(--muted)">
                {p}
              </text>
            ) : null,
          )}
          {hover !== null && (
            <line x1={x(hover)} x2={x(hover)} y1={M.top} y2={M.top + innerH} stroke="var(--muted)" strokeWidth={1} />
          )}
          {series.map((s) => {
            const { color } = seriesOf(s.source_type)
            const pts = s.points.map((p) => ({ ...p, i: periods.indexOf(p.period) }))
            return (
              <g key={s.source_type}>
                <polyline
                  points={pts.map((p) => `${x(p.i)},${y(p.share)}`).join(' ')}
                  fill="none"
                  stroke={color}
                  strokeWidth={2}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
                {pts.map((p) => (
                  <circle
                    key={p.period}
                    cx={x(p.i)}
                    cy={y(p.share)}
                    r={p.i === hover ? 5 : 4}
                    fill={p.small_sample ? 'var(--surface)' : color}
                    stroke={p.small_sample ? color : 'var(--surface)'}
                    strokeWidth={2}
                  />
                ))}
              </g>
            )
          })}
          {endLabels.map((l) => (
            <g key={l.key}>
              <line x1={M.left + innerW + 8} x2={M.left + innerW + 20} y1={l.y} y2={l.y} stroke={l.color} strokeWidth={2} />
              <text x={M.left + innerW + 24} y={l.y + 4} fontSize="11" fill="var(--text)">
                {l.text}
              </text>
            </g>
          ))}
          <rect
            x={M.left}
            y={M.top}
            width={innerW}
            height={innerH}
            fill="transparent"
            onPointerMove={onMove}
            onPointerLeave={() => setHover(null)}
          />
        </svg>
        {hovered && (
          <div
            className="share-tooltip"
            style={{ left: `${(x(hover!) / W) * 100}%`, transform: hover! > periods.length / 2 ? 'translateX(-105%)' : 'translateX(5%)' }}
          >
            <div className="share-tooltip-title">{hovered}</div>
            {series.map((s) => {
              const p = s.points.find((q) => q.period === hovered)
              return (
                <div key={s.source_type} className="share-tooltip-row">
                  <span className="share-key-line" style={{ background: seriesOf(s.source_type).color }} aria-hidden="true" />
                  <strong>{p ? pct(p.share) : 'none'}</strong> {seriesOf(s.source_type).label}
                  {p && <span className="hint"> · {p.articles.toLocaleString()} articles{p.small_sample ? ', small sample' : ''}</span>}
                </div>
              )
            })}
          </div>
        )}
      </div>
      <details>
        <summary className="hint">Table</summary>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Period</th>
                {series.map((s) => (
                  <th key={s.source_type}>{seriesOf(s.source_type).label} (share, articles)</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {periods.map((period) => (
                <tr key={period}>
                  <td>{period}</td>
                  {series.map((s) => {
                    const p = s.points.find((q) => q.period === period)
                    return (
                      <td key={s.source_type}>
                        {p ? `${pct(p.share)} (${p.articles.toLocaleString()}${p.small_sample ? ', small' : ''})` : '–'}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  )
}
