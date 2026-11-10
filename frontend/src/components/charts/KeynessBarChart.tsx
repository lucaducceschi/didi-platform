import type { KeynessItem } from '../../api'

interface KeynessBarChartProps {
  items: KeynessItem[]
  targetLabel?: string
  refLabel?: string
  width?: number
}

export function KeynessBarChart({
  items,
  targetLabel = 'Target Language',
  refLabel = 'Reference Language',
  width = 640,
}: KeynessBarChartProps) {
  if (items.length === 0) {
    return <p className="result-count">No distinctive vocabulary found for this selection.</p>
  }

  // Sort by signed g2 ascending so top positive terms are at the top
  const sorted = [...items].sort((a, b) => b.g2 - a.g2)
  const maxAbsG2 = Math.max(...items.map((i) => Math.abs(i.g2)), 10)

  const rowHeight = 28
  const height = sorted.length * rowHeight + 60
  const margin = { top: 30, right: 90, bottom: 20, left: 110 }
  const chartWidth = width - margin.left - margin.right
  const midX = chartWidth / 2

  return (
    <div style={{ width: '100%', maxWidth: `${width}px` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '8px', padding: '0 8px' }}>
        <span style={{ color: '#c53030', fontWeight: 600 }}>← Overused in {refLabel}</span>
        <span style={{ color: '#1f5f8b', fontWeight: 600 }}>Overused in {targetLabel} →</span>
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        style={{ width: '100%', height: 'auto', overflow: 'visible' }}
        role="img"
        aria-label="Differential Keyness Bar Chart"
      >
        <g transform={`translate(${margin.left}, ${margin.top})`}>
          {/* Zero center line */}
          <line
            x1={midX}
            y1={0}
            x2={midX}
            y2={sorted.length * rowHeight}
            stroke="var(--muted, #888)"
            strokeWidth={1.5}
          />

          {sorted.map((item, idx) => {
            const y = idx * rowHeight
            const isPositive = item.g2 >= 0
            const barLength = (Math.abs(item.g2) / maxAbsG2) * (chartWidth / 2)
            const x = isPositive ? midX : midX - barLength
            const color = isPositive ? '#1f5f8b' : '#c53030'

            return (
              <g key={item.term} transform={`translate(0, ${y})`}>
                {/* Term label */}
                <text
                  x={-10}
                  y={rowHeight / 2 + 4}
                  textAnchor="end"
                  fontSize={12}
                  fontWeight={600}
                  fill="var(--text, #1f2328)"
                >
                  {item.term}
                </text>

                {/* Bar */}
                <rect
                  x={x}
                  y={4}
                  width={Math.max(2, barLength)}
                  height={rowHeight - 8}
                  fill={color}
                  rx={2}
                />

                {/* Score text */}
                <text
                  x={isPositive ? midX + barLength + 6 : midX - barLength - 6}
                  y={rowHeight / 2 + 4}
                  textAnchor={isPositive ? 'start' : 'end'}
                  fontSize={11}
                  fontWeight={500}
                  fill="var(--muted, #666)"
                >
                  {Math.abs(item.g2).toFixed(1)} (G²)
                </text>
              </g>
            )
          })}
        </g>
      </svg>
    </div>
  )
}

