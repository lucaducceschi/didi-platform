import { type FormEvent, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { type SearchFilters, getCorpusSummary, searchArticles } from '../api'
import { Snippet } from '../components/Snippet'
import { useApi } from '../useApi'

const PAGE_SIZE = 20

function readFilters(params: URLSearchParams): SearchFilters {
  return {
    q: params.get('q') ?? '',
    sources: params.getAll('source'),
    languages: params.getAll('language'),
    page: Math.max(1, Number(params.get('page')) || 1),
  }
}

export function FacetGroup({ legend, name, options, selected, onChange }: {
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
              onChange(event.target.checked ? [...selected, option.id] : selected.filter((value) => value !== option.id))
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
  const summary = useApi((signal) => getCorpusSummary(signal), 'summary')
  const search = useApi((signal) => searchArticles(filters, signal), params.toString())

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

  const total = search.data?.total ?? 0
  const lastPage = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="search-layout">
      <aside className="filters" aria-label="Filters">
        {summary.data && (
          <>
            <FacetGroup legend="Language variety" name="language" options={summary.data.languages} selected={filters.languages} onChange={(languages) => update({ languages })} />
            <FacetGroup legend="Source" name="source" options={summary.data.sources} selected={filters.sources} onChange={(sources) => update({ sources })} />
            <p className="corpus-note">
              {summary.data.total_articles.toLocaleString()} articles, {summary.data.min_date.slice(0, 4)}–{summary.data.max_date.slice(0, 4)}.
              {' '}German and Italian coverage is mostly 2024 to May 2025.
            </p>
          </>
        )}
      </aside>

      <section className="results" aria-label="Search results">
        <form className="search-form" role="search" onSubmit={submit}>
          <label htmlFor="search-query">Search the corpus</label>
          <div className="search-row">
            <input id="search-query" type="search" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="scuola, Autonomie, lingaz…" />
            <button type="submit">Search</button>
          </div>
        </form>

        {search.error && <p className="message message-error" role="alert">{search.error.message}</p>}
        {!search.error && (
          <p className="result-count" aria-live="polite">
            {search.loading ? 'Searching…' : `${total.toLocaleString()} ${total === 1 ? 'article' : 'articles'}`}
          </p>
        )}
        {!search.loading && !search.error && total === 0 && (
          <p className="message">No articles match. Try fewer words or remove a filter.</p>
        )}

        <ol className="result-list">
          {search.data?.results.map((article) => (
            <li key={article.id}>
              <h2><Link to={`/articles/${encodeURIComponent(article.id)}`}>{article.title}</Link></h2>
              <p className="result-meta">
                {article.publish_date.slice(0, 10)} · {article.source_label} · {article.language_label} · {article.word_count.toLocaleString()} words
              </p>
              <Snippet parts={article.snippet} />
            </li>
          ))}
        </ol>

        {total > PAGE_SIZE && (
          <nav className="pagination" aria-label="Pages">
            <button type="button" disabled={filters.page <= 1} onClick={() => update({ page: filters.page - 1 })}>Previous</button>
            <span>Page {filters.page.toLocaleString()} of {lastPage.toLocaleString()}</span>
            <button type="button" disabled={filters.page >= lastPage} onClick={() => update({ page: filters.page + 1 })}>Next</button>
          </nav>
        )}
      </section>
    </div>
  )
}
