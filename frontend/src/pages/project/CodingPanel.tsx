import { type FormEvent, useMemo, useState } from 'react'
import { type Code, type Project, createAnnotation, createCode } from '../../api'
import { flattenCodeTree } from '../../codebook'
import { ErrorMessage } from '../../components/Message'
import { trimSelection } from '../../selection'
import { useAction } from '../../useAction'

export function CodingPanel({ project, articleId, text, selection, codes, onSaved, onCodesChanged, onCancel }: {
  project: Project
  articleId: string
  text: string
  selection: { start: number; end: number }
  codes: Code[]
  onSaved: (message: string | null) => void
  onCodesChanged: () => void
  onCancel: () => void
}) {
  const [filter, setFilter] = useState('')
  const [codeId, setCodeId] = useState('')
  const [memo, setMemo] = useState('')
  const [newCode, setNewCode] = useState('')
  const { busy, error, run } = useAction()
  const trimmed = trimSelection(text, selection.start, selection.end)

  const nodes = useMemo(() => flattenCodeTree(codes), [codes])
  const visible = useMemo(() => {
    const term = filter.trim().toLowerCase()
    return term ? nodes.filter((node) => node.path.toLowerCase().includes(term) || node.code.definition.toLowerCase().includes(term)) : nodes
  }, [filter, nodes])

  const save = (event: FormEvent) => {
    event.preventDefault()
    void run(async () => {
      const saved = await createAnnotation(project.id, articleId, { start: selection.start, end: selection.end, code_id: codeId, memo })
      const current = codes.find((code) => code.id === saved.code_id)
      let message: string | null = null
      if (saved.merged_from) {
        message = `"${saved.merged_from}" was merged while you were working, so this was saved under "${current?.name ?? 'the new code'}".`
      } else if (saved.created === false) {
        message = 'You already coded this passage with this code, so nothing new was added.'
      }
      onSaved(message)
    }).then((ok) => {
      if (!ok) onCodesChanged()
    })
  }

  const addCode = () => void run(async () => {
    const created = await createCode(project.id, { name: newCode, parent_id: null, definition: '' })
    setNewCode('')
    setFilter('')
    setCodeId(created.id)
    onCodesChanged()
  })

  return (
    <form className="panel stack" aria-label="Code this passage" onSubmit={save} onKeyDown={(event) => { if (event.key === 'Escape') onCancel() }}>
      <div className="page-title">
        <h2>Code this passage</h2>
        <button type="button" className="button-quiet" onClick={onCancel}>Cancel</button>
      </div>
      <ErrorMessage error={error} />
      <p className="coding-quote" data-testid="pending-quote">{trimmed?.quote}</p>
      {codes.length > 5 && (
        <label className="field">
          Find a code
          <input type="search" value={filter} onChange={(event) => setFilter(event.target.value)} />
        </label>
      )}
      {codes.length === 0 ? <p className="hint">This codebook has no codes yet. Add the first one below.</p> : (
        <fieldset className="code-picker">
          <legend>Code</legend>
          {visible.length === 0 && <p className="hint code-option">No codes match.</p>}
          {visible.map(({ code, path }) => (
            <label key={code.id} className="code-option">
              <input type="radio" name="code" checked={codeId === code.id} onChange={() => setCodeId(code.id)} />
              <i className="swatch" style={{ background: code.color }} aria-hidden="true" />
              <span>
                {path}
                {code.definition && <small>{code.definition}</small>}
              </span>
            </label>
          ))}
        </fieldset>
      )}
      <div className="field">
        <label htmlFor="new-code-name">New code</label>
        <div className="inline-field">
          <input id="new-code-name" value={newCode} onChange={(event) => setNewCode(event.target.value)} onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault()
              if (newCode.trim()) addCode()
            }
          }} />
          <button type="button" className="button-quiet" disabled={busy || !newCode.trim()} onClick={addCode}>Add</button>
        </div>
      </div>
      <label className="field">
        Memo
        <textarea rows={2} value={memo} onChange={(event) => setMemo(event.target.value)} />
      </label>
      <div><button type="submit" disabled={busy || !codeId}>Save segment</button></div>
    </form>
  )
}
