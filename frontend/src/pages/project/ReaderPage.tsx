import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useParams, useSearchParams } from 'react-router'
import { type Annotation, ApiError, type Code, type MyStatus, type Project, type UserBrief, getArticleDictionarySpans, getProgress, getProjectArticle, leaveArticle, listAnnotations, listCodes, sendHeartbeat, setProgress } from '../../api'
import { useAuth } from '../../auth'
import { flattenCodeTree } from '../../codebook'
import { ArticleReader, type Highlight, type PendingSelection } from '../../components/ArticleReader'
import { QuickCodeCard } from '../../components/QuickCodeCard'
import { ErrorMessage } from '../../components/Message'
import { formatNumber } from '../../format'
import { trimSelection } from '../../selection'
import { useAction } from '../../useAction'
import { useApi } from '../../useApi'
import { CodingPanel } from './CodingPanel'
import { SegmentPanel } from './SegmentPanel'

interface CodeInfo {
  path: string
  color: string
  order: number
}

const HEARTBEAT_MS = 30_000

function usePresence(projectId: string, articleId: string): UserBrief[] {
  const [others, setOthers] = useState<UserBrief[]>([])

  useEffect(() => {
    const controller = new AbortController()
    const beat = () => {
      sendHeartbeat(projectId, articleId, controller.signal)
        .then((result) => setOthers(result.others))
        .catch(() => {}) // Presence is only a courtesy, so a failure must never get in the way of coding.
    }
    const leave = () => leaveArticle(projectId, articleId)
    beat()
    const timer = window.setInterval(beat, HEARTBEAT_MS)
    window.addEventListener('pagehide', leave)
    return () => {
      controller.abort()
      window.clearInterval(timer)
      window.removeEventListener('pagehide', leave)
      leave()
    }
  }, [projectId, articleId])

  return others
}

const joinNames = (people: UserBrief[]) => people.map((person) => person.display_name).join(', ')

const STATUS_TEXT: Record<MyStatus, string> = {
  not_started: 'Not started',
  in_progress: 'In progress',
  done: 'Done',
}

