import { useEffect, useMemo } from 'react'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router'
import { ApiError, getArticle } from '../api'
import { CodeInProject } from '../components/CodeInProject'
import { formatNumber } from '../format'
import { useApi } from '../useApi'

export function ArticlePage() {
  const { id = '' } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const targetPos = searchParams.get('pos') ? parseInt(searchParams.get('pos')!, 10) : null
  const targetQuery = searchParams.get('q')

  // An article opened directly has no results page to go back to.
  const goBack = () => (location.key === 'default' ? navigate('/search') : navigate(-1))
  const { data: article, error, loading } = useApi((signal) => getArticle(id, signal), id)

  const renderedText = useMemo(() => {
    if (targetPos === null || !article?.full_text) return article?.full_text ?? ''
    const text = article.full_text
    const len = targetQuery ? targetQuery.length : 12
    const start = Math.max(0, targetPos)
    const end = Math.min(text.length, start + len)
    const before = text.slice(0, start)
    const match = text.slice(start, end)
    const after = text.slice(end)
    return (
      <>
        {before}
        <mark
          id="target-search-match"
          className="hl-search-match"
          style={{
            background: 'var(--amber-3, #fef08a)',
            color: 'var(--amber-11, #854d0e)',
            padding: '2px 4px',
            borderRadius: '3px',
            fontWeight: 600,
            boxShadow: '0 0 0 2px #eab308',
          }}
        >
          {match}
        </mark>
        {after}
      </>
    )
  }, [article?.full_text, targetPos, targetQuery])

  useEffect(() => {
    if (targetPos !== null && article) {
      const timer = setTimeout(() => {
        document.getElementById('target-search-match')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }, 150)
      return () => clearTimeout(timer)
    }
  }, [targetPos, article])

  if (loading) return <p className="result-count">Loading article…</p>
  if (error) {
    const notFound = error instanceof ApiError && error.status === 404
    return (
      <div>
        <p className="message message-error" role="alert">{notFound ? 'This article is not in the corpus.' : error.message}</p>
        <Link to="/search">Back to search</Link>
      </div>
    )
  }
  if (!article) return null

  return (
    <div className="article-layout">
      <aside className="article-meta" aria-label="Article details">
        <button type="button" className="button-quiet back" onClick={goBack}>Back to results</button>
        <dl>
          <dt>Source</dt><dd>{article.source_label}{article.source_type === 'official_press' && <span className="tag">Official press</span>}</dd>
          <dt>Variety</dt><dd>{article.language_label}</dd>
          <dt>Date</dt><dd>{article.publish_date.slice(0, 10)}</dd>
          <dt>Author</dt><dd>{article.author || 'Not available'}</dd>
          {article.category && <><dt>Category</dt><dd>{article.category}</dd></>}
          <dt>Words</dt><dd>{article.word_count.toLocaleString()}</dd>
          <dt>Net sentiment</dt><dd>{formatNumber(article.metrics.net_sentiment, 2)}</dd>
          <dt>Moral words per 1,000</dt><dd>{formatNumber(article.metrics.moral_density)}</dd>
          {article.metrics.readability_score != null && (
            <>
              <dt>Readability</dt>
              <dd>
                {article.metrics.readability_metric}: {formatNumber(article.metrics.readability_score, 1)}
                {article.metrics.readability_grade && (
                  <span style={{ display: 'block', fontSize: '0.85em', opacity: 0.85 }}>
                    {article.metrics.readability_grade}
                  </span>
                )}
              </dd>
            </>
          )}
          <dt>Corpus ID</dt><dd><code>{article.id}</code></dd>
          {article.twin_article_id && (
            <>
              <dt>Twin release</dt>
              <dd>
                <Link to={`/articles/${encodeURIComponent(article.twin_article_id)}`}>
                  Twin press release ({article.language === 'it' ? 'German' : 'Italian'})
                </Link>
              </dd>
            </>
          )}
        </dl>
        <a href={article.url} target="_blank" rel="noreferrer noopener">Open original article</a>
      </aside>
      <article className="article-body">
        <CodeInProject articleId={article.id} />
        <h1>{article.title}</h1>
        <div className="article-text" data-testid="article-text">{renderedText}</div>
      </article>
    </div>
  )
}
