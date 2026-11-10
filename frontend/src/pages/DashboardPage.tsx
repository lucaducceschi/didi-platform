import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import {
  type FocusEventItem,
  type RadarAnalyticsResponse,
  type WordBubbleItem,
  getCorpusSummary,
  getFocusEvents,
  getRadarAnalytics,
  getWordBubbles,
  listProjects,
} from '../api'
import { useAuth } from '../auth'
import { RadarChart } from '../components/charts/RadarChart'
import { WordBubbleChart } from '../components/charts/WordBubbleChart'
import { LexicalDossierModal } from '../components/LexicalDossierModal'
import { ErrorMessage } from '../components/Message'
import { useApi } from '../useApi'

export function DashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [quickQuery, setQuickQuery] = useState('')
  const [bubbleMode, setBubbleMode] = useState<'focus' | 'languages' | 'discourse'>('focus')
  const [selectedWord, setSelectedWord] = useState<WordBubbleItem | null>(null)

  const projectsApi = useApi((signal) => listProjects(signal), 'dashboard-projects')
  const corpusApi = useApi((signal) => getCorpusSummary(signal), 'dashboard-summary')
  const radarApi = useApi<RadarAnalyticsResponse>((signal) => getRadarAnalytics(undefined, signal), 'dashboard-radar')
  const eventsApi = useApi<FocusEventItem[]>((signal) => getFocusEvents(signal), 'dashboard-events')
  const wordBubblesApi = useApi<WordBubbleItem[]>(
    (signal) => getWordBubbles(bubbleMode, signal),
    `dashboard-word-bubbles-${bubbleMode}`
  )

  const handleSearchSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (quickQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(quickQuery.trim())}`)
    } else {
      navigate('/search')
    }
  }

  const projects = projectsApi.data ?? []
  const corpus = corpusApi.data
  const radar = radarApi.data
  const latestEvent = eventsApi.data?.[eventsApi.data.length - 1]

  return (
    <div className="stack" style={{ gap: '28px' }}>
      {/* 1. Welcome & Global Quick-Search Command Center */}
      <div
        className="card"
        style={{
          background: 'linear-gradient(135deg, var(--surface) 0%, rgba(31, 95, 139, 0.06) 100%)',
          padding: '24px',
          border: '1px solid var(--border)',
          borderRadius: '10px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: '8px', marginBottom: '16px' }}>
          <div>
            <h1 style={{ margin: '0 0 4px', fontSize: '24px' }}>
              Welcome back, {user?.display_name || 'Researcher'}
            </h1>
            <p style={{ margin: 0, fontSize: '13px', color: 'var(--muted)' }}>
              DIDI Mixed-Methods Research Command Center · Eurac Research &amp; University of Innsbruck
            </p>
          </div>
          {corpus && (
            <span style={{ fontSize: '12px', color: 'var(--muted)', background: 'var(--bg)', padding: '4px 10px', borderRadius: '12px', border: '1px solid var(--border)' }}>
              Corpus: <strong>{corpus.total_articles.toLocaleString()}</strong> articles ({corpus.min_date.slice(0, 4)}–{corpus.max_date.slice(0, 4)})
            </span>
          )}
        </div>

        {/* Quick Search across full corpus */}
        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <input
            type="search"
            placeholder="Search across 113,823 regional news articles (e.g. Autonomie, scuola, Brenner, Wolf, Sanità)…"
            value={quickQuery}
            onChange={(e) => setQuickQuery(e.target.value)}
            style={{
              flex: '1 1 320px',
              padding: '10px 14px',
              borderRadius: '6px',
              border: '1px solid var(--border)',
              fontSize: '14px',
              background: 'var(--surface)',
            }}
          />
          <button type="submit" className="button" style={{ padding: '10px 20px', fontSize: '14px' }}>
            Search Corpus
          </button>
        </form>

        <div style={{ display: 'flex', gap: '8px', marginTop: '10px', alignItems: 'center', flexWrap: 'wrap', fontSize: '12px', color: 'var(--muted)' }}>
          <span>Trilingual suggestions:</span>
          {['Autonomie', 'Brennerbasistunnel', 'Scuola', 'Sanità', 'Wolf'].map((term) => (
            <button
              key={term}
              type="button"
              className="tag-link"
              onClick={() => navigate(`/search?q=${encodeURIComponent(term)}`)}
              style={{ cursor: 'pointer', background: 'none', border: 'none', padding: '2px 6px', fontSize: '12px' }}
            >
              #{term}
            </button>
          ))}
        </div>
      </div>

      {/* 2. Interactive Regional Discourse Word Bubbles */}
      <div
        className="card"
        style={{
          padding: '20px 24px',
          border: '1px solid var(--border)',
          borderRadius: '10px',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '12px',
          }}
        >
          <div>
            <h2 style={{ margin: '0 0 2px', fontSize: '18px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>💬 Regional Discourse Bubbles</span>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 500,
                  color: 'var(--muted)',
                  background: 'var(--canvas-subtle, rgba(0,0,0,0.02))',
                  padding: '2px 8px',
                  borderRadius: '10px',
                  border: '1px solid var(--border)',
                }}
              >
                Interactive Lexicon
              </span>
            </h2>
            <p style={{ margin: 0, fontSize: '12px', color: 'var(--muted)' }}>
              Click any bubble to inspect its 10-year longitudinal trajectory, cross-linguistic balance, and regional collocates
            </p>
          </div>

          {/* Perspective Mode Switcher */}
          <div className="segmented">
            <button
              type="button"
              aria-pressed={bubbleMode === 'focus'}
              onClick={() => setBubbleMode('focus')}
              style={{ fontSize: '12px', padding: '6px 12px', cursor: 'pointer' }}
            >
              ⚡ Focus Themes
            </button>
            <button
              type="button"
              aria-pressed={bubbleMode === 'languages'}
              onClick={() => setBubbleMode('languages')}
              style={{ fontSize: '12px', padding: '6px 12px', cursor: 'pointer' }}
            >
              🌐 German vs. Italian
            </button>
            <button
              type="button"
              aria-pressed={bubbleMode === 'discourse'}
              onClick={() => setBubbleMode('discourse')}
              style={{ fontSize: '12px', padding: '6px 12px', cursor: 'pointer' }}
            >
              🗞️ Scrutiny vs. PR
            </button>
          </div>
        </div>

        <ErrorMessage error={wordBubblesApi.error} />

        {wordBubblesApi.loading && (
          <div style={{ padding: '36px', textAlign: 'center', color: 'var(--muted)', fontSize: '13px' }}>
            Aggregating lexical bubbles across regional corpus…
          </div>
        )}

        {wordBubblesApi.data && (
          <WordBubbleChart
            data={wordBubblesApi.data}
            onSelectWord={setSelectedWord}
            selectedId={selectedWord?.id}
          />
        )}
      </div>

      {/* Lexical Dossier Slide-Over / Dialog */}
      <LexicalDossierModal
        item={selectedWord}
        onClose={() => setSelectedWord(null)}
      />

      {/* 3. Main Dual-Perspective Grid: Workspaces (Left) vs. Corpus Pulse (Right) */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '24px',
          alignItems: 'start',
        }}
      >
        {/* LEFT PANE: Active Research Workspaces */}
        <div className="stack" style={{ gap: '16px', flex: '1 1 540px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ fontSize: '18px', margin: 0 }}>Active Research Projects ({projects.length})</h2>
            <Link to="/projects" className="button-link" style={{ fontSize: '13px' }}>
              Manage all projects &rarr;
            </Link>
          </div>

          <ErrorMessage error={projectsApi.error} />
          {projectsApi.loading && <p className="result-count">Loading research workspaces…</p>}

          {projects.length === 0 && !projectsApi.loading && (
            <div className="card" style={{ padding: '24px', textAlign: 'center' }}>
              <p style={{ margin: '0 0 12px', color: 'var(--muted)' }}>
                You don't have any research projects yet.
              </p>
              <Link to="/projects" className="button">
                Create a Project
              </Link>
            </div>
          )}

          {projects.map((proj) => {
            const totalArticles = proj.article_count
            const segmentCount = proj.segment_count
            const codeCount = proj.code_count
            const memberCount = proj.member_count

            return (
              <div
                key={proj.id}
                className="card"
                style={{
                  padding: '20px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                  border: '1px solid var(--border)',
                  borderRadius: '8px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
                  <div>
                    <h3 style={{ margin: '0 0 4px', fontSize: '17px' }}>
                      <Link to={`/projects/${proj.id}`}>{proj.name}</Link>
                      {proj.archived && <span className="tag" style={{ marginLeft: '8px' }}>Archived</span>}
                    </h3>
                    {proj.description && (
                      <p style={{ margin: 0, fontSize: '13px', color: 'var(--muted)' }}>
                        {proj.description}
                      </p>
                    )}
                  </div>
                  {proj.role && (
                    <span className="tag" style={{ textTransform: 'capitalize', fontSize: '11px' }}>
                      {proj.role}
                    </span>
                  )}
                </div>

                {/* Workspace quick stats */}
                <div
                  style={{
                    display: 'flex',
                    gap: '16px',
                    fontSize: '12px',
                    color: 'var(--muted)',
                    backgroundColor: 'var(--canvas-subtle, rgba(0,0,0,0.02))',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    flexWrap: 'wrap',
                  }}
                >
                  <span><strong>{totalArticles}</strong> articles</span>
                  <span><strong>{segmentCount}</strong> coded segments</span>
                  <span><strong>{codeCount}</strong> codes</span>
                  <span><strong>{memberCount}</strong> {memberCount === 1 ? 'member' : 'members'}</span>
                </div>

                {/* Quick Action Navigation Buttons */}
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '4px' }}>
                  <Link
                    to={`/projects/${proj.id}/articles`}
                    className="button"
                    style={{ fontSize: '12px', padding: '6px 12px' }}
                  >
                    📖 Continue Coding
                  </Link>
                  <Link
                    to={`/projects/${proj.id}/analysis`}
                    className="button-quiet"
                    style={{ fontSize: '12px', padding: '6px 12px' }}
                  >
                    📊 Project vs. Corpus Analysis
                  </Link>
                  <Link
                    to={`/projects/${proj.id}/codebook`}
                    className="button-quiet"
                    style={{ fontSize: '12px', padding: '6px 12px' }}
                  >
                    🏷️ Codebook
                  </Link>
                  <Link
                    to={`/projects/${proj.id}/passages`}
                    className="button-quiet"
                    style={{ fontSize: '12px', padding: '6px 12px' }}
                  >
                    🔍 Passages
                  </Link>
                </div>
              </div>
            )
          })}
        </div>

        {/* RIGHT PANE: Regional Discourse Pulse & Benchmarks */}
        <div className="stack" style={{ gap: '20px', flex: '1 1 360px' }}>
          <h2 style={{ fontSize: '18px', margin: 0 }}>Regional Corpus Pulse</h2>

          {/* Corpus Telemetry Card */}
          {corpus && (
            <div className="card" style={{ padding: '18px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '10px' }}>
                <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--muted)' }}>
                  MEDIA CORPUS REPOSITORY
                </span>
                <Link to="/search" style={{ fontSize: '12px' }}>
                  Browse &rarr;
                </Link>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '12px' }}>
                <div style={{ background: 'var(--bg)', padding: '10px', borderRadius: '6px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--muted)' }}>Total Articles</div>
                  <div style={{ fontSize: '18px', fontWeight: 700 }}>
                    {corpus.total_articles.toLocaleString()}
                  </div>
                </div>
                <div style={{ background: 'var(--bg)', padding: '10px', borderRadius: '6px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--muted)' }}>Total Word Tokens</div>
                  <div style={{ fontSize: '18px', fontWeight: 700 }}>
                    {(corpus.total_words / 1_000_000).toFixed(1)}M
                  </div>
                </div>
              </div>

              <div style={{ fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--muted)' }}>🇩🇪 German Media (Tageszeitung):</span>
                  <strong>{corpus.languages.find((l) => l.id === 'de')?.count.toLocaleString() || '90,697'}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--muted)' }}>🇮🇹 Italian Media (Salto / Press):</span>
                  <strong>{corpus.languages.find((l) => l.id === 'it')?.count.toLocaleString() || '23,126'}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid var(--border)', paddingTop: '6px', marginTop: '2px' }}>
                  <span style={{ color: 'var(--muted)' }}>🗞️ Journalism vs 🏛️ Official Press:</span>
                  <span>
                    {corpus.source_types?.find((t) => t.id === 'journalism')?.count.toLocaleString() || '80k'} /{' '}
                    {corpus.source_types?.find((t) => t.id === 'official_press')?.count.toLocaleString() || '22k'}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Mini Moral Framing Radar Preview */}
          {radarApi.loading && (
            <div className="card" style={{ padding: '24px', textAlign: 'center' }}>
              <p className="result-count" style={{ margin: 0 }}>Computing media framing radar…</p>
            </div>
          )}
          {radar && radar.languages.length > 0 && (
            <div className="card" style={{ padding: '18px', textAlign: 'center' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '8px' }}>
                <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--muted)' }}>
                  MEDIA FRAMING RADAR (DE vs IT)
                </span>
                <Link to="/analytics" style={{ fontSize: '12px' }}>
                  Full Radar &rarr;
                </Link>
              </div>
              <p style={{ fontSize: '11px', color: 'var(--muted)', margin: '0 0 10px' }}>
                Moral Foundations density per 1,000 words across German &amp; Italian press
              </p>
              <div style={{ display: 'flex', justifyContent: 'center' }}>
                <RadarChart data={radar.languages.filter((l) => l.language === 'de' || l.language === 'it')} size={300} />
              </div>
            </div>
          )}

          {/* Regional Focus Event Ticker */}
          {latestEvent && (
            <div className="card" style={{ padding: '18px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '6px' }}>
                <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--muted)' }}>
                  REGIONAL FOCUS EVENT SPOTLIGHT
                </span>
                <Link to="/analytics" style={{ fontSize: '12px' }}>
                  Meaning-making &rarr;
                </Link>
              </div>
              <div style={{ fontWeight: 600, fontSize: '14px', marginBottom: '4px' }}>
                ⚡ {latestEvent.title}
              </div>
              <p style={{ fontSize: '12px', color: 'var(--muted)', margin: '0 0 10px' }}>
                {latestEvent.description}
              </p>
              <div style={{ fontSize: '11px', color: 'var(--muted)', display: 'flex', gap: '8px' }}>
                <span className="tag">{latestEvent.category}</span>
                <span>Date: {latestEvent.date}</span>
                <span>Window: ±{latestEvent.default_window}d</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
