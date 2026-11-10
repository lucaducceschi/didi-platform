import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import {
  type LibraryArticle,
  type LibraryFilters,
  type MyStatus,
  type Project,
  type SavedSelection,
  deleteSelection,
  getLibrary,
  listSelections,
  refreshSelection,
  removeArticle,
  removeUnstartedArticles,
} from '../../api'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { ErrorMessage } from '../../components/Message'
import { useAction } from '../../useAction'
import { useApi } from '../../useApi'

const STATUS_LABELS: Record<MyStatus, string> = {
  not_started: 'Not started',
  in_progress: 'In progress',
  done: 'Done',
}

function readFilters(params: URLSearchParams): LibraryFilters {
  const status = params.get('status')
  return {
    languages: params.getAll('language'),
    sources: params.getAll('source'),
    types: params.getAll('type'),
    status: status === 'not_started' || status === 'in_progress' || status === 'done' ? status : '',
    page: Math.max(1, Number(params.get('page')) || 1),
  }
}

function Coders({ article }: { article: LibraryArticle }) {
  if (article.coders.length === 0) return null
  return (
    <div className="coder-row">
      {article.coders.map((coder) => (
        <span key={coder.user.id} className="coder-chip">
          <strong>{coder.user.display_name}</strong>
          {` · ${coder.segments} ${coder.segments === 1 ? 'segment' : 'segments'}`}
          {coder.status === 'done' && <span className="status-done"> · Done</span>}
          {coder.status === 'in_progress' && ' · In progress'}
          {coder.stale_segments > 0 && <span className="status-warn"> · {coder.stale_segments} to review</span>}
        </span>
      ))}
    </div>
  )
}

