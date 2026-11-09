import { type FormEvent, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { type Project, type SearchFilters, addArticles, addArticlesFromSearch, getCorpusSummary, searchForProject } from '../../api'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { ErrorMessage } from '../../components/Message'
import { Snippet } from '../../components/Snippet'
import { useAction } from '../../useAction'
import { useApi } from '../../useApi'
import { FacetGroup } from '../SearchPage'

const PAGE_SIZE = 20

export function AddArticlesPage({ project }: { project: Project }) {
  const [params, setParams] = useSearchParams()
  const filters: SearchFilters = {
    q: params.get('q') ?? '',
    sources: params.getAll('source'),
    languages: params.getAll('language'),
    page: Math.max(1, Number(params.get('page')) || 1),
  }
  const [draft, setDraft] = useState(filters.q)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [confirmAll, setConfirmAll] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const summary = useApi((signal) => getCorpusSummary(signal), 'summary')
  const search = useApi((signal) => searchForProject(project.id, filters, signal), `${project.id}?${params}`)
  const { busy, error, run } = useAction()

  useEffect(() => setDraft(filters.q), [filters.q])

  const update = (next: Partial<SearchFilters>) => {
    const merged = { ...filters, page: 1, ...next }
    const updated = new URLSearchParams()
    if (merged.q.trim()) updated.set('q', merged.q.trim())
    merged.sources.forEach((source) => updated.append('source', source))
    merged.languages.forEach((language) => updated.append('language', language))
    if (merged.page > 1) updated.set('page', String(merged.page))
    setParams(updated)
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    update({ q: draft })
  }

  const toggle = (id: string, checked: boolean) => {
    setSelected((current) => {
      const next = new Set(current)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }

  const describe = (added: number, present: number) =>
    `Added ${added.toLocaleString()} ${added === 1 ? 'article' : 'articles'}.${present ? ` ${present.toLocaleString()} ${present === 1 ? 'was' : 'were'} already in the project.` : ''}`

  const addSelected = () => void run(async () => {
    const result = await addArticles(project.id, [...selected])
    setNotice(describe(result.added, result.already_present))
    setSelected(new Set())
    search.reload()
  })

  const addAll = () => {
    setConfirmAll(false)
    void run(async () => {
      const result = await addArticlesFromSearch(project.id, { q: filters.q, source: filters.sources, language: filters.languages })
      setNotice(describe(result.added, result.already_present))
      setSelected(new Set())
      search.reload()
    })
  }

  const data = search.data
  const newMatches = data ? data.total - data.in_project_total : 0
  const lastPage = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1

  return (
    <div className="add-layout">
      <aside className="filters" aria-label="Filters">
        {summary.data && (
          <>
            <FacetGroup legend="Language variety" name="language" options={summary.data.languages} selected={filters.languages} onChange={(languages) => update({ languages })} />
            <FacetGroup legend="Source" name="source" options={summary.data.sources} selected={filters.sources} onChange={(sources) => update({ sources })} />
          </>
        )}
      </aside>
      <section className="stack" aria-label="Add articles">
        <div className="page-title">
          <h2>Add articles to {project.name}</h2>
          <Link to={`/projects/${project.id}/articles`}>Back to articles</Link>
        </div>
        <form className="search-form" role="search" onSubmit={submit}>
          <label htmlFor="add-search-query">Search the corpus</label>
          <div className="search-row">
            <input id="add-search-query" type="search" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="scuola, Autonomie, lingaz…" />
            <button type="submit">Search</button>
          </div>
        </form>

        <ErrorMessage error={error ?? search.error} />
        {notice && <p className="message" role="status">{notice}</p>}
        {(data?.hidden_articles ?? 0) > 0 && (
          <p className="message" role="note">
            {(data?.hidden_articles ?? 0).toLocaleString()} {data?.hidden_articles === 1 ? 'article' : 'articles'} in unconfigured languages are hidden from this view.
          </p>
        )}

        {data && !search.error && (
          <div className="add-bar">
            <p className="result-count" aria-live="polite">
              {data.total.toLocaleString()} {data.total === 1 ? 'match' : 'matches'}, {data.in_project_total.toLocaleString()} already in the project
            </p>
            <button type="button" disabled={busy || selected.size === 0} onClick={addSelected}>Add selected ({selected.size.toLocaleString()})</button>
            <button type="button" className="button-quiet" disabled={busy || newMatches === 0} onClick={() => setConfirmAll(true)}>Add all new matches…</button>
          </div>
        )}

        {data?.total === 0 && <p className="message">No articles match. Try fewer words or remove a filter.</p>}

        <ol className="result-list">
          {data?.results.map((article) => (
            <li key={article.id} className="pick-row">
              <input
                type="checkbox"
                aria-label={`Select ${article.title}`}
                checked={article.in_project || selected.has(article.id)}
                disabled={article.in_project}
                onChange={(event) => toggle(article.id, event.target.checked)}
              />
              <div>
                <h2>{article.title}{article.in_project && <span className="tag">In project</span>}</h2>
                <p className="result-meta">{article.publish_date} · {article.source_label} · {article.language_label} · {article.word_count.toLocaleString()} words</p>
                <Snippet parts={article.snippet} />
              </div>
            </li>
          ))}
        </ol>

        {data && data.total > PAGE_SIZE && (
          <nav className="pagination" aria-label="Pages">
            <button type="button" disabled={filters.page <= 1} onClick={() => update({ page: filters.page - 1 })}>Previous</button>
            <span>Page {filters.page.toLocaleString()} of {lastPage.toLocaleString()}</span>
            <button type="button" disabled={filters.page >= lastPage} onClick={() => update({ page: filters.page + 1 })}>Next</button>
          </nav>
        )}
      </section>

      {confirmAll && data && (
        <ConfirmDialog title={`Add ${newMatches.toLocaleString()} articles?`} confirmLabel={`Add ${newMatches.toLocaleString()} articles`} busy={busy} onCancel={() => setConfirmAll(false)} onConfirm={addAll}>
          <p>This adds every new match for this search and these filters, including those on other result pages. Articles can't yet be removed from a project.</p>
        </ConfirmDialog>
      )}
    </div>
  )
}