export function ReaderPage({ project }: { project: Project }) {
  const { articleId = '' } = useParams()
  const { user } = useAuth()
  const [searchParams] = useSearchParams()
  const targetSegment = searchParams.get('segment')
  const targetPosStr = searchParams.get('pos')
  const targetPos = targetPosStr ? parseInt(targetPosStr, 10) : null
  const targetQuery = searchParams.get('q')
  const autoCode = searchParams.get('code') === '1'
  const backToPassages = (useLocation().state as { back?: string } | null)?.back
  // A passage opened from the list may be someone else's, so it has to be in view.
  const [scope, setScope] = useState<'mine' | 'all'>(targetSegment ? 'all' : 'mine')
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [pending, setPending] = useState<PendingSelection | null>(null)
  const [pendingCoords, setPendingCoords] = useState<{ top: number; left: number } | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [showDictionaryLayer, setShowDictionaryLayer] = useState(false)
  const others = usePresence(project.id, articleId)
  const progressAction = useAction()
  const key = `${project.id}/${articleId}`
  const article = useApi((signal) => getProjectArticle(project.id, articleId, signal), key)
  const codes = useApi((signal) => listCodes(project.id, signal), project.id)
  const annotations = useApi((signal) => listAnnotations(project.id, articleId, scope, signal), `${key}/${scope}`)
  const progress = useApi((signal) => getProgress(project.id, articleId, signal), key)
  const dictSpans = useApi(
    (signal) => getArticleDictionarySpans(project.id, articleId, signal),
    showDictionaryLayer ? `dict-spans/${articleId}` : 'dict-disabled',
  )
  const canCode = project.role !== null && !project.archived

  const codeInfo = useMemo(() => {
    const info = new Map<string, CodeInfo>()
    flattenCodeTree(codes.data ?? []).forEach((node, order) => info.set(node.code.id, { path: node.path, color: node.code.color, order }))
    return info
  }, [codes.data])

  const quickCodes = useMemo<Code[]>(() => {
    if (!codes.data) return []
    const counts = new Map<string, number>()
    for (const ann of annotations.data ?? []) {
      counts.set(ann.code_id, (counts.get(ann.code_id) ?? 0) + 1)
    }
    const sorted = [...codes.data].sort((a, b) => {
      const diff = (counts.get(b.id) ?? 0) - (counts.get(a.id) ?? 0)
      if (diff !== 0) return diff
      return a.name.localeCompare(b.name)
    })
    return sorted.slice(0, 5)
  }, [codes.data, annotations.data])

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

  const mergedHighlights = useMemo<Highlight[]>(() => {
    if (!showDictionaryLayer || !dictSpans.data) return highlights
    const dictHighlights: Highlight[] = dictSpans.data.map((ds, idx) => ({
      id: `dict-${idx}`,
      start: ds.start,
      end: ds.end,
      color: ds.color,
      label: `${ds.label}`,
      mine: false,
    }))
    return [...dictHighlights, ...highlights]
  }, [highlights, showDictionaryLayer, dictSpans.data])

  const groups = useMemo(() => {
    const byCode = new Map<string, Annotation[]>()
    for (const segment of active) byCode.set(segment.code_id, [...(byCode.get(segment.code_id) ?? []), segment])
    return [...byCode.entries()].sort(([a], [b]) => (codeInfo.get(a)?.order ?? 1e9) - (codeInfo.get(b)?.order ?? 1e9))
  }, [active, codeInfo])

  const pathOf = useCallback((codeId: string) => codeInfo.get(codeId)?.path ?? 'Unknown code', [codeInfo])

  const startCoding = useCallback((selection: PendingSelection, coords?: { top: number; left: number }) => {
    setNotice(null)
    setSelectedIds([])
    setPending(selection)
    setPendingCoords(coords ?? null)
  }, [])

  const selectSegments = useCallback((ids: string[]) => {
    setPending(null)
    setPendingCoords(null)
    setSelectedIds(ids)
  }, [])

  const selectFromList = useCallback((segment: Annotation) => {
    setPending(null)
    setPendingCoords(null)
    setSelectedIds([segment.id])
    document.querySelector(`[data-segments~="${segment.id}"]`)?.scrollIntoView({ block: 'center' })
  }, [])

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        if (pending) {
          event.preventDefault()
          setPending(null)
          setPendingCoords(null)
          window.getSelection()?.removeAllRanges()
        } else if (selectedIds.length > 0) {
          event.preventDefault()
          setSelectedIds([])
          window.getSelection()?.removeAllRanges()
        }
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [pending, selectedIds])

  const openedTarget = useRef<string | null>(null)
  useEffect(() => {
    if (!targetSegment || openedTarget.current === targetSegment || !annotations.data || !article.data) return
    openedTarget.current = targetSegment
    if (annotations.data.some((segment) => segment.id === targetSegment)) {
      setSelectedIds([targetSegment])
      document.querySelector(`[data-segments~="${targetSegment}"]`)?.scrollIntoView({ block: 'center' })
    } else {
      setNotice('That passage no longer exists. Its coder may have deleted it.')
    }
  }, [targetSegment, annotations.data, article.data])

  const openedPos = useRef<number | null>(null)
  useEffect(() => {
    if (targetPos === null || openedPos.current === targetPos || !article.data) return
    openedPos.current = targetPos
    const textLen = article.data.full_text.length
    const start = Math.max(0, Math.min(targetPos, textLen))
    const end = Math.min(textLen, start + (targetQuery?.length ?? 12))

    setTimeout(() => {
      const el = document.querySelector(`[data-start="${start}"]`) ||
        document.querySelector(`.didi-reader [data-start]`)
      el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 150)

    if (autoCode && canCode) {
      startCoding({ start, end })
    }
  }, [targetPos, targetQuery, autoCode, article.data, canCode, startCoding])

  const backLink = backToPassages
    ? <Link to={backToPassages}>Back to passages</Link>
    : <Link to={`/projects/${project.id}/articles`}>Back to articles</Link>

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
  const status = progress.data?.status ?? 'not_started'
  const changeStatus = (next: 'in_progress' | 'done') => void progressAction.run(async () => {
    await setProgress(project.id, articleId, next)
    progress.reload()
  })
  const handleTextSelected = (selection: PendingSelection, coords?: { top: number; left: number }) => {
    // A selection of only spaces or line breaks has nothing to code.
    if (trimSelection(data.full_text, selection.start, selection.end)) startCoding(selection, coords)
  }

  return (
    <div className="stack">
      <div>{backLink}</div>
      <div className="reader-header">
        <div>
          <h2>
            {data.title}
            {data.source_type === 'official_press' && <span className="tag">Official press</span>}
          </h2>
          <p className="result-meta">
            {data.publish_date.slice(0, 10)} · {data.source_label} · {data.language_label} · {data.author || 'No author'} · {data.word_count.toLocaleString()} words ·{' '}
            <a href={data.url} target="_blank" rel="noreferrer noopener">Original article</a>
            {data.twin_article_id && (
              <>
                {' · '}
                <Link to={`/projects/${project.id}/articles/${encodeURIComponent(data.twin_article_id)}`}>
                  Twin press release ({data.language === 'it' ? 'German' : 'Italian'})
                </Link>
              </>
            )}
          </p>
          <div className="row" style={{ gap: '0.5rem', marginTop: '0.4rem', flexWrap: 'wrap' }}>
            {data.metrics.readability_score != null && (
              <span className="tag" title={data.metrics.readability_grade || undefined}>
                📖 {data.metrics.readability_metric}: {formatNumber(data.metrics.readability_score, 1)}
              </span>
            )}
            {data.metrics.net_sentiment != null && (
              <span className="tag">
                ⚖️ Sentiment: {data.metrics.net_sentiment > 0 ? `+${formatNumber(data.metrics.net_sentiment, 2)}` : formatNumber(data.metrics.net_sentiment, 2)}
              </span>
            )}
            {data.metrics.moral_density != null && data.metrics.moral_density > 0 && (
              <span className="tag">
                🧭 Moral: {formatNumber(data.metrics.moral_density, 1)}/k
              </span>
            )}
          </div>
        </div>
        <div className="reader-actions">
          {project.role && (
            <>
              <span className="status-pill">Your status: {STATUS_TEXT[status]}</span>
              {canCode && status !== 'done' && <button type="button" className="button-quiet" disabled={progressAction.busy} onClick={() => changeStatus('done')}>Mark done</button>}
              {canCode && status === 'done' && <button type="button" className="button-quiet" disabled={progressAction.busy} onClick={() => changeStatus('in_progress')}>Reopen</button>}
            </>
          )}
          <div className="segmented" role="group" aria-label="Whose segments to show">
            <button type="button" aria-pressed={scope === 'mine'} onClick={() => { setScope('mine'); setSelectedIds([]) }}>Mine</button>
            <button type="button" aria-pressed={scope === 'all'} onClick={() => { setScope('all'); setSelectedIds([]) }}>All coders</button>
          </div>
          <button
            type="button"
            className={showDictionaryLayer ? 'button' : 'button-quiet'}
            style={{ fontSize: '12px' }}
            onClick={() => setShowDictionaryLayer(!showDictionaryLayer)}
            title="Toggle word-layer dictionary highlights for Moral Foundations, Ingroup Pronouns, and Konjunktiv I"
          >
            {showDictionaryLayer ? '👁️ Hide Dictionary Layer' : '🔍 Dictionary Layer'}
          </button>
        </div>
      </div>

      {showDictionaryLayer && (
        <div
          className="row"
          style={{
            gap: '12px',
            fontSize: '11px',
            padding: '8px 14px',
            backgroundColor: 'var(--canvas-subtle, rgba(0,0,0,0.03))',
            borderRadius: '6px',
            border: '1px solid var(--border)',
            flexWrap: 'wrap',
            alignItems: 'center',
          }}
        >
          <span style={{ fontWeight: 600 }}>Dictionary Layer:</span>
          <span><span style={{ display: 'inline-block', width: 8, height: 8, backgroundColor: '#2ca02c', borderRadius: 2, marginRight: 4 }} />Care</span>
          <span><span style={{ display: 'inline-block', width: 8, height: 8, backgroundColor: '#1f77b4', borderRadius: 2, marginRight: 4 }} />Fairness</span>
          <span><span style={{ display: 'inline-block', width: 8, height: 8, backgroundColor: '#ff7f0e', borderRadius: 2, marginRight: 4 }} />Loyalty</span>
          <span><span style={{ display: 'inline-block', width: 8, height: 8, backgroundColor: '#9467bd', borderRadius: 2, marginRight: 4 }} />Authority</span>
          <span><span style={{ display: 'inline-block', width: 8, height: 8, backgroundColor: '#d62728', borderRadius: 2, marginRight: 4 }} />Sanctity</span>
          <span><span style={{ display: 'inline-block', width: 8, height: 8, backgroundColor: '#8c564b', borderRadius: 2, marginRight: 4 }} />Ingroup (wir/noi)</span>
          {data.language === 'de' && <span><span style={{ display: 'inline-block', width: 8, height: 8, backgroundColor: '#e377c2', borderRadius: 2, marginRight: 4 }} />Konjunktiv I</span>}
          <span><span style={{ display: 'inline-block', width: 8, height: 8, backgroundColor: '#17becf', borderRadius: 2, marginRight: 4 }} />Direct Quote <span style={{ opacity: 0.7, fontSize: '10px' }}>[unvalidated]</span></span>
          <span style={{ marginLeft: 'auto', color: 'var(--muted)' }}>
            {dictSpans.loading ? 'Scanning words…' : `${dictSpans.data?.length ?? 0} tokens tagged`}
          </span>
        </div>
      )}

      {others.length > 0 && (
        <p className="presence-banner" role="status">
          {joinNames(others)} {others.length === 1 ? 'is' : 'are'} also working on this article. Your work stays separate, so you can keep going.
        </p>
      )}
      <ErrorMessage error={progressAction.error} />

      <div className="reader-layout">
        <ArticleReader
          text={data.full_text}
          highlights={mergedHighlights}
          selectedIds={selectedIds}
          pending={pending}
          popover={
            canCode && pending && pendingCoords ? (
              <QuickCodeCard
                project={project}
                articleId={articleId}
                selection={pending}
                codes={codes.data ?? []}
                quickCodes={quickCodes}
                coords={pendingCoords}
                onSaved={(message) => {
                  setPending(null)
                  setPendingCoords(null)
                  setNotice(message)
                  annotations.reload()
                  codes.reload()
                  progress.reload()
                }}
                onCancel={() => {
                  setPending(null)
                  setPendingCoords(null)
                }}
              />
            ) : null
          }
          onSelect={selectSegments}
          onTextSelected={canCode ? handleTextSelected : undefined}
          onCancelSelection={() => {
            setPending(null)
            setPendingCoords(null)
          }}
        />
        <aside className="reader-side" aria-label="Segments">
          <ErrorMessage error={annotations.error ?? codes.error} />

          {notice && <p className="message" role="status">{notice}</p>}
          {canCode && !pending && selected.length === 0 && <p className="hint">Select text in the article to code it.</p>}

          {pending && (
            <CodingPanel
              key={`${pending.start}-${pending.end}`}
              project={project}
              articleId={articleId}
              text={data.full_text}
              selection={pending}
              codes={codes.data ?? []}
              onCancel={() => {
                setPending(null)
                setPendingCoords(null)
              }}
              onCodesChanged={codes.reload}
              onSaved={(message) => {
                setPending(null)
                setPendingCoords(null)
                setNotice(message)
                annotations.reload()
                codes.reload()
                progress.reload()
              }}
            />
          )}

          {selected.length > 0 && (
            <SegmentPanel
              project={project}
              segments={selected}
              codes={codes.data ?? []}
              paths={pathOf}
              userId={user?.id}
              canEdit={canCode}
              onChanged={annotations.reload}
              onDeleted={() => { setSelectedIds([]); annotations.reload(); codes.reload() }}
              onClose={() => setSelectedIds([])}
            />
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
