import { type FormEvent, useState } from 'react'
import { type Project, updateProject } from '../../api'
import { ErrorMessage } from '../../components/Message'
import { useAction } from '../../useAction'

export function SettingsTab({ project, onChanged }: { project: Project; onChanged: () => void }) {
  const [name, setName] = useState(project.name)
  const [description, setDescription] = useState(project.description)
  const { busy, error, run } = useAction()

  const change = (body: { name?: string; description?: string; archived?: boolean }) =>
    void run(async () => {
      await updateProject(project.id, { revision: project.revision, ...body })
    }).then(onChanged)

  const submit = (event: FormEvent) => {
    event.preventDefault()
    change({ name, description })
  }

  return (
    <div className="narrow stack">
      <ErrorMessage error={error} />
      {!project.archived && (
        <form className="panel stack" onSubmit={submit}>
          <label className="field">Name<input required value={name} onChange={(event) => setName(event.target.value)} /></label>
          <label className="field">
            Research question or description
            <textarea rows={3} value={description} onChange={(event) => setDescription(event.target.value)} />
          </label>
          <div><button type="submit" disabled={busy}>Save changes</button></div>
        </form>
      )}
      <div className="panel stack">
        <h2>{project.archived ? 'This project is archived' : 'Archive this project'}</h2>
        <p>Archived projects stay readable and exportable, but nobody can change them.</p>
        <div>
          <button type="button" className="button-quiet" disabled={busy} onClick={() => change({ archived: !project.archived })}>
            {project.archived ? 'Restore project' : 'Archive project'}
          </button>
        </div>
      </div>
    </div>
  )
}
