import { useState } from 'react'
import type { RadarLanguageData } from '../../api'

const EMOTIONS: Array<{ key: keyof RadarLanguageData['emotions']; label: string }> = [
  { key: 'anger', label: 'Anger' },
  { key: 'anticipation', label: 'Anticipation' },
  { key: 'disgust', label: 'Disgust' },
  { key: 'fear', label: 'Fear' },
  { key: 'joy', label: 'Joy' },
  { key: 'sadness', label: 'Sadness' },
  { key: 'surprise', label: 'Surprise' },
  { key: 'trust', label: 'Trust' },
]

const LANG_COLORS: Record<string, string> = {
  de: '#1f77b4',
  it: '#2ca02c',
  lld_gherd: '#ff7f0e',
  lld_badia: '#d62728',
  lld_fascia: '#9467bd',
}

interface EmotionBarChartProps {
  data: RadarLanguageData[]
  width?: number
  height?: number
}

export function EmotionBarChart({ data, width = 680, height = 320 }: EmotionBarChartProps) {
  const [hovered, setHovered] = useState<{
    lang: string
    emotion: string
    value: number
    x: number
    y: number
  } | null>(null)

  const margin = { top: 20, right: 20, bottom: 50, left: 50 }
  const chartWidth = width - margin.left - margin.right
  const chartHeight = height - margin.top - margin.bottom

  let maxVal = 1.0
  data.forEach((d) => {
    EMOTIONS.forEach(({ key }) => {
      const val = d.emotions[key] || 0
      if (val > maxVal) maxVal = val
    })
  })
  maxVal = Math.ceil(maxVal * 1.2 * 10) / 10

  const groupWidth = chartWidth / EMOTIONS.length
  const barWidth = Math.min(22, (groupWidth * 0.75) / Math.max(1, data.length))

  return (
    <div style={{ position: 'relative', display: 'inline-block', width: '100%', maxWidth: `${width}px` }}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        style={{ width: '100%', height: 'auto', overflow: 'visible' }}
        role="img"
        aria-label="Plutchik Discrete Emotions Distribution"
      >
        <g transform={`translate(${margin.left}, ${margin.top})`}>
          {/* Horizontal grid lines */}
          {[0, 0.25, 0.5, 0.75, 1.0].map((frac) => {
            const y = chartHeight * (1 - frac)
            const val = (maxVal * frac).toFixed(1)
            return (
              <g key={frac}>
                <line
                  x1={0}
                  y1={y}
                  x2={chartWidth}
                  y2={y}
                  stroke="var(--border, #dcdde0)"
                  strokeDasharray={frac === 0 ? 'none' : '3 3'}
                  strokeWidth={frac === 0 ? 1.5 : 1}
                />
                <text
                  x={-8}
                  y={y + 4}
                  textAnchor="end"
                  fontSize={11}
                  fill="var(--muted, #666)"
                >
                  {val}
                </text>
              </g>
            )
          })}

          {/* Groups of bars */}
          {EMOTIONS.map((emo, eIdx) => {
            const groupX = eIdx * groupWidth
            const totalBarsWidth = data.length * barWidth + (data.length - 1) * 2
            const offset = (groupWidth - totalBarsWidth) / 2

            return (
              <g key={emo.key} transform={`translate(${groupX}, 0)`}>
                {data.map((langData, lIdx) => {
                  const val = langData.emotions[emo.key] || 0
                  const barH = (val / maxVal) * chartHeight
                  const x = offset + lIdx * (barWidth + 2)
                  const y = chartHeight - barH
                  const color = LANG_COLORS[langData.language] || '#636efa'

                  return (
                    <rect
                      key={langData.language}
                      x={x}
                      y={y}
                      width={barWidth}
                      height={barH}
                      fill={color}
                      rx={2}
                      style={{ cursor: 'pointer', transition: 'opacity 0.15s' }}
                      onMouseEnter={() => {
                        setHovered({
                          lang: langData.language_label,
                          emotion: emo.label,
                          value: val,
                          x: groupX + x + barWidth / 2 + margin.left,
                          y: y + margin.top,
                        })
                      }}
                      onMouseLeave={() => setHovered(null)}
                    />
                  )
                })}

                {/* X Axis Label */}
                <text
                  x={groupWidth / 2}
                  y={chartHeight + 22}
                  textAnchor="middle"
                  fontSize={12}
                  fontWeight={500}
                  fill="var(--text, #1f2328)"
                >
                  {emo.label}
                </text>
              </g>
            )
          })}
        </g>
      </svg>

      {/* Tooltip */}
      {hovered && (
        <div
          style={{
            position: 'absolute',
            left: `${(hovered.x / width) * 100}%`,
            top: hovered.y - 32,
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
          <strong>{hovered.lang}</strong>: {hovered.emotion} = {hovered.value.toFixed(2)} / 1k
        </div>
      )}

      {/* Legend */}
      <div style={{ display: 'flex', justifyContent: 'center', gap: '16px', marginTop: '8px' }}>
        {data.map((d) => (
          <div key={d.language} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px' }}>
            <span
              style={{
                display: 'inline-block',
                width: '12px',
                height: '12px',
                borderRadius: '2px',
                backgroundColor: LANG_COLORS[d.language] || '#636efa',
              }}
            />
            <span>{d.language_label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
