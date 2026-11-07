import { type FormEvent, useEffect, useState } from 'react'
import { type Annotation, type Code, type Project, deleteAnnotation, updateAnnotation } from '../../api'
import { flattenCodeTree } from '../../codebook'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { ErrorMessage } from '../../components/Message'
import { useAction } from '../../useAction'

function ReadOnlyDetail({ segment, path }: { segment: Annotation; path: string }) {
  return (
    <>
      <strong>{path}</strong>
      <span className="label">{segment.user.display_name} · {new Date(segment.created_at).toLocaleDateString()}</span>
      <p>{segment.quote}</p>
      {segment.memo && (
        <>
          <span className="label">Memo</span>
          <p>{segment.memo}</p>
        </>
      )}
    </>
  )
}

function OwnSegmentEditor({ project, segment, codes, onChanged, onDeleted }: {
  project: Project
  segment: Annotation
  codes: Code[]
  onChanged: () => void
  onDeleted: () => void
}) {
  const [codeId, setCodeId] = useState(segment.code_id)
  const [memo, setMemo] = useState(segment.memo)
  const [confirming, setConfirming] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const { busy, error, run } = useAction()
  const nodes = flattenCodeTree(codes)

  // Show the latest version after a save or a conflict. Staying mounted keeps any message visible.
  useEffect(() => {
    setCodeId(segment.code_id)
    setMemo(segment.memo)
  }, [segment.revision, segment.code_id, segment.memo])

  const save = (event: FormEvent) => {
    event.preventDefault()
    setNotice(null)
    void run(async () => {
      const saved = await updateAnnotation(project.id, segment.id, { revision: segment.revision, code_id: codeId, memo })
      setNotice(saved.merged_from ? `"${saved.merged_from}" was merged, so this now uses the code it became.` : 'Saved.')
    }).then(onChanged)
  }

  return (
    <form className="stack" onSubmit={save}>
      <ErrorMessage error={error} />
      {notice && <p className="hint" role="status">{notice}</p>}
      <p className="coding-quote">{segment.quote}</p>
      <label className="field">
        Code
        <select value={codeId} onChange={(event) => setCodeId(event.target.value)}>
          {nodes.map((node) => <option key={node.code.id} value={node.code.id}>{node.path}</option>)}
        </select>
      </label>
      <label className="field">
        Memo
        <textarea rows={3} value={memo} onChange={(event) => setMemo(event.target.value)} />
      </label>
      <div className="row">
        <button type="submit" disabled={busy}>Save changes</button>
        <button type="button" className="button-quiet button-danger-quiet" disabled={busy} onClick={() => setConfirming(true)}>Delete…</button>
      </div>
      {confirming && (
        <ConfirmDialog
          title="Delete this segment?"
          confirmLabel="Delete segment"
          danger
          busy={busy}
          onCancel={() => setConfirming(false)}
          onConfirm={() => {
            setConfirming(false)
            void run(async () => {
              await deleteAnnotation(project.id, segment)
              onDeleted()
            }).then((ok) => {
              if (!ok) onChanged()
            })
          }}
        >
          <p className="coding-quote">{segment.quote}</p>
        </ConfirmDialog>
      )}
    </form>
  )
}

export function SegmentPanel({ project, segments, codes, paths, userId, canEdit, onChanged, onDeleted, onClose }: {
  project: Project
  segments: Annotation[]
  codes: Code[]
  paths: (codeId: string) => string
  userId: string | undefined
  canEdit: boolean
  onChanged: () => void
  onDeleted: () => void
  onClose: () => void
}) {
  return (
    <div className="panel" aria-label="Selected segments">
      <div className="page-title">
        <h2>{segments.length === 1 ? 'Segment' : `${segments.length} segments`}</h2>
        <button type="button" className="button-quiet" onClick={onClose}>Close</button>
      </div>
      {segments.map((segment) => (
        <div key={segment.id} className="segment-detail">
          {canEdit && segment.user.id === userId ? (
            <OwnSegmentEditor project={project} segment={segment} codes={codes} onChanged={onChanged} onDeleted={onDeleted} />
          ) : <ReadOnlyDetail segment={segment} path={paths(segment.code_id)} />}
        </div>
      ))}
    </div>
  )
}
