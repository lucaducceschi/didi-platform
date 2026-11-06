import { useCallback, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router'
import { type Annotation, ApiError, type Project, getProjectArticle, listAnnotations, listCodes } from '../../api'
import { useAuth } from '../../auth'
import { flattenCodeTree } from '../../codebook'
import { ArticleReader, type Highlight } from '../../components/ArticleReader'
import { ErrorMessage } from '../../components/Message'
import { useApi } from '../../useApi'

interface CodeInfo {
  path: string
  color: string
  order: number
}

function SegmentDetail({ segment, code }: { segment: Annotation; code?: CodeInfo }) {
  return (
    <div className="segment-detail">
      <strong>{code?.path ?? 'Unknown code'}</strong>
      <span className="label">{segment.user.display_name} · {new Date(segment.created_at).toLocaleDateString()}</span>
      <p>{segment.quote}</p>
      {segment.memo && (
        <>
          <span className="label">Memo</span>
          <p>{segment.memo}</p>
        </>
      )}
    </div>
  )
}

export function ReaderPage({ project }: { project: Project }) {
  const { articleId = '' } = useParams()
  const { user } = useAuth()
  const [scope, setScope] = useState<'mine' | 'all'>('mine')
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const key = `${project.id}/${articleId}`
  const article = useApi((signal) => getProjectArticle(project.id, articleId, signal), key)
  const codes = useApi((signal) => listCodes(project.id, signal), project.id)
  const annotations = useApi((signal) => listAnnotations(project.id, articleId, scope, signal), `${key}/${scope}`)

  const codeInfo = useMemo(() => {
    const info = new Map<string, CodeInfo>()
    flattenCodeTree(codes.data ?? []).forEach((node, order) => info.set(node.code.id, { path: node.path, color: node.code.color, order }))
    return info
  }, [codes.data])

  const segments = useMemo(() => annotations.data ?? [], [annotations.data])
  const active = useMemo(() => segments.filter((segment) => segment.status === 'active'), [segments])
  const stale = useMemo(() => segments.filter((segment) => segment.status === 'stale'), [segments])

  const highlights = useMemo<Highlight[]>(
    () => active.map((segment) => ({
      id: segment.id,
      start: segment.start_pos,
      end: segment.end_pos,
      color: codeInfo.get(segment.code_id)?.color ?? '#888888',
      label: `${codeInfo.get(segment.code_id)?.path ?? 'Unknown code'} · ${segment.user.display_name}`,
      mine: segment.user.id === user?.id,
    })),
    [active, codeInfo, user?.id],
  )

  const groups = useMemo(() => {
    const byCode = new Map<string, Annotation[]>()
    for (const segment of active) byCode.set(segment.code_id, [...(byCode.get(segment.code_id) ?? []), segment])
    return [...byCode.entries()].sort(([a], [b]) => (codeInfo.get(a)?.order ?? 1e9) - (codeInfo.get(b)?.order ?? 1e9))
  }, [active, codeInfo])

  const selectFromList = useCallback((segment: Annotation) => {
    setSelectedIds([segment.id])
    document.querySelector(`[data-segments~="${segment.id}"]`)?.scrollIntoView({ block: 'center' })
  }, [])

  const backLink = <Link to={`/projects/${project.id}/articles`}>Back to articles</Link>

  if (article.error) {
    const notFound = article.error instanceof ApiError && article.error.status === 404
    return (
      <div className="stack">
        <ErrorMessage error={notFound ? "This article isn't in this project." : article.error} />
        <div>{backLink}</div>
      </div>
    )
  }
  if (!article.data) return <p className="result-count">Loading article…</p>

  const selected = segments.filter((segment) => selectedIds.includes(segment.id))
  const data = article.data

  return (
    <div className="stack">
      <div>{backLink}</div>
      <div className="reader-header">
        <div>
          <h2>{data.title}</h2>
          <p className="result-meta">
            {data.publish_date.slice(0, 10)} · {data.source_label} · {data.language_label} · {data.author || 'No author'} · {data.word_count.toLocaleString()} words ·{' '}
            <a href={data.url} target="_blank" rel="noreferrer noopener">Original article</a>
          </p>
        </div>
        <div className="segmented" role="group" aria-label="Whose segments to show">
          <button type="button" aria-pressed={scope === 'mine'} onClick={() => { setScope('mine'); setSelectedIds([]) }}>Mine</button>
          <button type="button" aria-pressed={scope === 'all'} onClick={() => { setScope('all'); setSelectedIds([]) }}>All coders</button>
        </div>
      </div>

      <div className="reader-layout">
        <ArticleReader text={data.full_text} highlights={highlights} selectedIds={selectedIds} onSelect={setSelectedIds} />
        <aside className="reader-side" aria-label="Segments">
          <ErrorMessage error={annotations.error ?? codes.error} />

          {selected.length > 0 && (
            <div className="panel">
              <div className="page-title">
                <h2>{selected.length === 1 ? 'Segment' : `${selected.length} segments`}</h2>
                <button type="button" className="button-quiet" onClick={() => setSelectedIds([])}>Close</button>
              </div>
              {selected.map((segment) => <SegmentDetail key={segment.id} segment={segment} code={codeInfo.get(segment.code_id)} />)}
            </div>
          )}

          {stale.length > 0 && (
            <div className="panel stack">
              <h2>To review ({stale.length})</h2>
              <p className="hint">The article's text changed, so these passages can't be placed. They are kept, not deleted.</p>
              {stale.map((segment) => (
                <button key={segment.id} type="button" className="segment-item" aria-pressed={selectedIds.includes(segment.id)} onClick={() => setSelectedIds([segment.id])}>
                  <span className="segment-quote">{segment.quote}</span>
                  <span className="segment-by">{codeInfo.get(segment.code_id)?.path ?? 'Unknown code'} · {segment.user.display_name}</span>
                </button>
              ))}
            </div>
          )}

          {annotations.data && active.length === 0 && stale.length === 0 && (
            <p className="message">{scope === 'mine' ? "You haven't coded anything in this article yet." : 'Nobody has coded anything in this article yet.'}</p>
          )}

          {groups.map(([codeId, items]) => {
            const code = codeInfo.get(codeId)
            return (
              <div key={codeId} className="segment-group">
                <h3><span className="swatch" style={{ background: code?.color ?? '#888888' }} aria-hidden="true" />{code?.path ?? 'Unknown code'} ({items.length})</h3>
                {items.map((segment) => (
                  <button key={segment.id} type="button" className="segment-item" aria-pressed={selectedIds.includes(segment.id)} onClick={() => selectFromList(segment)}>
                    <span className="segment-quote">{segment.quote}</span>
                    {scope === 'all' && <span className="segment-by">{segment.user.display_name}</span>}
                  </button>
                ))}
              </div>
            )
          })}
        </aside>
      </div>
    </div>
  )
}
