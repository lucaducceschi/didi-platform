import { type FormEvent, useEffect, useState } from 'react'
import { type Code, type MergePreview, type Project, createCode, deleteCode, getMergePreview, listCodes, mergeCodes, updateCode } from '../../api'
import { allowedParents, flattenCodeTree } from '../../codebook'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { ErrorMessage } from '../../components/Message'
import { useAction } from '../../useAction'
import { useApi } from '../../useApi'

const pluralize = (count: number, one: string) => `${count.toLocaleString()} ${one}${count === 1 ? '' : 's'}`

function AddCodeForm({ project, codes, onAdded }: { project: Project; codes: Code[]; onAdded: () => void }) {
  const [name, setName] = useState('')
  const [parent, setParent] = useState('')
  const [definition, setDefinition] = useState('')
  const { busy, error, run } = useAction()

  const submit = (event: FormEvent) => {
    event.preventDefault()
    void run(async () => {
      await createCode(project.id, { name, parent_id: parent || null, definition })
      setName('')
      setDefinition('')
      onAdded()
    })
  }

  return (
    <form className="panel stack" onSubmit={submit}>
      <h2>Add a code</h2>
      <ErrorMessage error={error} />
      <label className="field">Name<input required value={name} onChange={(event) => setName(event.target.value)} /></label>
      <label className="field">
        Inside
        <select value={parent} onChange={(event) => setParent(event.target.value)}>
          <option value="">Top level</option>
          {flattenCodeTree(codes).map((node) => <option key={node.code.id} value={node.code.id}>{node.path}</option>)}
        </select>
      </label>
      <label className="field">
        Definition
        <textarea rows={2} value={definition} onChange={(event) => setDefinition(event.target.value)} placeholder="When should this code be used?" />
      </label>
      <div><button type="submit" disabled={busy}>Add code</button></div>
    </form>
  )
}

function MergeDialog({ project, source, target, onDone, onCancel }: {
  project: Project
  source: Code
  target: Code
  onDone: () => void
  onCancel: () => void
}) {
  const [preview, setPreview] = useState<MergePreview | null>(null)
  const { busy, error, run } = useAction()

  useEffect(() => {
    void run(async () => setPreview(await getMergePreview(project.id, source.id, target.id)))
  }, [project.id, source.id, target.id, run])

  const blocked = !preview || preview.name_conflicts.length > 0
  return (
    <ConfirmDialog
      title={`Merge "${source.name}" into "${target.name}"?`}
      confirmLabel={busy ? 'Merging…' : 'Merge codes'}
      busy={busy || blocked}
      onCancel={onCancel}
      onConfirm={() => void run(async () => {
        await mergeCodes(project.id, source, target)
        onDone()
      })}
    >
      <ErrorMessage error={error} />
      {preview && (
        <>
          <p>
            {pluralize(preview.segments, 'segment')} from {pluralize(preview.coders, 'coder')} will move to "{target.name}", and "{source.name}" will disappear from the codebook.
          </p>
          {preview.duplicates > 0 && (
            <p>{pluralize(preview.duplicates, 'segment')} already {preview.duplicates === 1 ? 'has' : 'have'} the target code on the same text, so they will combine, keeping both memos.</p>
          )}
          {preview.name_conflicts.length > 0 && (
            <p className="message message-error">Both codes have a child named {preview.name_conflicts.join(', ')}. Rename or merge those first.</p>
          )}
          <p className="hint">Other coders' segments move too. This can't be undone from the app.</p>
        </>
      )}
    </ConfirmDialog>
  )
}

