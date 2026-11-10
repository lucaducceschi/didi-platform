import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router'
import type { WordBubbleItem } from '../api'

interface LexicalDossierModalProps {
  item: WordBubbleItem | null
  onClose: () => void
}

export function LexicalDossierModal({ item, onClose }: LexicalDossierModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    const el = dialogRef.current
    if (!el) return
    if (item && !el.open) {
      el.showModal()
    } else if (!item && el.open) {
      el.close()
    }
  }, [item])

  if (!item) return null

  const dePct = Math.round(item.de_ratio * 100)
  const itPct = Math.round(item.it_ratio * 100)
  const journPct = Math.round(item.journalism_ratio * 100)
  const pressPct = Math.round(item.official_press_ratio * 100)

  // Sparkline coordinates for 10-year trend (2016-2025)
  const sparkWidth = 420
  const sparkHeight = 65
  const maxVal = Math.max(...item.yearly_trend, 1)
  const points = item.yearly_trend.map((val, idx) => {
    const x = Math.round((idx / (item.yearly_trend.length - 1)) * (sparkWidth - 20) + 10)
    const y = Math.round(sparkHeight - 10 - (val / maxVal) * (sparkHeight - 20))
    return { x, y, val, year: item.years[idx] }
  })
  const pathD = points.reduce(
    (acc, pt, i) => `${acc} ${i === 0 ? 'M' : 'L'} ${pt.x} ${pt.y}`,
    ''
  )
  const areaD = `${pathD} L ${points[points.length - 1].x} ${sparkHeight - 5} L ${points[0].x} ${sparkHeight - 5} Z`

  const handleSearchTerm = (searchTerm: string) => {
    onClose()
    navigate(`/search?q=${encodeURIComponent(searchTerm)}`)
  }

  const handleAnalyticsTerm = (searchTerm: string) => {
    onClose()
    navigate(`/analytics?q=${encodeURIComponent(searchTerm)}`)
  }

  return (
    <dialog
      ref={dialogRef}
      className="dialog"
      onCancel={(e) => {
        e.preventDefault()
        onClose()
      }}
      style={{
        maxWidth: '560px',
        width: '92%',
        borderRadius: '10px',
        padding: '0',
        border: '1px solid var(--border)',
        boxShadow: '0 12px 32px rgba(0, 0, 0, 0.22)',
        background: 'var(--surface)',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '18px 24px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: '12px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <h2 style={{ margin: 0, fontSize: '22px', fontWeight: 700 }}>
              {item.term}
            </h2>
            {item.twin_term && item.twin_term !== item.term && (
              <span style={{ fontSize: '16px', color: 'var(--muted)', fontStyle: 'italic' }}>
                / {item.twin_term}
              </span>
            )}
            <span
              style={{
                fontSize: '11px',
                fontWeight: 600,
                padding: '2px 8px',
                borderRadius: '12px',
                backgroundColor: item.category_color + '22',
                color: item.category_color,
                border: `1px solid ${item.category_color}44`,
              }}
            >
              {item.category}
            </span>
          </div>
          <div style={{ display: 'flex', gap: '8px', marginTop: '6px', fontSize: '12px' }}>
            <span className="tag">
              ⚖️ Moral: <strong>{item.primary_moral}</strong>
            </span>
            <span
              className="tag"
              style={{
                color: item.sentiment >= 0 ? 'var(--ok, #2e7d32)' : 'var(--error-text, #c53030)',
              }}
            >
              Sentiment: <strong>{item.sentiment > 0 ? `+${item.sentiment.toFixed(2)}` : item.sentiment.toFixed(2)}</strong>
            </span>
          </div>
        </div>

        <button
          type="button"
          onClick={onClose}
          aria-label="Close dialog"
          style={{
            background: 'none',
            border: 'none',
            fontSize: '20px',
            lineHeight: 1,
            cursor: 'pointer',
            color: 'var(--muted)',
            padding: '4px',
          }}
        >
          ✕
        </button>
      </div>

      {/* Dialog Body */}
      <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
        {/* Ratios & Telemetry */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
          {/* Language Balance */}
          <div
            style={{
              padding: '12px',
              borderRadius: '8px',
              background: 'var(--canvas-subtle, rgba(0,0,0,0.02))',
              border: '1px solid var(--border)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '6px' }}>
              <span style={{ color: 'var(--muted)' }}>Language Ratio</span>
              <strong>🇩🇪 {dePct}% · 🇮🇹 {itPct}%</strong>
            </div>
            <div
              style={{
                height: '8px',
                borderRadius: '4px',
                overflow: 'hidden',
                display: 'flex',
                background: 'var(--border)',
              }}
            >
              <div style={{ width: `${dePct}%`, background: '#3182ce' }} title={`German: ${dePct}%`} />
              <div style={{ width: `${itPct}%`, background: '#38a169' }} title={`Italian: ${itPct}%`} />
            </div>
          </div>

          {/* Discourse Type Balance */}
          <div
            style={{
              padding: '12px',
              borderRadius: '8px',
              background: 'var(--canvas-subtle, rgba(0,0,0,0.02))',
              border: '1px solid var(--border)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '6px' }}>
              <span style={{ color: 'var(--muted)' }}>Discourse Source</span>
              <strong>🗞️ {journPct}% · 🏛️ {pressPct}%</strong>
            </div>
            <div
              style={{
                height: '8px',
                borderRadius: '4px',
                overflow: 'hidden',
                display: 'flex',
                background: 'var(--border)',
              }}
            >
              <div style={{ width: `${journPct}%`, background: '#805ad5' }} title={`Journalism: ${journPct}%`} />
              <div style={{ width: `${pressPct}%`, background: '#dd6b20' }} title={`Official Press: ${pressPct}%`} />
            </div>
          </div>
        </div>

        {/* 10-Year Longitudinal Trend (2016-2025) */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '6px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--muted)' }}>
              10-YEAR LONGITUDINAL TRAJECTORY (2016–2025)
            </span>
            <span style={{ fontSize: '12px', color: 'var(--muted)' }}>
              Total: <strong>{item.count.toLocaleString()}</strong> mentions
            </span>
          </div>

          <div
            style={{
              background: 'var(--canvas-subtle, rgba(0,0,0,0.02))',
              borderRadius: '8px',
              border: '1px solid var(--border)',
              padding: '10px 14px 6px',
            }}
          >
            <svg
              viewBox={`0 0 ${sparkWidth} ${sparkHeight}`}
              style={{ width: '100%', height: '65px', display: 'block', overflow: 'visible' }}
            >
              {/* Fill Area */}
              <path
                d={areaD}
                fill={item.category_color}
                fillOpacity={0.15}
              />
              {/* Sparkline Stroke */}
              <path
                d={pathD}
                fill="none"
                stroke={item.category_color}
                strokeWidth={2.5}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              {/* Data points */}
              {points.map((pt) => (
                <g key={pt.year}>
                  <circle
                    cx={pt.x}
                    cy={pt.y}
                    r={3}
                    fill="var(--surface)"
                    stroke={item.category_color}
                    strokeWidth={2}
                  >
                    <title>{`${pt.year}: ${pt.val.toLocaleString()} articles`}</title>
                  </circle>
                  <text
                    x={pt.x}
                    y={sparkHeight + 4}
                    textAnchor="middle"
                    fontSize="9"
                    fill="var(--muted)"
                  >
                    {pt.year.slice(2)}
                  </text>
                </g>
              ))}
            </svg>
          </div>
        </div>

        {/* Collocates & Framing Context */}
        {item.collocates && item.collocates.length > 0 && (
          <div>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--muted)', display: 'block', marginBottom: '6px' }}>
              KEY REGIONAL COLLOCATES
            </span>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {item.collocates.map((col) => (
                <button
                  key={col}
                  type="button"
                  className="tag"
                  onClick={() => handleSearchTerm(`${item.term} ${col}`)}
                  style={{
                    cursor: 'pointer',
                    background: 'var(--surface)',
                    border: '1px solid var(--border)',
                    fontSize: '12px',
                    padding: '3px 8px',
                  }}
                  title={`Search corpus for "${item.term} ${col}"`}
                >
                  +{col}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Representative Regional Excerpt */}
        {item.sample_snippet && (
          <div>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--muted)', display: 'block', marginBottom: '6px' }}>
              REPRESENTATIVE REGIONAL EXCERPT
            </span>
            <blockquote
              style={{
                margin: 0,
                padding: '10px 14px',
                borderLeft: `3px solid ${item.category_color}`,
                background: 'var(--canvas-subtle, rgba(0,0,0,0.02))',
                borderRadius: '0 6px 6px 0',
                fontSize: '13px',
                lineHeight: 1.5,
                color: 'var(--text)',
                fontStyle: 'italic',
                cursor: 'pointer',
              }}
              onClick={() => {
                onClose()
                navigate(`/search?q=${encodeURIComponent(item.term)}&view=kwic`)
              }}
              title="Click to view KWIC concordance for this term"
            >
              &ldquo;{item.sample_snippet}&rdquo;
            </blockquote>
          </div>
        )}
      </div>

      {/* Actions Footer */}
      <div
        className="dialog-actions"
        style={{
          padding: '14px 24px',
          borderTop: '1px solid var(--border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '10px',
        }}
      >
        <button type="button" className="button-quiet" onClick={onClose} style={{ fontSize: '13px' }}>
          Close
        </button>

        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            type="button"
            className="button-quiet"
            onClick={() => handleAnalyticsTerm(item.term)}
            style={{ fontSize: '13px' }}
          >
            📊 Media Radar
          </button>
          <button
            type="button"
            className="button-secondary"
            onClick={() => {
              onClose()
              navigate(`/search?q=${encodeURIComponent(item.term)}&view=kwic`)
            }}
            style={{ fontSize: '13px' }}
          >
            🔍 KWIC Concordance
          </button>
          <button
            type="button"
            className="button"
            onClick={() => handleSearchTerm(item.term)}
            style={{ fontSize: '13px' }}
          >
            📄 Search Articles ({item.count.toLocaleString()})
          </button>
        </div>
      </div>
    </dialog>
  )
}

