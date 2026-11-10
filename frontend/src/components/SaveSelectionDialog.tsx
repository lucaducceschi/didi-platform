import { type FormEvent, useState } from 'react'
import {
  type Project,
  type SavedSelection,
  type SearchFilters,
  createSelection,
} from '../api'
import { ErrorMessage } from './Message'
import { useAction } from '../useAction'

interface SaveSelectionDialogProps {
  filters: SearchFilters
  totalCount: number
  selectedIds: string[]
  projects: Project[]
  defaultProjectId?: string
  onCancel: () => void
  onSuccess: (selection: SavedSelection, projectName: string) => void
}

export function SaveSelectionDialog({
  filters,
  totalCount,
  selectedIds,
  projects,
  defaultProjectId,
  onCancel,
  onSuccess,
}: SaveSelectionDialogProps) {
  const [projectId, setProjectId] = useState(defaultProjectId || projects[0]?.id || '')
  const [name, setName] = useState(
    filters.q ? `Selection: ${filters.q.trim()}` : `Corpus Subset (${new Date().toLocaleDateString()})`,
  )
  const [description, setDescription] = useState('')
  const [saveMode, setSaveMode] = useState<'query' | 'selected'>(
    selectedIds.length > 0 ? 'selected' : 'query',
  )
  const { busy, error, run } = useAction()

  const selectedProject = projects.find((p) => p.id === projectId)

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!projectId || !name.trim()) return

    void run(async () => {
      const payload = {
        name: name.trim(),
        description: description.trim(),
        query_definition:
          saveMode === 'query'
            ? {
                q: filters.q,
                mode: filters.mode ?? 'concept',
                sources: filters.sources,
                languages: filters.languages,
                types: filters.types,
                min_date: filters.min_date,
                max_date: filters.max_date,
              }
            : {},
        article_ids: saveMode === 'selected' ? selectedIds : undefined,
      }

      const created = await createSelection(projectId, payload)
      onSuccess(created, selectedProject?.name ?? 'project')
    })
  }

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0,0,0,0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: '16px',
      }}
    >
      <div
        style={{
          background: 'var(--surface, #fff)',
          border: '1px solid var(--border)',
          borderRadius: '8px',
          maxWidth: '520px',
          width: '100%',
          padding: '24px',
          boxShadow: '0 10px 25px rgba(0,0,0,0.2)',
        }}
      >
        <h2 style={{ margin: '0 0 12px', fontSize: '18px' }}>Save as Corpus Selection</h2>
        <p style={{ margin: '0 0 16px', fontSize: '13px', color: 'var(--muted)' }}>
          Save this document selection as a first-class, reproducible subcorpus object in your project.
        </p>

        {error && <ErrorMessage error={error} />}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <label className="field">
            <span>Project</span>
            <select
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              disabled={busy}
              required
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Selection Name</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Autonomy Reforms 2021-2025"
              disabled={busy}
              required
            />
          </label>

          <label className="field">
            <span>Description (optional)</span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Rationale, hypothesis, or sampling criteria..."
              rows={2}
              disabled={busy}
            />
          </label>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600 }}>Selection Basis</span>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', cursor: 'pointer' }}>
              <input
                type="radio"
                name="saveMode"
                checked={saveMode === 'query'}
                onChange={() => setSaveMode('query')}
                disabled={busy}
              />
              <span>
                <strong>Dynamic Search Criteria</strong> ({totalCount.toLocaleString()} matching articles)
              </span>
            </label>
            <span style={{ fontSize: '11px', color: 'var(--muted)', marginLeft: '24px' }}>
              Preserves query parameters and materializes the current matching snapshot. Can be refreshed later.
            </span>

            {selectedIds.length > 0 && (
              <>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', cursor: 'pointer', marginTop: '6px' }}>
                  <input
                    type="radio"
                    name="saveMode"
                    checked={saveMode === 'selected'}
                    onChange={() => setSaveMode('selected')}
                    disabled={busy}
                  />
                  <span>
                    <strong>Selected Articles Only</strong> ({selectedIds.length.toLocaleString()} checked)
                  </span>
                </label>
                <span style={{ fontSize: '11px', color: 'var(--muted)', marginLeft: '24px' }}>
                  Creates a frozen manual selection containing only the explicitly checked articles.
                </span>
              </>
            )}
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
            <button type="button" className="button-quiet" onClick={onCancel} disabled={busy}>
              Cancel
            </button>
            <button type="submit" className="button" disabled={busy || !name.trim() || !projectId}>
              {busy ? 'Saving…' : 'Save Selection'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

