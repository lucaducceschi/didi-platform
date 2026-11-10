import { useState } from 'react'
import type { TimelinePoint } from '../../api'

const LANG_COLORS: Record<string, string> = {
  de: '#1f77b4',
  it: '#2ca02c',
  lld_gherd: '#ff7f0e',
  lld_badia: '#d62728',
  lld_fascia: '#9467bd',
}

interface TimelineChartProps {
  series: TimelinePoint[]
  metric: 'avg_sentiment' | 'avg_moral_density'
  width?: number
  height?: number
}

export function TimelineChart({
  series,
  metric,
  width = 860,
  height = 360,
}: TimelineChartProps) {
  const [hoveredPoint, setHoveredPoint] = useState<{
    period: string
    lang: string
    val: number
    count: number
    x: number
    y: number
  } | null>(null)

  const margin = { top: 25, right: 30, bottom: 45, left: 55 }
  const chartWidth = width - margin.left - margin.right
  const chartHeight = height - margin.top - margin.bottom

  // Extract unique sorted periods
  const periods = Array.from(new Set(series.map((s) => s.period))).sort()
  const languages = Array.from(new Set(series.map((s) => s.language)))

  if (periods.length === 0) {
    return <p className="result-count">No timeline data matching current filters.</p>
  }

  // Determine Y range
  let minY = 0
  let maxY = 1
  if (metric === 'avg_sentiment') {
    minY = -0.6
    maxY = 0.8
    series.forEach((s) => {
      if (s.avg_sentiment < minY) minY = Math.floor(s.avg_sentiment * 10) / 10
      if (s.avg_sentiment > maxY) maxY = Math.ceil(s.avg_sentiment * 10) / 10
    })
  } else {
    minY = 0
    maxY = 10
    series.forEach((s) => {
      if (s.avg_moral_density > maxY) maxY = Math.ceil(s.avg_moral_density * 1.15)
    })
  }

  // Scales
  const getX = (period: string) => {
    const idx = periods.indexOf(period)
    return periods.length > 1 ? (idx / (periods.length - 1)) * chartWidth : chartWidth / 2
  }

  const getY = (val: number) => {
    const frac = (val - minY) / (maxY - minY || 1)
    return chartHeight * (1 - frac)
  }

  // Group by language
  const seriesByLang: Record<string, TimelinePoint[]> = {}
  languages.forEach((l) => {
    seriesByLang[l] = series.filter((s) => s.language === l).sort((a, b) => a.period.localeCompare(b.period))
  })

  // Y-grid ticks
  const numYTicks = 5
  const yTicks = Array.from({ length: numYTicks + 1 }, (_, i) => minY + (i * (maxY - minY)) / numYTicks)

  // X-axis label step (e.g. show ~8-10 ticks)
  const xStep = Math.max(1, Math.floor(periods.length / 8))

  return (
    <div style={{ position: 'relative', width: '100%', maxWidth: `${width}px` }}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        style={{ width: '100%', height: 'auto', overflow: 'visible' }}
        role="img"
        aria-label="Discourse Dynamics Timeline"
      >
        <g transform={`translate(${margin.left}, ${margin.top})`}>
          {/* Y Grid & Labels */}
          {yTicks.map((tick) => {
            const y = getY(tick)
            return (
              <g key={tick}>
                <line
                  x1={0}
                  y1={y}
                  x2={chartWidth}
                  y2={y}
                  stroke="var(--border, #dcdde0)"
                  strokeDasharray="3 3"
                  strokeWidth={1}
                />
                <text
                  x={-8}
                  y={y + 4}
                  textAnchor="end"
                  fontSize={11}
                  fill="var(--muted, #666)"
                >
                  {tick.toFixed(metric === 'avg_sentiment' ? 2 : 1)}
                </text>
              </g>
            )
          })}

          {/* Zero baseline for sentiment */}
          {metric === 'avg_sentiment' && minY < 0 && (
            <line
              x1={0}
              y1={getY(0)}
              x2={chartWidth}
              y2={getY(0)}
              stroke="var(--muted, #888)"
              strokeWidth={1.5}
            />
          )}

          {/* X Grid & Labels */}
          {periods.map((period, idx) => {
            if (idx % xStep !== 0 && idx !== periods.length - 1) return null
            const x = getX(period)
            return (
              <g key={period}>
                <line
                  x1={x}
                  y1={0}
                  x2={x}
                  y2={chartHeight}
                  stroke="var(--border, #dcdde0)"
                  strokeDasharray="2 2"
                  strokeOpacity={0.6}
                />
                <text
                  x={x}
                  y={chartHeight + 18}
                  textAnchor="middle"
                  fontSize={11}
                  fill="var(--muted, #666)"
                >
                  {period}
                </text>
              </g>
            )
          })}

          {/* Data Lines & Dots per language */}
          {languages.map((lang) => {
            const points = seriesByLang[lang] || []
            if (points.length === 0) return null
            const color = LANG_COLORS[lang] || '#636efa'

            const pathD = points
              .map((p, idx) => {
                const val = metric === 'avg_sentiment' ? p.avg_sentiment : p.avg_moral_density
                const x = getX(p.period)
                const y = getY(val)
                return `${idx === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`
              })
              .join(' ')

            return (
              <g key={lang}>
                <path
                  d={pathD}
                  fill="none"
                  stroke={color}
                  strokeWidth={2.5}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                {points.map((p) => {
                  const val = metric === 'avg_sentiment' ? p.avg_sentiment : p.avg_moral_density
                  const x = getX(p.period)
                  const y = getY(val)
                  return (
                    <circle
                      key={p.period}
                      cx={x}
                      cy={y}
                      r={3.5}
                      fill={color}
                      stroke="var(--surface, #fff)"
                      strokeWidth={1.5}
                      style={{ cursor: 'pointer' }}
                      onMouseEnter={() =>
                        setHoveredPoint({
                          period: p.period,
                          lang: lang.toUpperCase(),
                          val,
                          count: p.article_count,
                          x: x + margin.left,
                          y: y + margin.top,
                        })
                      }
                      onMouseLeave={() => setHoveredPoint(null)}
                    />
                  )
                })}
              </g>
            )
          })}
        </g>
      </svg>

      {/* Tooltip */}
      {hoveredPoint && (
        <div
          style={{
            position: 'absolute',
            left: `${(hoveredPoint.x / width) * 100}%`,
            top: hoveredPoint.y - 38,
            transform: 'translateX(-50%)',
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
          <strong>{hoveredPoint.period}</strong> ({hoveredPoint.lang}):{' '}
          {metric === 'avg_sentiment' ? 'Net Sentiment' : 'Moral Density'} = {hoveredPoint.val.toFixed(3)}
          <span style={{ color: 'var(--muted, #666)', marginLeft: '6px' }}>({hoveredPoint.count} arts)</span>
        </div>
      )}

      {/* Legend */}
      <div style={{ display: 'flex', justifyContent: 'center', gap: '16px', marginTop: '12px' }}>
        {languages.map((l) => (
          <div key={l} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px' }}>
            <span
              style={{
                display: 'inline-block',
                width: '16px',
                height: '3px',
                backgroundColor: LANG_COLORS[l] || '#636efa',
              }}
            />
            <span>{l.toUpperCase()}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