function CodeEditor({ project, code, codes, onChanged, onClose }: {
  project: Project
  code: Code
  codes: Code[]
  onChanged: () => void
  onClose: () => void
}) {
  const [name, setName] = useState(code.name)
  const [definition, setDefinition] = useState(code.definition)
  const [color, setColor] = useState(code.color)
  const [parent, setParent] = useState(code.parent_id ?? '')
  const [mergeTarget, setMergeTarget] = useState('')
  const [dialog, setDialog] = useState<'merge' | 'delete' | null>(null)
  const { busy, error, run } = useAction()
  const nodes = flattenCodeTree(codes)
  const paths = new Map(nodes.map((node) => [node.code.id, node.path]))
  const parents = allowedParents(codes, code.id)
  const target = codes.find((item) => item.id === mergeTarget)

  // Show the latest version after a save or a conflict. Staying mounted keeps any error message visible.
  useEffect(() => {
    setName(code.name)
    setDefinition(code.definition)
    setColor(code.color)
    setParent(code.parent_id ?? '')
  }, [code.revision, code.name, code.definition, code.color, code.parent_id])

  const failed = () => onChanged() // Reload, so the form shows what the other person saved.

  const save = (event: FormEvent) => {
    event.preventDefault()
    void run(async () => {
      await updateCode(project.id, code.id, { revision: code.revision, name, definition, color, parent_id: parent || null })
      onChanged()
    }).then((ok) => { if (!ok) failed() })
  }

  return (
    <div className="panel stack">
      <div className="page-title">
        <h2>Edit code</h2>
        <button type="button" className="button-quiet" onClick={onClose}>Close</button>
      </div>
      <ErrorMessage error={error} />
      <form className="stack" onSubmit={save}>
        <label className="field">Name<input required value={name} onChange={(event) => setName(event.target.value)} /></label>
        <label className="field">
          Definition
          <textarea rows={3} value={definition} onChange={(event) => setDefinition(event.target.value)} />
        </label>
        <label className="field">
          Inside
          <select value={parent} onChange={(event) => setParent(event.target.value)}>
            <option value="">Top level</option>
            {parents.map((item) => <option key={item.id} value={item.id}>{paths.get(item.id)}</option>)}
          </select>
        </label>
        <label className="field field-inline">Color<input type="color" value={color} onChange={(event) => setColor(event.target.value)} /></label>
        <div><button type="submit" disabled={busy}>Save changes</button></div>
      </form>

      <div className="stack section-divider">
        <label className="field">
          Merge into another code
          <select value={mergeTarget} onChange={(event) => setMergeTarget(event.target.value)}>
            <option value="">Choose a code</option>
            {nodes.filter((node) => node.code.id !== code.id).map((node) => <option key={node.code.id} value={node.code.id}>{node.path}</option>)}
          </select>
        </label>
        <div className="row">
          <button type="button" className="button-quiet" disabled={!target} onClick={() => setDialog('merge')}>Merge…</button>
          <button type="button" className="button-quiet button-danger-quiet" onClick={() => setDialog('delete')}>Delete…</button>
        </div>
      </div>

      {dialog === 'merge' && target && (
        <MergeDialog project={project} source={code} target={target} onCancel={() => { setDialog(null); onChanged() }} onDone={() => { setDialog(null); onClose(); onChanged() }} />
      )}
      {dialog === 'delete' && (
        <ConfirmDialog
          title={`Delete "${code.name}"?`}
          confirmLabel="Delete code"
          danger
          busy={busy}
          onCancel={() => setDialog(null)}
          onConfirm={() => {
            setDialog(null)
            void run(async () => {
              await deleteCode(project.id, code)
              onClose()
              onChanged()
            }).then((ok) => { if (!ok) failed() })
          }}
        >
          <p>Codes with segments or child codes can't be deleted. Merge them instead.</p>
        </ConfirmDialog>
      )}
    </div>
  )
}

export function CodebookTab({ project }: { project: Project }) {
  const codes = useApi((signal) => listCodes(project.id, signal), project.id)
  const [selected, setSelected] = useState<string | null>(null)
  const list = codes.data ?? []
  const nodes = flattenCodeTree(list)
  const selectedCode = list.find((code) => code.id === selected)

  return (
    <div className="codebook-layout">
      <section aria-label="Codes">
        <ErrorMessage error={codes.error} />
        {codes.loading && !codes.data && <p className="result-count">Loading codes…</p>}
        {codes.data && nodes.length === 0 && <p className="message">This codebook is empty. Add the first code.</p>}
        <ul className="code-tree">
          {nodes.map(({ code, depth }) => (
            <li key={code.id} style={{ paddingLeft: `${depth * 20}px` }} className={code.id === selected ? 'selected' : undefined}>
              <span className="swatch" style={{ background: code.color }} aria-hidden="true" />
              <div className="code-text">
                {project.can_edit_codebook && !project.archived ? (
                  <button type="button" className="link-button" aria-expanded={code.id === selected} onClick={() => setSelected(code.id === selected ? null : code.id)}>{code.name}</button>
                ) : <strong>{code.name}</strong>}
                {code.definition && <p className="code-definition">{code.definition}</p>}
              </div>
              <span className="count">{pluralize(code.segment_count, 'segment')}</span>
            </li>
          ))}
        </ul>
      </section>
      <aside className="stack">
        {selectedCode && (
          <CodeEditor
            key={selectedCode.id}
            project={project}
            code={selectedCode}
            codes={list}
            onChanged={codes.reload}
            onClose={() => setSelected(null)}
          />
        )}
        {project.role && !project.archived && <AddCodeForm project={project} codes={list} onAdded={codes.reload} />}
      </aside>
    </div>
  )
}