export function LibraryTab({ project }: { project: Project }) {
  const [params, setParams] = useSearchParams()
  const filters = readFilters(params)
  const { data, error, loading, reload } = useApi((signal) => getLibrary(project.id, filters, signal), `${project.id}?${params}`)
  const selections = useApi((signal) => listSelections(project.id, signal), project.id)
  const removal = useAction()
  const selectionAction = useAction()
  const [showSelections, setShowSelections] = useState(false)
  const [removing, setRemoving] = useState<LibraryArticle | null>(null)
  const [removingUnstarted, setRemovingUnstarted] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const base = `/projects/${project.id}/articles`

  const setFilter = (name: 'language' | 'source' | 'type' | 'status', value: string) => {
    const next = new URLSearchParams(params)
    next.delete(name)
    next.delete('page')
    if (value) next.set(name, value)
    setParams(next)
  }

  const goToPage = (page: number) => {
    const next = new URLSearchParams(params)
    next.set('page', String(page))
    setParams(next)
  }

  const canAdd = project.can_manage && !project.archived

  const confirmRemove = () => {
    const article = removing!
    setRemoving(null)
    setNotice(null)
    void removal.run(async () => {
      await removeArticle(project.id, article.id)
      setNotice(`Removed “${article.title}” from this project.`)
      reload()
    })
  }

  const confirmRemoveUnstarted = () => {
    setRemovingUnstarted(false)
    setNotice(null)
    void removal.run(async () => {
      const { removed } = await removeUnstartedArticles(project.id)
      setNotice(`Removed ${removed.toLocaleString()} ${removed === 1 ? 'article' : 'articles'} that nobody had started.`)
      // The page may no longer exist once the list is shorter.
      goToPage(1)
      reload()
    })
  }

  const handleRefreshSelection = (sel: SavedSelection) => {
    void selectionAction.run(async () => {
      const updated = await refreshSelection(project.id, sel.id)
      setNotice(`Refreshed snapshot for "${sel.name}": now holds ${updated.article_count.toLocaleString()} articles.`)
      selections.reload()
    })
  }

  const handleDeleteSelection = (sel: SavedSelection) => {
    if (!confirm(`Delete saved selection "${sel.name}"? Articles in the project will remain.`)) return
    void selectionAction.run(async () => {
      await deleteSelection(project.id, sel.id)
      setNotice(`Deleted selection "${sel.name}".`)
      selections.reload()
    })
  }
  const lastPage = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  const hidden = data ? data.project_total - data.total : 0

  return (
    <section className="stack" aria-label="Project articles">
      <div className="filter-row">
        <label className="field">
          Variety
          <select value={filters.languages[0] ?? ''} onChange={(event) => setFilter('language', event.target.value)}>
            <option value="">All varieties</option>
            {data?.languages.map((facet) => <option key={facet.id} value={facet.id}>{facet.label} ({facet.count.toLocaleString()})</option>)}
          </select>
        </label>
        <label className="field">
          Source
          <select value={filters.sources[0] ?? ''} onChange={(event) => setFilter('source', event.target.value)}>
            <option value="">All sources</option>
            {data?.sources.map((facet) => <option key={facet.id} value={facet.id}>{facet.label} ({facet.count.toLocaleString()})</option>)}
          </select>
        </label>
        <label className="field">
          Type
          <select value={filters.types[0] ?? ''} onChange={(event) => setFilter('type', event.target.value)}>
            <option value="">All types</option>
            {data?.source_types?.map((facet) => <option key={facet.id} value={facet.id}>{facet.label} ({facet.count.toLocaleString()})</option>)}
          </select>
        </label>
        <label className="field">
          My status
          <select value={filters.status} onChange={(event) => setFilter('status', event.target.value)}>
            <option value="">Any status</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        {canAdd && <Link to={`${base}/add`} className="button-link">Add articles</Link>}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
        <button
          type="button"
          onClick={() => setShowSelections((prev) => !prev)}
          className="button-quiet"
          style={{ fontSize: '12px', padding: '4px 8px' }}
        >
          {showSelections ? 'Hide Selections ▲' : `📁 Saved Selections (${selections.data?.length ?? 0}) ▼`}
        </button>
      </div>

      {showSelections && (
        <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '8px', padding: '16px', margin: '6px 0 12px' }}>
          <h3 style={{ margin: '0 0 10px', fontSize: '13px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--muted)' }}>
            Saved Corpus Selections
          </h3>
          {selections.loading ? (
            <p style={{ margin: 0, fontSize: '13px', color: 'var(--muted)' }}>Loading selections…</p>
          ) : selections.data && selections.data.length === 0 ? (
            <p style={{ margin: 0, fontSize: '13px', color: 'var(--muted)' }}>
              No saved selections in this project yet. Use "Save Selection…" from Search to create one.
            </p>
          ) : selections.data ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {selections.data.map((sel) => {
                const hasQuery = Boolean(sel.query_definition && Object.keys(sel.query_definition).length > 0)
                return (
                  <div
                    key={sel.id}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '10px 12px',
                      background: 'var(--canvas-subtle, rgba(0,0,0,0.02))',
                      border: '1px solid var(--border)',
                      borderRadius: '6px',
                      gap: '12px',
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <strong style={{ fontSize: '13px' }}>{sel.name}</strong>
                        <span className="tag" style={{ margin: 0, fontSize: '11px', padding: '1px 6px' }}>
                          {sel.article_count.toLocaleString()} articles
                        </span>
                        <span
                          style={{
                            fontSize: '11px',
                            color: hasQuery ? 'var(--accent, #3182ce)' : 'var(--muted)',
                            fontWeight: 600,
                          }}
                        >
                          {hasQuery ? '⚡ Dynamic Query' : '📌 Frozen Set'}
                        </span>
                      </div>
                      {sel.description && (
                        <p style={{ margin: '4px 0 0', fontSize: '12px', color: 'var(--muted)' }}>{sel.description}</p>
                      )}
                      <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '4px' }}>
                        Updated {sel.updated_at.slice(0, 10)}
                        {sel.user ? ` · by ${sel.user.display_name}` : ''}
                      </div>
                    </div>

                    <div style={{ display: 'flex', gap: '6px' }}>
                      {hasQuery && (
                        <button
                          type="button"
                          className="button-quiet"
                          onClick={() => handleRefreshSelection(sel)}
                          disabled={selectionAction.busy}
                          style={{ fontSize: '11px', padding: '3px 8px' }}
                          title="Re-materialize snapshot against updated corpus"
                        >
                          🔄 Refresh
                        </button>
                      )}
                      <button
                        type="button"
                        className="button-quiet"
                        onClick={() => handleDeleteSelection(sel)}
                        disabled={selectionAction.busy}
                        style={{ fontSize: '11px', padding: '3px 8px', color: 'var(--error, #e53e3e)' }}
                        title="Delete selection object (articles stay in project)"
                      >
                        🗑️ Delete
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : null}
        </div>
      )}

      <ErrorMessage error={error ?? removal.error} />
      {notice && <p className="message" role="status">{notice}</p>}
      {canAdd && (data?.hidden_articles ?? 0) > 0 && (
        <p className="message" role="note">
          {(data?.hidden_articles ?? 0).toLocaleString()} {data?.hidden_articles === 1 ? 'article' : 'articles'} in unconfigured languages are hidden from this view.
        </p>
      )}
      {data && (
        <p className="result-count" aria-live="polite">
          {data.project_total === 0 ? '' : `${data.total.toLocaleString()} ${data.total === 1 ? 'article' : 'articles'}`}
          {hidden > 0 && ` · ${hidden.toLocaleString()} hidden by these filters`}
        </p>
      )}
      {canAdd && data && data.unstarted_total > 0 && (
        <div>
          <button type="button" className="button-quiet" disabled={removal.busy} onClick={() => setRemovingUnstarted(true)}>
            Remove articles nobody has started ({data.unstarted_total.toLocaleString()})…
          </button>
        </div>
      )}
      {loading && !data && <p className="result-count">Loading articles…</p>}
      {data?.project_total === 0 && (
        <p className="message">
          {canAdd ? 'This project has no articles yet. Add some from the corpus to start.' : 'This project has no articles yet. A project lead can add them.'}
        </p>
      )}
      {data && data.project_total > 0 && data.total === 0 && <p className="message">No articles match these filters.</p>}

      <ul className="library-list">
        {data?.results.map((article) => (
          <li key={article.id}>
            <h2>{article.in_corpus ? <Link to={`${base}/${encodeURIComponent(article.id)}`}>{article.title}</Link> : article.title}</h2>
            {article.in_corpus ? (
              <p className="result-meta">
                {article.source_type === 'official_press' && <span className="tag">Official press</span>}
                {article.publish_date} · {article.source_label} · {article.language_label} · {(article.word_count ?? 0).toLocaleString()} words · You: {STATUS_LABELS[article.my_status]}
              </p>
            ) : <p className="result-meta status-warn">This article is no longer in the corpus. Its segments are kept and marked for review.</p>}
            <Coders article={article} />
            {canAdd && (
              <button type="button" className="button-quiet library-remove" disabled={removal.busy} onClick={() => setRemoving(article)} aria-label={`Remove ${article.title}`}>
                Remove
              </button>
            )}
          </li>
        ))}
      </ul>

      {data && data.total > data.page_size && (
        <nav className="pagination" aria-label="Pages">
          <button type="button" disabled={filters.page <= 1} onClick={() => goToPage(filters.page - 1)}>Previous</button>
          <span>Page {filters.page.toLocaleString()} of {lastPage.toLocaleString()}</span>
          <button type="button" disabled={filters.page >= lastPage} onClick={() => goToPage(filters.page + 1)}>Next</button>
        </nav>
      )}

      {removing && (
        <ConfirmDialog title="Remove this article?" confirmLabel="Remove article" danger busy={removal.busy} onCancel={() => setRemoving(null)} onConfirm={confirmRemove}>
          <p>“{removing.title}” leaves this project and any coder's status on it is cleared. It stays in the corpus, and you can add it back. An article with coded passages can't be removed.</p>
        </ConfirmDialog>
      )}
      {removingUnstarted && data && (
        <ConfirmDialog title={`Remove ${data.unstarted_total.toLocaleString()} articles?`} confirmLabel={`Remove ${data.unstarted_total.toLocaleString()} articles`} danger busy={removal.busy} onCancel={() => setRemovingUnstarted(false)} onConfirm={confirmRemoveUnstarted}>
          <p>This removes every article in this project with no coded passages and no status from anyone, including any your filters hide. They stay in the corpus, and you can add them back.</p>
        </ConfirmDialog>
      )}
    </section>
  )
}
