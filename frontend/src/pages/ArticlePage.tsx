import { Link, useLocation, useNavigate, useParams } from 'react-router'
import { ApiError, getArticle } from '../api'
import { CodeInProject } from '../components/CodeInProject'
import { useApi } from '../useApi'

const formatNumber = (value: number | null, digits = 1) => (value === null ? 'Not available' : value.toFixed(digits))

export function ArticlePage() {
  const { id = '' } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  // An article opened directly has no results page to go back to.
  const goBack = () => (location.key === 'default' ? navigate('/search') : navigate(-1))
  const { data: article, error, loading } = useApi((signal) => getArticle(id, signal), id)

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
          <dt>Source</dt><dd>{article.source_label}</dd>
          <dt>Variety</dt><dd>{article.language_label}</dd>
          <dt>Date</dt><dd>{article.publish_date.slice(0, 10)}</dd>
          <dt>Author</dt><dd>{article.author || 'Not available'}</dd>
          {article.category && <><dt>Category</dt><dd>{article.category}</dd></>}
          <dt>Words</dt><dd>{article.word_count.toLocaleString()}</dd>
          <dt>Net sentiment</dt><dd>{formatNumber(article.metrics.net_sentiment, 2)}</dd>
          <dt>Moral words per 1,000</dt><dd>{formatNumber(article.metrics.moral_density)}</dd>
          <dt>Corpus ID</dt><dd><code>{article.id}</code></dd>
        </dl>
        <a href={article.url} target="_blank" rel="noreferrer noopener">Open original article</a>
      </aside>
      <article className="article-body">
        <CodeInProject articleId={article.id} />
        <h1>{article.title}</h1>
        <div className="article-text" data-testid="article-text">{article.full_text}</div>
      </article>
    </div>
  )
}
