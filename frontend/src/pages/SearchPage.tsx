import { type FormEvent, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import {
  type ConcordanceLine,
  type ConcordanceResponse,
  type SearchDistribution,
  type SearchFilters,
  addArticles,
  addArticlesFromSearch,
  getConcordance,
  getCorpusSummary,
  getSearchDistribution,
  listProjects,
  searchArticles,
} from '../api'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { ErrorMessage } from '../components/Message'
import { SaveSelectionDialog } from '../components/SaveSelectionDialog'
import { Snippet } from '../components/Snippet'
import { useAction } from '../useAction'
import { useApi } from '../useApi'

const PAGE_SIZE = 20

function readFilters(params: URLSearchParams): SearchFilters {
  const modeParam = params.get('mode')
  const mode: 'exact' | 'word_family' | 'concept' =
    modeParam === 'exact' || modeParam === 'word_family' || modeParam === 'concept'
      ? modeParam
      : 'concept'

  return {
    q: params.get('q') ?? '',
    mode,
    sources: params.getAll('source'),
    languages: params.getAll('language'),
    types: params.getAll('type'),
    min_date: params.get('min_date') ?? '',
    max_date: params.get('max_date') ?? '',
    page: Math.max(1, Number(params.get('page')) || 1),
  }
}

export function FacetGroup({
  legend,
  name,
  options,
  selected,
  onChange,
}: {
  legend: string
  name: string
  options: { id: string; label: string; count: number }[]
  selected: string[]
  onChange: (values: string[]) => void
}) {
  return (
    <fieldset className="facet">
      <legend>{legend}</legend>
      {options.map((option) => (
        <label key={option.id}>
          <input
            type="checkbox"
            name={name}
            checked={selected.includes(option.id)}
            onChange={(event) =>
              onChange(
                event.target.checked ? [...selected, option.id] : selected.filter((value) => value !== option.id)
              )
            }
          />
          <span>{option.label}</span>
          <span className="count">{option.count.toLocaleString()}</span>
        </label>
      ))}
    </fieldset>
  )
}

export function SearchPage() {
  const [params, setParams] = useSearchParams()
  const filters = readFilters(params)
  const [draft, setDraft] = useState(filters.q)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [targetProjectId, setTargetProjectId] = useState<string>('')
  const [confirmAll, setConfirmAll] = useState(false)
  const [showSaveSelection, setShowSaveSelection] = useState(false)
  const [notice, setNotice] = useState<{ text: string; projectId: string; projectName: string } | null>(null)

  const summary = useApi((signal) => getCorpusSummary(signal), 'summary')
  const search = useApi((signal) => searchArticles(filters, signal), params.toString())
  const projects = useApi((signal) => listProjects(signal), 'projects')
  const { busy, error: actionError, run } = useAction()
  const [viewMode, setViewMode] = useState<'articles' | 'concordance'>('articles')
  const [showDistribution, setShowDistribution] = useState(false)

  const concordance = useApi<ConcordanceResponse | null>(
    (signal) => (viewMode === 'concordance' ? getConcordance({ ...filters, page_size: 50 }, signal) : Promise.resolve(null)),
    viewMode === 'concordance' ? `concordance:${params.toString()}` : 'concordance:disabled',
  )
  const distribution = useApi<SearchDistribution | null>(
    (signal) => (showDistribution ? getSearchDistribution(filters, signal) : Promise.resolve(null)),
    showDistribution ? `distribution:${params.toString()}` : 'distribution:disabled',
  )

  const addable = (projects.data ?? []).filter((project) => project.can_manage && !project.archived)
  const carriedFilters = new URLSearchParams(params)
  carriedFilters.delete('page')

  useEffect(() => setDraft(filters.q), [filters.q])

  // Default target project to first available
  useEffect(() => {
    if (addable.length > 0 && !targetProjectId) {
      setTargetProjectId(addable[0].id)
    }
  }, [addable, targetProjectId])

  const update = (next: Partial<SearchFilters>) => {
    const merged = { ...filters, page: 1, ...next }
    const updated = new URLSearchParams()
    if (merged.q.trim()) updated.set('q', merged.q.trim())
    if (merged.mode && merged.mode !== 'concept') updated.set('mode', merged.mode)
    merged.sources.forEach((source) => updated.append('source', source))
    merged.languages.forEach((language) => updated.append('language', language))
    merged.types?.forEach((type) => updated.append('type', type))
    if (merged.min_date) updated.set('min_date', merged.min_date)
    if (merged.max_date) updated.set('max_date', merged.max_date)
    if (merged.page > 1) updated.set('page', String(merged.page))
    setSelected(new Set())
    setParams(updated)
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    update({ q: draft })
  }

  const total = search.data?.total ?? 0
  const lastPage = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const pageResultIds = (search.data?.results ?? []).map((r) => r.id)
  const allOnPageSelected = pageResultIds.length > 0 && pageResultIds.every((id) => selected.has(id))

  const toggleOne = (id: string, checked: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }

  const toggleAllOnPage = (checked: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev)
      pageResultIds.forEach((id) => {
        if (checked) next.add(id)
        else next.delete(id)
      })
      return next
    })
  }

  const selectedTargetProject = addable.find((p) => p.id === targetProjectId)

  const handleAddSelected = () => {
    if (!targetProjectId || selected.size === 0) return
    const project = selectedTargetProject
    if (!project) return

    void run(async () => {
      const res = await addArticles(targetProjectId, [...selected])
      const msg = `Added ${res.added.toLocaleString()} ${res.added === 1 ? 'article' : 'articles'} to ${project.name}.${res.already_present ? ` ${res.already_present.toLocaleString()} was already present.` : ''}`
      setNotice({ text: msg, projectId: project.id, projectName: project.name })
      setSelected(new Set())
    })
  }

  const handleAddAll = () => {
    if (!targetProjectId) return
    const project = selectedTargetProject
    if (!project) return
    setConfirmAll(false)

    void run(async () => {
      const res = await addArticlesFromSearch(targetProjectId, {
        q: filters.q,
        source: filters.sources,
        language: filters.languages,
        type: filters.types,
      })
      const msg = `Added all ${res.added.toLocaleString()} ${res.added === 1 ? 'article' : 'articles'} to ${project.name}.${res.already_present ? ` ${res.already_present.toLocaleString()} was already present.` : ''}`
      setNotice({ text: msg, projectId: project.id, projectName: project.name })
      setSelected(new Set())
    })
  }

  return (
    <div className="search-layout">
      <aside className="filters" aria-label="Filters">
        {summary.data && (
          <>
            <FacetGroup
              legend="Language variety"
              name="language"
              options={summary.data.languages}
              selected={filters.languages}
              onChange={(languages) => update({ languages })}
            />
            <FacetGroup
              legend="Source"
              name="source"
              options={summary.data.sources}
              selected={filters.sources}
              onChange={(sources) => update({ sources })}
            />
            {summary.data.source_types && summary.data.source_types.length > 0 && (
              <FacetGroup
                legend="Type"
                name="type"
                options={summary.data.source_types}
                selected={filters.types ?? []}
                onChange={(types) => update({ types })}
              />
            )}
            <fieldset className="facet">
              <legend>Publication Date</legend>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px' }}>
                <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: 'var(--muted)', fontSize: '12px' }}>From:</span>
                  <input
                    type="date"
                    value={filters.min_date || ''}
                    onChange={(e) => update({ min_date: e.target.value })}
                    style={{ padding: '3px 6px', fontSize: '12px', borderRadius: '4px', border: '1px solid var(--border)', background: 'var(--surface)' }}
                  />
                </label>
                <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: 'var(--muted)', fontSize: '12px' }}>To:</span>
                  <input
                    type="date"
                    value={filters.max_date || ''}
                    onChange={(e) => update({ max_date: e.target.value })}
                    style={{ padding: '3px 6px', fontSize: '12px', borderRadius: '4px', border: '1px solid var(--border)', background: 'var(--surface)' }}
                  />
                </label>
                {(filters.min_date || filters.max_date) && (
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => update({ min_date: '', max_date: '' })}
                    style={{ fontSize: '11px', marginTop: '2px', cursor: 'pointer' }}
                  >
                    Reset date range
                  </button>
                )}
              </div>
            </fieldset>
            <p className="corpus-note">
              {summary.data.total_articles.toLocaleString()} articles, {summary.data.min_date.slice(0, 4)}–
              {summary.data.max_date.slice(0, 4)}. German and Italian coverage is mostly 2024 to May 2025.
            </p>
          </>
        )}
      </aside>

      <section className="results" aria-label="Search results">
        <form className="search-form" role="search" onSubmit={submit}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px', marginBottom: '8px' }}>
            <label htmlFor="search-query" style={{ margin: 0, fontWeight: 600 }}>Search the corpus</label>
            <div className="segmented" role="radiogroup" aria-label="Search mode">
              <button
                type="button"
                aria-pressed={filters.mode === 'concept'}
                onClick={() => update({ mode: 'concept' })}
                title="Multilingual concept expansion across German, Italian, and Ladin"
                style={{ fontSize: '12px', padding: '4px 10px', cursor: 'pointer' }}
              >
                ⚡ Concept
              </button>
              <button
                type="button"
                aria-pressed={filters.mode === 'word_family'}
                onClick={() => update({ mode: 'word_family' })}
                title="Morphological prefix expansion (*)"
                style={{ fontSize: '12px', padding: '4px 10px', cursor: 'pointer' }}
              >
                🔤 Word Family
              </button>
              <button
                type="button"
                aria-pressed={filters.mode === 'exact'}
                onClick={() => update({ mode: 'exact' })}
                title="Exact literal phrase/term match only (no prefix, no synonyms)"
                style={{ fontSize: '12px', padding: '4px 10px', cursor: 'pointer' }}
              >
                🎯 Exact
              </button>
            </div>
          </div>

          <div className="search-row">
            <input
              id="search-query"
              type="search"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="scuola, Autonomie, lingaz…"
            />
            <button type="submit">Search</button>
          </div>

          {/* Terms Included in This Search Drawer */}
          {search.data?.query_interpretation && filters.q.trim() && (
            <details
              style={{
                marginTop: '10px',
                padding: '8px 12px',
                background: 'var(--canvas-subtle, rgba(0,0,0,0.02))',
                border: '1px solid var(--border)',
                borderRadius: '6px',
                fontSize: '12px',
              }}
            >
              <summary style={{ cursor: 'pointer', fontWeight: 600, color: 'var(--text)' }}>
                🔍 Terms included in this search ({search.data.query_interpretation.search_mode.replace('_', ' ')} mode)
              </summary>
              <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <div style={{ color: 'var(--muted)', fontSize: '11px' }}>
                  Effective FTS: <code style={{ color: 'var(--text)', background: 'var(--surface)', padding: '1px 4px', borderRadius: '3px' }}>{search.data.query_interpretation.effective_fts}</code>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '4px' }}>
                  {search.data.query_interpretation.expansion_terms.map((et, i) => (
                    <span
                      key={i}
                      className="tag"
                      style={{
                        margin: 0,
                        fontSize: '11px',
                        padding: '2px 8px',
                        background: 'var(--surface)',
                        border: '1px solid var(--border)',
                      }}
                    >
                      <strong>{et.term}</strong>
                      {et.language && <span style={{ marginLeft: '4px', color: 'var(--muted)', fontSize: '10px' }}>({et.language})</span>}
                    </span>
                  ))}
                </div>
              </div>
            </details>
          )}
        </form>

        {/* Non-blocking Coverage Warnings */}
        {search.data?.query_interpretation?.warnings && search.data.query_interpretation.warnings.length > 0 && (
          <div
            className="message"
            role="note"
            style={{
              borderLeft: '3px solid var(--accent, #3182ce)',
              padding: '10px 14px',
              fontSize: '13px',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px',
              margin: '12px 0 0',
            }}
          >
            <strong style={{ fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              ℹ️ Corpus Coverage Note
            </strong>
            {search.data.query_interpretation.warnings.map((w, idx) => (
              <span key={idx} style={{ color: 'var(--muted)' }}>
                {w}
              </span>
            ))}
          </div>
        )}

        {search.error && <p className="message message-error" role="alert">{search.error.message}</p>}
        {actionError && <ErrorMessage error={actionError} />}

        {notice && (
          <div className="message" role="status" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>{notice.text}</span>
            <Link to={`/projects/${notice.projectId}/articles`} className="button-link" style={{ fontSize: '13px' }}>
              Open {notice.projectName} library →
            </Link>
          </div>
        )}

        {addable.length > 0 && (search.data?.hidden_articles ?? 0) > 0 && (
          <p className="message" role="note">
            {(search.data?.hidden_articles ?? 0).toLocaleString()}{' '}
            {search.data?.hidden_articles === 1 ? 'article' : 'articles'} in unconfigured languages are hidden from this view.
          </p>
        )}

        {!search.error && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px', margin: '14px 0 8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ display: 'inline-flex', borderRadius: '6px', border: '1px solid var(--border)', overflow: 'hidden' }}>
                <button
                  type="button"
                  onClick={() => setViewMode('articles')}
                  style={{
                    padding: '5px 12px',
                    fontSize: '12px',
                    fontWeight: 600,
                    border: 'none',
                    cursor: 'pointer',
                    background: viewMode === 'articles' ? 'var(--accent, #3182ce)' : 'var(--surface)',
                    color: viewMode === 'articles' ? '#fff' : 'var(--text)',
                  }}
                >
                  📄 Articles
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode('concordance')}
                  style={{
                    padding: '5px 12px',
                    fontSize: '12px',
                    fontWeight: 600,
                    border: 'none',
                    borderLeft: '1px solid var(--border)',
                    cursor: 'pointer',
                    background: viewMode === 'concordance' ? 'var(--accent, #3182ce)' : 'var(--surface)',
                    color: viewMode === 'concordance' ? '#fff' : 'var(--text)',
                  }}
                >
                  🔍 Concordance (KWIC)
                </button>
              </div>

              <button
                type="button"
                onClick={() => setShowDistribution((prev) => !prev)}
                className="button-quiet"
                style={{ fontSize: '12px', padding: '4px 8px' }}
              >
                {showDistribution ? 'Hide Breakdown ▲' : '📊 Corpus Breakdown ▼'}
              </button>
            </div>

            <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
              <p className="result-count" aria-live="polite" style={{ margin: 0 }}>
                {search.loading ? 'Searching…' : `${total.toLocaleString()} ${total === 1 ? 'article' : 'articles'}`}
              </p>
              {addable.length > 0 && total > 0 && (
                <p className="add-to-project" style={{ margin: 0, fontSize: '13px' }}>
                  Add view to:{' '}
                  {addable.map((project) => (
                    <Link key={project.id} className="tag-link" to={`/projects/${project.id}/articles/add?${carriedFilters}`}>
                      {project.name}
                    </Link>
                  ))}
                </p>
              )}
            </div>
          </div>
        )}

        {showDistribution && (
          <div
            style={{
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: '8px',
              padding: '16px',
              margin: '10px 0 16px',
            }}
          >
            <h3 style={{ margin: '0 0 12px', fontSize: '13px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--muted)' }}>
              Search Distribution Breakdown
            </h3>
            {distribution.loading ? (
              <p style={{ margin: 0, fontSize: '13px', color: 'var(--muted)' }}>Calculating distribution across corpus…</p>
            ) : distribution.data ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px' }}>
                <div>
                  <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--muted)' }}>Languages</span>
                  <div style={{ marginTop: '6px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    {Object.entries(distribution.data.by_language).map(([lang, cnt]) => (
                      <div key={lang} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                        <span>{lang === 'de' ? 'German (de)' : lang === 'it' ? 'Italian (it)' : lang}</span>
                        <strong>{(cnt as number).toLocaleString()}</strong>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--muted)' }}>Discourse Type</span>
                  <div style={{ marginTop: '6px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    {Object.entries(distribution.data.by_source_type).map(([stype, cnt]) => (
                      <div key={stype} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                        <span>{stype === 'official_press' ? 'Official Press' : 'Journalism'}</span>
                        <strong>{(cnt as number).toLocaleString()}</strong>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--muted)' }}>Top Outlets</span>
                  <div style={{ marginTop: '6px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    {Object.entries(distribution.data.by_source).slice(0, 4).map(([src, cnt]) => (
                      <div key={src} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                        <span>{src}</span>
                        <strong>{(cnt as number).toLocaleString()}</strong>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--muted)' }}>Timeline (Years)</span>
                  <div style={{ marginTop: '6px', display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                    {Object.entries(distribution.data.by_year).map(([yr, cnt]) => (
                      <span key={yr} className="tag" style={{ margin: 0, fontSize: '11px', padding: '2px 6px' }}>
                        {yr}: {(cnt as number).toLocaleString()}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        )}

        {/* Batch Selection Bar */}
        {addable.length > 0 && !search.error && total > 0 && (
          <div
            className="add-bar"
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              gap: '12px',
              padding: '10px 12px',
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: '6px',
              margin: '12px 0 16px',
            }}
          >
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '13px', cursor: 'pointer', userSelect: 'none' }}>
              <input
                type="checkbox"
                checked={allOnPageSelected}
                onChange={(e) => toggleAllOnPage(e.target.checked)}
              />
              <span style={{ fontWeight: 600 }}>Select page ({pageResultIds.length})</span>
            </label>

            {selected.size > 0 && (
              <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--accent)' }}>
                {selected.size.toLocaleString()} selected
              </span>
            )}

            <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
              <label htmlFor="target-project-select" style={{ fontSize: '12px', color: 'var(--muted)' }}>
                Project:
              </label>
              <select
                id="target-project-select"
                value={targetProjectId}
                onChange={(e) => setTargetProjectId(e.target.value)}
                style={{ padding: '5px 8px', borderRadius: '4px', fontSize: '13px', border: '1px solid var(--border)' }}
              >
                {addable.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>

              <button
                type="button"
                className="button"
                disabled={busy || selected.size === 0 || !targetProjectId}
                onClick={handleAddSelected}
                style={{ fontSize: '13px', padding: '6px 14px' }}
              >
                Add selected ({selected.size.toLocaleString()})
              </button>

              <button
                type="button"
                className="button-quiet"
                disabled={busy || !targetProjectId}
                onClick={() => setConfirmAll(true)}
                style={{ fontSize: '13px', padding: '6px 14px' }}
              >
                Add all {total.toLocaleString()} matches…
              </button>

              <button
                type="button"
                className="button-quiet"
                disabled={busy || !targetProjectId}
                onClick={() => setShowSaveSelection(true)}
                style={{ fontSize: '13px', padding: '6px 14px' }}
                title="Save this search or selection as a reusable corpus object in the project"
              >
                💾 Save Selection…
              </button>
            </div>
          </div>
        )}

        {viewMode === 'concordance' ? (
          <div className="concordance-container" style={{ margin: '16px 0' }}>
            {concordance.loading ? (
              <p className="result-count">Loading concordance lines…</p>
            ) : concordance.error ? (
              <p className="message message-error">{concordance.error.message}</p>
            ) : concordance.data && concordance.data.items.length === 0 ? (
              <p className="message">No concordance lines found for this query.</p>
            ) : concordance.data ? (
              <>
                <div style={{ marginBottom: '12px', fontSize: '13px', color: 'var(--muted)' }}>
                  Showing {concordance.data.items.length} occurrences across {concordance.data.total_articles.toLocaleString()} articles
                </div>
                <div style={{ overflowX: 'auto', border: '1px solid var(--border)', borderRadius: '6px', background: 'var(--surface)' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', tableLayout: 'fixed' }}>
                    <thead style={{ background: 'var(--canvas-subtle, rgba(0,0,0,0.02))', borderBottom: '1px solid var(--border)' }}>
                      <tr>
                        <th style={{ width: '180px', padding: '8px 10px', textAlign: 'left', fontWeight: 600 }}>Article / Date</th>
                        <th style={{ width: '35%', padding: '8px 10px', textAlign: 'right', fontWeight: 600 }}>Left Context</th>
                        <th style={{ width: '130px', padding: '8px 10px', textAlign: 'center', fontWeight: 600 }}>Keyword</th>
                        <th style={{ width: '35%', padding: '8px 10px', textAlign: 'left', fontWeight: 600 }}>Right Context</th>
                        <th style={{ width: '100px', padding: '8px 10px', textAlign: 'center', fontWeight: 600 }}>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {concordance.data.items.map((line: ConcordanceLine, idx: number) => (
                        <tr key={idx} style={{ borderBottom: '1px solid var(--border)' }}>
                          <td style={{ padding: '8px 10px', verticalAlign: 'middle', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            <div style={{ fontWeight: 600, fontSize: '12px', overflow: 'hidden', textOverflow: 'ellipsis' }} title={line.title}>
                              <Link to={`/articles/${encodeURIComponent(line.article_id)}?pos=${line.start_char}&q=${encodeURIComponent(line.keyword)}`}>
                                {line.title}
                              </Link>
                            </div>
                            <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '2px' }}>
                              {line.publish_date.slice(0, 10)} · {line.source_label}
                            </div>
                          </td>
                          <td style={{ padding: '8px 10px', textAlign: 'right', fontFamily: 'monospace', fontSize: '12px', color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {line.left_context}
                          </td>
                          <td style={{ padding: '8px 10px', textAlign: 'center', whiteSpace: 'nowrap' }}>
                            <Link
                              to={`/articles/${encodeURIComponent(line.article_id)}?pos=${line.start_char}&q=${encodeURIComponent(line.keyword)}`}
                              style={{
                                display: 'inline-block',
                                padding: '2px 8px',
                                background: 'var(--amber-3, #fef08a)',
                                color: 'var(--amber-11, #854d0e)',
                                borderRadius: '4px',
                                fontWeight: 700,
                                fontSize: '12px',
                                textDecoration: 'none',
                              }}
                              title="Open match in Reader"
                            >
                              {line.keyword}
                            </Link>
                          </td>
                          <td style={{ padding: '8px 10px', textAlign: 'left', fontFamily: 'monospace', fontSize: '12px', color: 'var(--muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {line.right_context}
                          </td>
                          <td style={{ padding: '8px 10px', textAlign: 'center', whiteSpace: 'nowrap' }}>
                            {addable.length > 0 ? (
                              <Link
                                to={`/projects/${targetProjectId || addable[0].id}/articles/${encodeURIComponent(line.article_id)}?pos=${line.start_char}&q=${encodeURIComponent(line.keyword)}&code=1`}
                                className="button-link"
                                style={{ fontSize: '11px', padding: '3px 6px' }}
                                title="Code this passage in project"
                              >
                                Code 🏷️
                              </Link>
                            ) : (
                              <Link
                                to={`/articles/${encodeURIComponent(line.article_id)}?pos=${line.start_char}&q=${encodeURIComponent(line.keyword)}`}
                                className="button-link"
                                style={{ fontSize: '11px', padding: '3px 6px' }}
                              >
                                View ↗
                              </Link>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : null}
          </div>
        ) : (
          <>
            {!search.loading && !search.error && total === 0 && (
              <p className="message">No articles match. Try fewer words or remove a filter.</p>
            )}

            <ol className="result-list">
              {search.data?.results.map((article) => (
                <li key={article.id} className="pick-row">
                  {addable.length > 0 && (
                    <input
                      type="checkbox"
                      aria-label={`Select ${article.title}`}
                      checked={selected.has(article.id)}
                      onChange={(event) => toggleOne(article.id, event.target.checked)}
                      style={{ marginTop: '6px' }}
                    />
                  )}
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <h2>
                      <Link to={`/articles/${encodeURIComponent(article.id)}`}>{article.title}</Link>
                    </h2>
                    <p className="result-meta">
                      {article.source_type === 'official_press' && <span className="tag">Official press</span>}
                      {article.publish_date.slice(0, 10)} · {article.source_label} · {article.language_label} ·{' '}
                      {article.word_count.toLocaleString()} words
                    </p>
                    <Snippet parts={article.snippet} />
                  </div>
                </li>
              ))}
            </ol>
          </>
        )}

        {total > PAGE_SIZE && (
          <nav className="pagination" aria-label="Pages">
            <button
              type="button"
              disabled={filters.page <= 1}
              onClick={() => update({ page: filters.page - 1 })}
            >
              Previous
            </button>
            <span>
              Page {filters.page.toLocaleString()} of {lastPage.toLocaleString()}
            </span>
            <button
              type="button"
              disabled={filters.page >= lastPage}
              onClick={() => update({ page: filters.page + 1 })}
            >
              Next
            </button>
          </nav>
        )}
      </section>

      {/* Confirmation Dialog for Add All */}
      {confirmAll && selectedTargetProject && (
        <ConfirmDialog
          title={`Add all ${total.toLocaleString()} articles to ${selectedTargetProject.name}?`}
          confirmLabel={`Add all ${total.toLocaleString()} articles`}
          busy={busy}
          onCancel={() => setConfirmAll(false)}
          onConfirm={handleAddAll}
        >
          <p>
            This will add all <strong>{total.toLocaleString()} articles</strong> matching your search
            {filters.q ? ` "${filters.q}"` : ''} and active filters directly to project{' '}
            <strong>{selectedTargetProject.name}</strong>.
          </p>
          <p style={{ fontSize: '13px', color: 'var(--muted)', marginTop: '8px' }}>
            Articles that are already in the project will be preserved.
          </p>
        </ConfirmDialog>
      )}

      {/* Save as Corpus Selection Dialog */}
      {showSaveSelection && addable.length > 0 && (
        <SaveSelectionDialog
          filters={filters}
          totalCount={total}
          selectedIds={Array.from(selected)}
          projects={addable}
          defaultProjectId={targetProjectId}
          onCancel={() => setShowSaveSelection(false)}
          onSuccess={(sel, projName) => {
            setShowSaveSelection(false)
            setNotice({
              text: `Saved selection "${sel.name}" (${sel.article_count} articles) in project "${projName}".`,
              projectId: sel.project_id,
              projectName: projName,
            })
          }}
        />
      )}
    </div>
  )
}
