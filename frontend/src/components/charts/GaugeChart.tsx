interface GaugeChartProps {
  value: number
  title?: string
  width?: number
  height?: number
}

export function GaugeChart({
  value,
  title = 'Moral Framing Divergence (JSD)',
  width = 240,
  height = 145,
}: GaugeChartProps) {
  const cx = width / 2
  const cy = height - 25
  const radius = Math.min(cx - 20, cy - 15)

  // JSD is mathematically between 0.0 and 1.0.
  const clampedVal = Math.max(0, Math.min(1, value))

  // Piecewise scaling:
  // Maps [0.0, 0.10] to 0..0.33 of the dial (High Alignment)
  // Maps [0.10, 0.25] to 0.33..0.67 of the dial (Moderate Gap)
  // Maps [0.25, 1.00] to 0.67..1.00 of the dial (Substantial Divergence)
  let dialFraction = 0
  if (clampedVal <= 0.1) {
    dialFraction = (clampedVal / 0.1) * (1 / 3)
  } else if (clampedVal <= 0.25) {
    dialFraction = 1 / 3 + ((clampedVal - 0.1) / 0.15) * (1 / 3)
  } else {
    dialFraction = 2 / 3 + ((clampedVal - 0.25) / 0.75) * (1 / 3)
  }

  // Dial sweeps 210 degrees: from 195° (7π/12 rad) on the left down to -15° (-π/12 rad) on the right
  const startAngleDeg = 195
  const sweepDeg = 210
  const needleAngleDeg = startAngleDeg - dialFraction * sweepDeg
  const needleRad = (needleAngleDeg * Math.PI) / 180

  const toRad = (deg: number) => (deg * Math.PI) / 180

  // Creates an SVG arc segment given start and end fractions [0..1] of the 210° dial
  const makeArc = (startFrac: number, endFrac: number) => {
    const a1Deg = startAngleDeg - startFrac * sweepDeg
    const a2Deg = startAngleDeg - endFrac * sweepDeg
    const a1 = toRad(a1Deg)
    const a2 = toRad(a2Deg)
    const x1 = cx + radius * Math.cos(a1)
    const y1 = cy - radius * Math.sin(a1)
    const x2 = cx + radius * Math.cos(a2)
    const y2 = cy - radius * Math.sin(a2)
    // Semicircle segments (< 180°) always have largeArc = 0 and sweep = 1 (clockwise)
    return `M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${radius} ${radius} 0 0 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`
  }

  // Needle tip
  const needleLen = radius - 8
  const tipX = cx + needleLen * Math.cos(needleRad)
  const tipY = cy - needleLen * Math.sin(needleRad)

  // Needle base perpendicular corners (tapered pointer)
  const baseWidth = 4
  const perpRad = needleRad + Math.PI / 2
  const p1X = cx + baseWidth * Math.cos(perpRad)
  const p1Y = cy - baseWidth * Math.sin(perpRad)
  const p2X = cx - baseWidth * Math.cos(perpRad)
  const p2Y = cy - baseWidth * Math.sin(perpRad)

  const label =
    clampedVal < 0.1
      ? 'High Framing Alignment'
      : clampedVal < 0.25
        ? 'Moderate Framing Divergence'
        : 'Substantially Divergent Framing'

  const labelColor = clampedVal < 0.1 ? '#1f6f43' : clampedVal < 0.25 ? '#b7791f' : '#c53030'

  return (
    <div style={{ textAlign: 'center', display: 'inline-block' }}>
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={title}
      >
        {/* Background track */}
        <path
          d={makeArc(0, 1)}
          fill="none"
          stroke="var(--border-subtle, rgba(0,0,0,0.06))"
          strokeWidth={14}
        />

        {/* 3 Threshold Zones (Equal 70° visual presence) */}
        {/* Zone 1: High Alignment (0 to 0.10) */}
        <path
          d={makeArc(0, 1 / 3)}
          fill="none"
          stroke="#48bb78"
          strokeWidth={12}
          strokeLinecap="round"
        />
        {/* Zone 2: Moderate Gap (0.10 to 0.25) */}
        <path
          d={makeArc(1 / 3, 2 / 3)}
          fill="none"
          stroke="#ed8936"
          strokeWidth={12}
        />
        {/* Zone 3: Divergence (0.25 to 1.0) */}
        <path
          d={makeArc(2 / 3, 1)}
          fill="none"
          stroke="#f56565"
          strokeWidth={12}
          strokeLinecap="round"
        />

        {/* Needle pointer */}
        <polygon
          points={`${p1X.toFixed(2)},${p1Y.toFixed(2)} ${tipX.toFixed(2)},${tipY.toFixed(2)} ${p2X.toFixed(2)},${p2Y.toFixed(2)}`}
          fill="var(--text, #1f2328)"
        />
        <circle cx={cx} cy={cy} r={5} fill="var(--text, #1f2328)" />
        <circle cx={cx} cy={cy} r={2} fill="var(--canvas, #ffffff)" />

        {/* Value text in center */}
        <text
          x={cx}
          y={cy - 24}
          textAnchor="middle"
          fontSize={20}
          fontWeight={700}
          fill="var(--text, #1f2328)"
        >
          {value.toFixed(3)}
        </text>
        <text
          x={cx}
          y={cy - 8}
          textAnchor="middle"
          fontSize={11}
          fill="var(--muted, #666)"
        >
          JSD Index (0–1)
        </text>
      </svg>
      <div style={{ fontSize: '12px', fontWeight: 600, color: labelColor, marginTop: '-6px' }}>
        {label}
      </div>
    </div>
  )
}
