import { useEffect, useState } from 'react'
import {
  type FocusEventDetails,
  type FocusEventItem,
  getFocusEventDetails,
  getFocusEvents,
} from '../../api'
import { ErrorMessage } from '../Message'
import { GaugeChart } from './GaugeChart'

const FOUNDATION_LABELS: Record<string, string> = {
  care: 'Care',
  fairness: 'Fairness',
  loyalty: 'Loyalty',
  authority: 'Authority',
  sanctity: 'Sanctity',
}

export function FocusEventSection() {
  const [events, setEvents] = useState<FocusEventItem[]>([])
  const [selectedEventId, setSelectedEventId] = useState<string>('')
  const [windowDays, setWindowDays] = useState<number>(30)
  const [details, setDetails] = useState<FocusEventDetails | null>(null)
  const [loadingEvents, setLoadingEvents] = useState(true)
  const [loadingDetails, setLoadingDetails] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Load events list on mount
  useEffect(() => {
    let active = true
    getFocusEvents()
      .then((items) => {
        if (!active) return
        setEvents(items)
        if (items.length > 0) {
          // Default to 2020 COVID or first event
          const defaultEv = items.find((e) => e.date === '2020-03-10') || items[0]
          setSelectedEventId(defaultEv.date)
          setWindowDays(defaultEv.default_window)
        }
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        if (active) setLoadingEvents(false)
      })
    return () => {
      active = false
    }
  }, [])

  // Load details when selected event or window changes
  useEffect(() => {
    if (!selectedEventId) return
    let active = true
    setLoadingDetails(true)
    setError(null)
    getFocusEventDetails(selectedEventId, windowDays)
      .then((data) => {
        if (active) setDetails(data)
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        if (active) setLoadingDetails(false)
      })
    return () => {
      active = false
    }
  }, [selectedEventId, windowDays])

  if (loadingEvents) return <p className="result-count">Loading regional focus events…</p>

  const currentEvent = events.find((e) => e.date === selectedEventId)

  // SVG parameters for Moral Reconfiguration Bar Chart
  const foundations = ['care', 'fairness', 'loyalty', 'authority', 'sanctity']
  const maxMoral = details
    ? Math.max(
        ...foundations.map((f) => Math.max(details.pre_moral[f] || 0, details.post_moral[f] || 0)),
        10
      ) * 1.15
    : 20

  return (
    <div className="stack" style={{ gap: '24px' }}>
      {/* Event Selection & Window Slider */}
      <div
        className="card"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '16px',
          alignItems: 'center',
        }}
      >
        <div>
          <label htmlFor="focus-event-select" style={{ display: 'block', fontWeight: 600, marginBottom: '6px' }}>
            Historical Focus Event (Hurtado-Bodell & Menshikova 2026)
          </label>
          <select
            id="focus-event-select"
            value={selectedEventId}
            onChange={(e) => {
              const ev = events.find((item) => item.date === e.target.value)
              setSelectedEventId(e.target.value)
              if (ev) setWindowDays(ev.default_window)
            }}
            style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--border)' }}
          >
            {events.map((ev) => (
              <option key={ev.id} value={ev.date}>
                {ev.date} — {ev.title} ({ev.category})
              </option>
            ))}
          </select>
          {currentEvent && (
            <p style={{ fontSize: '13px', color: 'var(--muted)', marginTop: '6px' }}>
              {currentEvent.description}
            </p>
          )}
        </div>

        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
            <label htmlFor="window-slider" style={{ fontWeight: 600 }}>
              Analysis Window: ±{windowDays} Days
            </label>
            <span style={{ fontSize: '12px', color: 'var(--muted)' }}>Pre / Post Event</span>
          </div>
          <input
            id="window-slider"
            type="range"
            min={15}
            max={60}
            step={5}
            value={windowDays}
            onChange={(e) => setWindowDays(Number(e.target.value))}
            style={{ width: '100%' }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--muted)' }}>
            <span>±15d (Immediate)</span>
            <span>±30d (Standard)</span>
            <span>±60d (Longitudinal)</span>
          </div>
        </div>
      </div>

      {error && <ErrorMessage error={error} />}
      {loadingDetails && <p className="result-count">Analyzing pre/post event framing shifts…</p>}

      {details && (
        <>
          {/* KPI Summary Cards */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: '16px',
            }}
          >
            <div className="card" style={{ padding: '16px', textAlign: 'center' }}>
              <div style={{ fontSize: '12px', color: 'var(--muted)', fontWeight: 600 }}>ARTICLE VOLUME</div>
              <div style={{ fontSize: '24px', fontWeight: 700, margin: '4px 0' }}>
                {details.pre_count} → {details.post_count}
              </div>
              <div
                style={{
                  fontSize: '12px',
                  fontWeight: 600,
                  color: details.pct_surge >= 0 ? '#1f6f43' : '#a32a2a',
                }}
              >
                {details.pct_surge >= 0 ? `+${details.pct_surge}%` : `${details.pct_surge}%`} surge
              </div>
            </div>

            <div className="card" style={{ padding: '16px', textAlign: 'center' }}>
              <div style={{ fontSize: '12px', color: 'var(--muted)', fontWeight: 600 }}>NET SENTIMENT SHIFT</div>
              <div style={{ fontSize: '24px', fontWeight: 700, margin: '4px 0' }}>
                {details.pre_sentiment >= 0 ? `+${details.pre_sentiment}` : details.pre_sentiment} →{' '}
                {details.post_sentiment >= 0 ? `+${details.post_sentiment}` : details.post_sentiment}
              </div>
              <div
                style={{
                  fontSize: '12px',
                  fontWeight: 600,
                  color: details.delta_sentiment >= 0 ? '#1f6f43' : '#a32a2a',
                }}
              >
                Δ {details.delta_sentiment >= 0 ? `+${details.delta_sentiment}` : details.delta_sentiment}
              </div>
            </div>

            <div className="card" style={{ padding: '16px', textAlign: 'center' }}>
              <div style={{ fontSize: '12px', color: 'var(--muted)', fontWeight: 600 }}>PRIMARY DIVERGENCE</div>
              <div style={{ fontSize: '22px', fontWeight: 700, margin: '4px 0', textTransform: 'capitalize' }}>
                {details.moral_divergence?.primary_divergence_foundation || 'None'}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--muted)' }}>Max moral reconfiguration</div>
            </div>

            <div className="card" style={{ padding: '12px', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
              <GaugeChart value={details.moral_divergence?.jsd || 0} />
            </div>
          </div>

          {/* Moral Reconfiguration Grouped Bar Chart & Keyness Table */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))',
              gap: '20px',
            }}
          >
            {/* Moral Reconfiguration Bar Chart */}
            <div className="card" style={{ padding: '20px' }}>
              <h3 style={{ margin: '0 0 12px', fontSize: '16px' }}>
                Moral Framing Reconfiguration (Tokens / 1k Words)
              </h3>
              <p style={{ fontSize: '12px', color: 'var(--muted)', margin: '0 0 16px' }}>
                Pre-window ({details.pre_period}) vs. Post-window ({details.post_period})
              </p>

              <svg viewBox="0 0 460 260" style={{ width: '100%', height: 'auto', overflow: 'visible' }}>
                <g transform="translate(45, 15)">
                  {/* Y grid lines */}
                  {[0, 0.25, 0.5, 0.75, 1.0].map((frac) => {
                    const y = 200 * (1 - frac)
                    return (
                      <g key={frac}>
                        <line x1={0} y1={y} x2={390} y2={y} stroke="var(--border)" strokeDasharray="3 3" />
                        <text x={-6} y={y + 4} textAnchor="end" fontSize={10} fill="var(--muted)">
                          {(maxMoral * frac).toFixed(1)}
                        </text>
                      </g>
                    )
                  })}

                  {/* Bars for each foundation */}
                  {foundations.map((f, idx) => {
                    const groupX = idx * (390 / foundations.length)
                    const preVal = details.pre_moral[f] || 0
                    const postVal = details.post_moral[f] || 0
                    const preH = (preVal / maxMoral) * 200
                    const postH = (postVal / maxMoral) * 200

                    return (
                      <g key={f} transform={`translate(${groupX + 12}, 0)`}>
                        {/* Pre bar */}
                        <rect x={0} y={200 - preH} width={22} height={preH} fill="#718096" rx={2} />
                        {/* Post bar */}
                        <rect x={26} y={200 - postH} width={22} height={postH} fill="#dd6b20" rx={2} />
                        {/* Label */}
                        <text x={24} y={218} textAnchor="middle" fontSize={11} fontWeight={600} fill="var(--text)">
                          {FOUNDATION_LABELS[f]}
                        </text>
                      </g>
                    )
                  })}
                </g>
              </svg>

              <div style={{ display: 'flex', justifyContent: 'center', gap: '20px', marginTop: '12px', fontSize: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ width: '12px', height: '12px', backgroundColor: '#718096', borderRadius: '2px' }} />
                  <span>Pre-Event Window</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ width: '12px', height: '12px', backgroundColor: '#dd6b20', borderRadius: '2px' }} />
                  <span>Post-Event Window</span>
                </div>
              </div>
            </div>

            {/* Differential Keyness Table (Top Post-Event Terms) */}
            <div className="card" style={{ padding: '20px' }}>
              <h3 style={{ margin: '0 0 8px', fontSize: '16px' }}>
                Distinctive Post-Event Discourse (Dunning G²)
              </h3>
              <p style={{ fontSize: '12px', color: 'var(--muted)', margin: '0 0 14px' }}>
                Vocabulary statistically overrepresented after the focus event
              </p>

              {details.keyness.length === 0 ? (
                <p className="result-count">Insufficient word tokens for differential keyness.</p>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table className="table" style={{ width: '100%', fontSize: '13px' }}>
                    <thead>
                      <tr>
                        <th style={{ textAlign: 'left' }}>Term</th>
                        <th style={{ textAlign: 'right' }}>Dunning G²</th>
                        <th style={{ textAlign: 'right' }}>Post Rate (/1k)</th>
                        <th style={{ textAlign: 'right' }}>Pre Rate (/1k)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {details.keyness.slice(0, 10).map((k) => (
                        <tr key={k.term}>
                          <td style={{ fontWeight: 600 }}>{k.term}</td>
                          <td style={{ textAlign: 'right', color: k.g2 > 0 ? '#1f5f8b' : '#a32a2a', fontWeight: 600 }}>
                            {k.g2.toFixed(1)}
                          </td>
                          <td style={{ textAlign: 'right' }}>{k.target_per_1k.toFixed(2)}</td>
                          <td style={{ textAlign: 'right', color: 'var(--muted)' }}>{k.ref_per_1k.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

