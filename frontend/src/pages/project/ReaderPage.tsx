import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router'
import { type Annotation, ApiError, type MyStatus, type Project, type UserBrief, getProgress, getProjectArticle, leaveArticle, listAnnotations, listCodes, sendHeartbeat, setProgress } from '../../api'
import { useAuth } from '../../auth'
import { flattenCodeTree } from '../../codebook'
import { ArticleReader, type Highlight, type PendingSelection } from '../../components/ArticleReader'
import { ErrorMessage } from '../../components/Message'
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
  const [scope, setScope] = useState<'mine' | 'all'>('mine')
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [pending, setPending] = useState<PendingSelection | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const others = usePresence(project.id, articleId)
  const progressAction = useAction()
  const key = `${project.id}/${articleId}`
  const article = useApi((signal) => getProjectArticle(project.id, articleId, signal), key)
  const codes = useApi((signal) => listCodes(project.id, signal), project.id)
  const annotations = useApi((signal) => listAnnotations(project.id, articleId, scope, signal), `${key}/${scope}`)
  const progress = useApi((signal) => getProgress(project.id, articleId, signal), key)
  const canCode = project.role !== null && !project.archived

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

  const pathOf = useCallback((codeId: string) => codeInfo.get(codeId)?.path ?? 'Unknown code', [codeInfo])

  const startCoding = useCallback((selection: PendingSelection) => {
    setNotice(null)
    setSelectedIds([])
    setPending(selection)
  }, [])

  const selectSegments = useCallback((ids: string[]) => {
    setPending(null)
    setSelectedIds(ids)
  }, [])

  const selectFromList = useCallback((segment: Annotation) => {
    setPending(null)
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
  const status = progress.data?.status ?? 'not_started'
  const changeStatus = (next: 'in_progress' | 'done') => void progressAction.run(async () => {
    await setProgress(project.id, articleId, next)
    progress.reload()
  })
  const handleTextSelected = (selection: PendingSelection) => {
    // A selection of only spaces or line breaks has nothing to code.
    if (trimSelection(data.full_text, selection.start, selection.end)) startCoding(selection)
  }

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
        </div>
      </div>

      {others.length > 0 && (
        <p className="presence-banner" role="status">
          {joinNames(others)} {others.length === 1 ? 'is' : 'are'} also working on this article. Your work stays separate, so you can keep going.
        </p>
      )}
      <ErrorMessage error={progressAction.error} />

      <div className="reader-layout">
        <ArticleReader
          text={data.full_text}
          highlights={highlights}
          selectedIds={selectedIds}
          pending={pending}
          onSelect={selectSegments}
          onTextSelected={canCode ? handleTextSelected : undefined}
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
              onCancel={() => setPending(null)}
              onCodesChanged={codes.reload}
              onSaved={(message) => {
                setPending(null)
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
