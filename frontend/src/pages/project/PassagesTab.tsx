import { useMemo } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router'
import { type Passage, type Project, getPassages, listCodes, passagesCsvPath } from '../../api'
import { useAuth } from '../../auth'
import { flattenCodeTree } from '../../codebook'
import { ErrorMessage } from '../../components/Message'
import { useApi } from '../../useApi'

const EVERYONE = 'all'

function PassageCard({ passage, base, back }: { passage: Passage; base: string; back: string }) {
  return (
    <li>
      <p className="passage-code">
        <span className="swatch" style={{ background: passage.code_color }} aria-hidden="true" />
        {passage.code_path}
        {passage.status === 'stale' && <span className="tag">To review</span>}
      </p>
      {/* Always React text children, so markup in scraped articles stays literal. */}
      <p className="passage-text">
        <span className="context">{passage.before}</span>
        <span className="passage-quote" style={{ '--hl': passage.code_color } as React.CSSProperties}>{passage.quote}</span>
        <span className="context">{passage.after}</span>
      </p>
      {passage.memo && <p className="passage-memo">{passage.memo}</p>}
      <p className="result-meta">
        {passage.in_corpus ? (
          <Link to={`${base}/articles/${encodeURIComponent(passage.article_id)}?segment=${passage.id}`} state={{ back }}>{passage.article_title}</Link>
        ) : <span className="status-warn">{passage.article_title} (no longer in the corpus)</span>}
        {passage.in_corpus && ` · ${passage.publish_date} · ${passage.source_label} · ${passage.language_label}`}
        {` · ${passage.user.display_name}`}
      </p>
    </li>
  )
}

export function PassagesTab({ project }: { project: Project }) {
  const { user } = useAuth()
  const location = useLocation()
  const [params, setParams] = useSearchParams()
  const base = `/projects/${project.id}`

  // Members start on their own passages, as in the reader. Someone outside the project has none.
  const coder = params.get('coder') ?? (project.role && user ? user.id : EVERYONE)
  const codeId = params.get('code') ?? ''
  const includeSubcodes = params.get('subcodes') !== 'false'

  const query = new URLSearchParams(params)
  query.delete('coder')
  if (coder !== EVERYONE) query.set('coder', coder)
  const { data, error, loading } = useApi((signal) => getPassages(project.id, query, signal), `${project.id}?${query}`)
  const codes = useApi((signal) => listCodes(project.id, signal), project.id)
  const tree = useMemo(() => flattenCodeTree(codes.data ?? []), [codes.data])
  const counts = useMemo(() => new Map(data?.codes.map((entry) => [entry.id, entry])), [data])

  const setFilter = (name: string, value: string) => {
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
    window.scrollTo(0, 0)
  }

  const page = Math.max(1, Number(params.get('page')) || 1)
  const lastPage = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  const hidden = data ? data.project_total - data.total : 0
  const selectedHasSubcodes = tree.some((node) => node.code.parent_id === codeId)
  const coderOptions = data?.coders ?? []
  const meListed = coderOptions.some((entry) => entry.user.id === user?.id)
  const language = params.get('language') ?? ''
  const csvQuery = new URLSearchParams(query)
  csvQuery.delete('page')

  return (
    <section className="passage-layout" aria-label="Coded passages">
      <aside aria-label="Codes">
        <div className="code-tree">
          <button type="button" className="code-tree-item" aria-pressed={!codeId} onClick={() => setFilter('code', '')}>
            <span className="name">All codes</span>
          </button>
          {tree.map((node) => {
            const total = counts.get(node.code.id)?.total ?? 0
            return (
              <button
                key={node.code.id}
                type="button"
                className={`code-tree-item${total === 0 ? ' empty' : ''}`}
                style={{ paddingLeft: 8 + node.depth * 16 }}
                aria-pressed={codeId === node.code.id}
                onClick={() => setFilter('code', node.code.id)}
              >
                <span className="swatch" style={{ background: node.code.color }} aria-hidden="true" />
                <span className="name">{node.code.name}</span>
                <span className="count">{total.toLocaleString()}</span>
              </button>
            )
          })}
        </div>
        {selectedHasSubcodes && (
          <label className="subcodes-toggle">
            <input type="checkbox" checked={includeSubcodes} onChange={(event) => setFilter('subcodes', event.target.checked ? '' : 'false')} />
            Include subcodes
          </label>
        )}
      </aside>

      <div className="stack">
        <div className="filter-row">
          <label className="field">
            Variety
            <select value={language} onChange={(event) => setFilter('language', event.target.value)}>
              <option value="">All varieties</option>
              {data?.languages.map((facet) => <option key={facet.id} value={facet.id}>{facet.label} ({facet.count.toLocaleString()})</option>)}
            </select>
          </label>
          <label className="field">
            Source
            <select value={params.get('source') ?? ''} onChange={(event) => setFilter('source', event.target.value)}>
              <option value="">All sources</option>
              {data?.sources.map((facet) => <option key={facet.id} value={facet.id}>{facet.label} ({facet.count.toLocaleString()})</option>)}
            </select>
          </label>
          <label className="field">
            Coder
            <select value={coder} onChange={(event) => setFilter('coder', event.target.value)}>
              <option value={EVERYONE}>Everyone</option>
              {project.role && user && !meListed && <option value={user.id}>{user.display_name} (0)</option>}
              {coderOptions.map((entry) => <option key={entry.user.id} value={entry.user.id}>{entry.user.display_name} ({entry.count.toLocaleString()})</option>)}
            </select>
          </label>
          <label className="field">
            Status
            <select value={params.get('status') ?? ''} onChange={(event) => setFilter('status', event.target.value)}>
              <option value="">Any status</option>
              <option value="active">In the text</option>
              <option value="stale">To review</option>
            </select>
          </label>
        </div>

        <ErrorMessage error={error ?? codes.error} />
        {project.can_manage && (data?.hidden_passages ?? 0) > 0 && (
          <p className="message" role="note">
            {(data?.hidden_passages ?? 0).toLocaleString()} {data?.hidden_passages === 1 ? 'passage' : 'passages'} in unconfigured languages are hidden from this view.
          </p>
        )}
        {data && data.project_total > 0 && (
          <div className="row passage-summary">
            <p className="result-count" aria-live="polite">
              {data.total.toLocaleString()} {data.total === 1 ? 'passage' : 'passages'}
              {hidden > 0 && ` · ${hidden.toLocaleString()} hidden by these filters`}
            </p>
            {data.total > 0 && <a className="button-link button-quiet" href={passagesCsvPath(project.id, csvQuery)}>Download these passages (CSV)</a>}
          </div>
        )}
        {loading && !data && <p className="result-count">Loading passages…</p>}
        {data?.project_total === 0 && <p className="message">Nobody has coded anything in this project yet. Open an article on the <Link to={`${base}/articles`}>Articles</Link> tab to start.</p>}
        {data && data.project_total > 0 && data.total === 0 && <p className="message">No passages match these filters.</p>}

        <ol className="passage-list">
          {data?.results.map((passage) => <PassageCard key={passage.id} passage={passage} base={base} back={`${location.pathname}${location.search}`} />)}
        </ol>

        {data && data.total > data.page_size && (
          <nav className="pagination" aria-label="Pages">
            <button type="button" disabled={page <= 1} onClick={() => goToPage(page - 1)}>Previous</button>
            <span>Page {page.toLocaleString()} of {lastPage.toLocaleString()}</span>
            <button type="button" disabled={page >= lastPage} onClick={() => goToPage(page + 1)}>Next</button>
          </nav>
        )}
      </div>
    </section>
  )
}
