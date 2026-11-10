import { useEffect, useState } from 'react'
import {
  type KeynessItem,
  type RadarAnalyticsResponse,
  type TimelineAnalyticsResponse,
  getCrossLingualKeyness,
  getRadarAnalytics,
  getTimelineAnalytics,
} from '../api'
import { EmotionBarChart } from '../components/charts/EmotionBarChart'
import { FocusEventSection } from '../components/charts/FocusEventSection'
import { GaugeChart } from '../components/charts/GaugeChart'
import { KeynessBarChart } from '../components/charts/KeynessBarChart'
import { RadarChart } from '../components/charts/RadarChart'
import { TimelineChart } from '../components/charts/TimelineChart'
import { ErrorMessage } from '../components/Message'

type AnalyticsTab = 'radar' | 'timeline' | 'events' | 'keyness'

export function CorpusAnalyticsPage() {
  const [activeTab, setActiveTab] = useState<AnalyticsTab>('radar')

  // Search & filter state
  const [query, setQuery] = useState('')
  const [appliedQuery, setAppliedQuery] = useState('')
  const [selectedLangs, setSelectedLangs] = useState<string[]>(['de', 'it'])
  const [selectedSources, setSelectedSources] = useState<string[]>([])

  // Radar data state
  const [radarData, setRadarData] = useState<RadarAnalyticsResponse | null>(null)
  const [loadingRadar, setLoadingRadar] = useState(false)
  const [radarError, setRadarError] = useState<string | null>(null)

  // Timeline data state
  const [timelineData, setTimelineData] = useState<TimelineAnalyticsResponse | null>(null)
  const [timelineMetric, setTimelineMetric] = useState<'avg_sentiment' | 'avg_moral_density'>('avg_sentiment')
  const [loadingTimeline, setLoadingTimeline] = useState(false)
  const [timelineError, setTimelineError] = useState<string | null>(null)

  // Keyness data state
  const [keynessTarget, setKeynessTarget] = useState('de')
  const [keynessRef, setKeynessRef] = useState('it')
  const [keynessData, setKeynessData] = useState<KeynessItem[]>([])
  const [loadingKeyness, setLoadingKeyness] = useState(false)
  const [keynessError, setKeynessError] = useState<string | null>(null)

  // Fetch Radar data
  useEffect(() => {
    let active = true
    setLoadingRadar(true)
    setRadarError(null)
    getRadarAnalytics({
      q: appliedQuery,
      languages: selectedLangs.length > 0 ? selectedLangs : undefined,
      sources: selectedSources.length > 0 ? selectedSources : undefined,
    })
      .then((res) => {
        if (active) setRadarData(res)
      })
      .catch((err) => {
        if (active) setRadarError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        if (active) setLoadingRadar(false)
      })
    return () => {
      active = false
    }
  }, [appliedQuery, selectedLangs, selectedSources])

  // Fetch Timeline data
  useEffect(() => {
    let active = true
    setLoadingTimeline(true)
    setTimelineError(null)
    getTimelineAnalytics({
      q: appliedQuery,
      languages: selectedLangs.length > 0 ? selectedLangs : undefined,
      sources: selectedSources.length > 0 ? selectedSources : undefined,
    })
      .then((res) => {
        if (active) setTimelineData(res)
      })
      .catch((err) => {
        if (active) setTimelineError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        if (active) setLoadingTimeline(false)
      })
    return () => {
      active = false
    }
  }, [appliedQuery, selectedLangs, selectedSources])

  // Fetch Cross-Lingual Keyness data
  useEffect(() => {
    let active = true
    setLoadingKeyness(true)
    setKeynessError(null)
    getCrossLingualKeyness(keynessTarget, keynessRef, appliedQuery, selectedSources.length > 0 ? selectedSources : undefined, 15)
      .then((res) => {
        if (active) setKeynessData(res)
      })
      .catch((err) => {
        if (active) setKeynessError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        if (active) setLoadingKeyness(false)
      })
    return () => {
      active = false
    }
  }, [appliedQuery, selectedSources, keynessTarget, keynessRef])

  const handleApplyFilters = (e: React.FormEvent) => {
    e.preventDefault()
    setAppliedQuery(query.trim())
  }

  const toggleLanguage = (lang: string) => {
    setSelectedLangs((prev) =>
      prev.includes(lang) ? (prev.length > 1 ? prev.filter((l) => l !== lang) : prev) : [...prev, lang]
    )
  }

  const toggleSource = (src: string) => {
    setSelectedSources((prev) =>
      prev.includes(src) ? prev.filter((s) => s !== src) : [...prev, src]
    )
  }

  return (
    <div className="stack" style={{ gap: '24px' }}>
      <div>
        <h1 style={{ margin: '0 0 6px', fontSize: '26px' }}>Macro Corpus Analytics</h1>
        <p style={{ color: 'var(--muted)', margin: 0, fontSize: '14px' }}>
          Quantitative media framing, longitudinal discourse trajectories, and event meaning-making across South Tyrolean regional press (113k+ articles, 2017–2026).
        </p>
      </div>

      {/* Global Filter Bar */}
      <form onSubmit={handleApplyFilters} className="card" style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', alignItems: 'center' }}>
        <div style={{ flex: '1 1 260px' }}>
          <label htmlFor="analytics-search" style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--muted)', marginBottom: '4px' }}>
            TOPIC / FTS5 KEYWORD FILTER (TRILINGUAL BRIDGE)
          </label>
          <input
            id="analytics-search"
            type="search"
            placeholder="e.g. Autonomie, Schule, Wolf, Sanità, Brenner…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border)' }}
          />
        </div>

        <div>
          <span style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--muted)', marginBottom: '6px' }}>
            LANGUAGES
          </span>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              className={selectedLangs.includes('de') ? 'button' : 'button-quiet'}
              onClick={() => toggleLanguage('de')}
              style={{ fontSize: '12px', padding: '6px 12px' }}
            >
              🇩🇪 German (de)
            </button>
            <button
              type="button"
              className={selectedLangs.includes('it') ? 'button' : 'button-quiet'}
              onClick={() => toggleLanguage('it')}
              style={{ fontSize: '12px', padding: '6px 12px' }}
            >
              🇮🇹 Italian (it)
            </button>
          </div>
        </div>

        <div>
          <span style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--muted)', marginBottom: '6px' }}>
            OUTLETS
          </span>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            <button
              type="button"
              className={selectedSources.includes('tageszeitung') ? 'button' : 'button-quiet'}
              onClick={() => toggleSource('tageszeitung')}
              style={{ fontSize: '12px', padding: '6px 10px' }}
            >
              Tageszeitung
            </button>
            <button
              type="button"
              className={selectedSources.includes('salto') ? 'button' : 'button-quiet'}
              onClick={() => toggleSource('salto')}
              style={{ fontSize: '12px', padding: '6px 10px' }}
            >
              Salto.bz
            </button>
            <button
              type="button"
              className={selectedSources.includes('provinz') ? 'button' : 'button-quiet'}
              onClick={() => toggleSource('provinz')}
              style={{ fontSize: '12px', padding: '6px 10px' }}
            >
              Landespresseamt
            </button>
          </div>
        </div>

        <div style={{ alignSelf: 'flex-end' }}>
          <button type="submit" className="button" style={{ padding: '8px 16px' }}>
            Filter Discourse
          </button>
          {appliedQuery && (
            <button
              type="button"
              className="button-quiet"
              onClick={() => {
                setQuery('')
                setAppliedQuery('')
              }}
              style={{ marginLeft: '8px', fontSize: '13px' }}
            >
              Reset
            </button>
          )}
        </div>
      </form>

      {/* Section Tabs Navigation */}
      <nav className="tabs" aria-label="Analytics Views">
        <button
          type="button"
          className={activeTab === 'radar' ? 'tab-active' : ''}
          onClick={() => setActiveTab('radar')}
          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '8px 16px', fontWeight: activeTab === 'radar' ? 600 : 400 }}
        >
          🕸️ Moral Framing Radar & Emotions
        </button>
        <button
          type="button"
          className={activeTab === 'timeline' ? 'tab-active' : ''}
          onClick={() => setActiveTab('timeline')}
          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '8px 16px', fontWeight: activeTab === 'timeline' ? 600 : 400 }}
        >
          📈 Longitudinal Discourse Dynamics
        </button>
        <button
          type="button"
          className={activeTab === 'events' ? 'tab-active' : ''}
          onClick={() => setActiveTab('events')}
          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '8px 16px', fontWeight: activeTab === 'events' ? 600 : 400 }}
        >
          ⚡ Focus Events & Meaning-Making
        </button>
        <button
          type="button"
          className={activeTab === 'keyness' ? 'tab-active' : ''}
          onClick={() => setActiveTab('keyness')}
          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '8px 16px', fontWeight: activeTab === 'keyness' ? 600 : 400 }}
        >
          ⚖️ Cross-Lingual Keyness (G²)
        </button>
      </nav>

      {/* Tab 1: Moral Framing Radar & Plutchik Emotions */}
      {activeTab === 'radar' && (
        <div className="stack" style={{ gap: '24px' }}>
          {radarError && <ErrorMessage error={radarError} />}
          {loadingRadar && <p className="result-count">Calculating Moral Foundations & discrete emotions…</p>}

          {radarData && (
            <>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
                  gap: '24px',
                  alignItems: 'start',
                }}
              >
                {/* 5-Axis Radar Chart Card */}
                <div className="card" style={{ padding: '20px', textAlign: 'center' }}>
                  <h2 style={{ fontSize: '18px', margin: '0 0 4px' }}>
                    Moral Foundations Framing Radar
                  </h2>
                  <p style={{ fontSize: '12px', color: 'var(--muted)', margin: '0 0 16px' }}>
                    Density of Moral Foundations dictionary lemmas per 1,000 words (MFD 2.0)
                  </p>
                  <div style={{ display: 'flex', justifyContent: 'center' }}>
                    <RadarChart data={radarData.languages} size={420} />
                  </div>
                </div>

                {/* Framing Divergence & Valence Card */}
                <div className="stack" style={{ gap: '16px' }}>
                  <div className="card" style={{ padding: '20px' }}>
                    <h2 style={{ fontSize: '18px', margin: '0 0 12px' }}>
                      Pairwise Moral Framing Divergence (JSD)
                    </h2>
                    <p style={{ fontSize: '13px', color: 'var(--muted)', margin: '0 0 16px' }}>
                      Jensen-Shannon Divergence quantifying the distance between language communities' moral framing profiles.
                    </p>

                    {Object.entries(radarData.pairwise_jsd).length === 0 ? (
                      <p className="result-count">Select at least two languages to compute pairwise divergence.</p>
                    ) : (
                      <div className="stack" style={{ gap: '16px' }}>
                        {Object.entries(radarData.pairwise_jsd).map(([pair, jsdInfo]) => (
                          <div
                            key={pair}
                            style={{
                              border: '1px solid var(--border)',
                              borderRadius: '8px',
                              padding: '12px 16px',
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                            }}
                          >
                            <div>
                              <div style={{ fontWeight: 600, fontSize: '15px' }}>{pair.replace('_vs_', ' vs ')}</div>
                              <div style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '2px' }}>
                                Primary divergence axis:{' '}
                                <strong style={{ textTransform: 'capitalize', color: 'var(--text)' }}>
                                  {jsdInfo.primary_divergence_foundation || 'None'}
                                </strong>
                              </div>
                            </div>
                            <div style={{ textAlign: 'right' }}>
                              <GaugeChart value={jsdInfo.jsd} width={180} height={110} />
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Summary metrics table */}
                  <div className="card" style={{ padding: '20px' }}>
                    <h3 style={{ fontSize: '16px', margin: '0 0 12px' }}>Language Community Sentiment & Morality</h3>
                    <div style={{ overflowX: 'auto' }}>
                      <table className="table" style={{ width: '100%', fontSize: '13px' }}>
                        <thead>
                          <tr>
                            <th style={{ textAlign: 'left' }}>Language</th>
                            <th style={{ textAlign: 'right' }}>Articles</th>
                            <th style={{ textAlign: 'right' }}>Net Sentiment</th>
                            <th style={{ textAlign: 'right' }}>Moral Density (/1k)</th>
                          </tr>
                        </thead>
                        <tbody>
                          {radarData.languages.map((l) => (
                            <tr key={l.language}>
                              <td style={{ fontWeight: 600 }}>{l.language_label}</td>
                              <td style={{ textAlign: 'right' }}>{l.article_count.toLocaleString()}</td>
                              <td
                                style={{
                                  textAlign: 'right',
                                  fontWeight: 600,
                                  color: l.net_sentiment >= 0 ? '#1f6f43' : '#a32a2a',
                                }}
                              >
                                {l.net_sentiment >= 0 ? `+${l.net_sentiment}` : l.net_sentiment}
                              </td>
                              <td style={{ textAlign: 'right' }}>{l.moral_density.toFixed(2)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </div>

              {/* Plutchik Discrete Emotions Bar Chart */}
              <div className="card" style={{ padding: '24px' }}>
                <h2 style={{ fontSize: '18px', margin: '0 0 4px' }}>
                  Plutchik Discrete Emotion Distributions (Per 1k Words)
                </h2>
                <p style={{ fontSize: '12px', color: 'var(--muted)', margin: '0 0 18px' }}>
                  NRC Emotion Lexicon distribution across 8 basic emotions: Anger, Anticipation, Disgust, Fear, Joy, Sadness, Surprise, Trust.
                </p>
                <div style={{ display: 'flex', justifyContent: 'center' }}>
                  <EmotionBarChart data={radarData.languages} width={820} height={340} />
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* Tab 2: Longitudinal Dynamics */}
      {activeTab === 'timeline' && (
        <div className="card" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
            <div>
              <h2 style={{ fontSize: '18px', margin: '0 0 4px' }}>Longitudinal Trajectories (2017–2026)</h2>
              <p style={{ fontSize: '12px', color: 'var(--muted)', margin: 0 }}>
                Monthly aggregated timeseries across South Tyrolean regional media discourse
              </p>
            </div>

            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                type="button"
                className={timelineMetric === 'avg_sentiment' ? 'button' : 'button-quiet'}
                onClick={() => setTimelineMetric('avg_sentiment')}
                style={{ fontSize: '12px' }}
              >
                Net Sentiment Polarity
              </button>
              <button
                type="button"
                className={timelineMetric === 'avg_moral_density' ? 'button' : 'button-quiet'}
                onClick={() => setTimelineMetric('avg_moral_density')}
                style={{ fontSize: '12px' }}
              >
                Moral Framing Density
              </button>
            </div>
          </div>

          {timelineError && <ErrorMessage error={timelineError} />}
          {loadingTimeline && <p className="result-count">Loading longitudinal timeline data…</p>}

          {timelineData && (
            <div style={{ display: 'flex', justifyContent: 'center', marginTop: '12px' }}>
              <TimelineChart series={timelineData.series} metric={timelineMetric} width={920} height={380} />
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Focus Events & Meaning-Making */}
      {activeTab === 'events' && <FocusEventSection />}

      {/* Tab 4: Cross-Lingual Keyness */}
      {activeTab === 'keyness' && (
        <div className="card" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
            <div>
              <h2 style={{ fontSize: '18px', margin: '0 0 4px' }}>
                Cross-Lingual Differential Keyness (Dunning G²)
              </h2>
              <p style={{ fontSize: '12px', color: 'var(--muted)', margin: 0 }}>
                Statistical log-likelihood test identifying distinctive regional vocabulary overused between language sub-corpora.
              </p>
            </div>

            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <span style={{ fontSize: '13px', fontWeight: 600 }}>Compare:</span>
              <select
                value={`${keynessTarget}_vs_${keynessRef}`}
                onChange={(e) => {
                  const [t, r] = e.target.value.split('_vs_')
                  setKeynessTarget(t)
                  setKeynessRef(r)
                }}
                style={{ padding: '6px 10px', borderRadius: '6px', border: '1px solid var(--border)', fontSize: '13px' }}
              >
                <option value="de_vs_it">🇩🇪 German (Target) vs 🇮🇹 Italian (Ref)</option>
                <option value="it_vs_de">🇮🇹 Italian (Target) vs 🇩🇪 German (Ref)</option>
              </select>
            </div>
          </div>

          {keynessError && <ErrorMessage error={keynessError} />}
          {loadingKeyness && <p className="result-count">Calculating Dunning G² log-likelihood keyness…</p>}

          {keynessData.length > 0 && (
            <div style={{ display: 'flex', justifyContent: 'center', marginTop: '16px' }}>
              <KeynessBarChart
                items={keynessData}
                targetLabel={keynessTarget === 'de' ? 'German' : 'Italian'}
                refLabel={keynessRef === 'de' ? 'German' : 'Italian'}
                width={780}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
