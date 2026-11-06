import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { type Project, createProject, getUserDirectory, listProjects } from '../api'
import { useAuth } from '../auth'
import { ErrorMessage } from '../components/Message'
import { useAction } from '../useAction'
import { useApi } from '../useApi'

type Mode = 'empty' | 'starter' | 'copy'

function NewProjectForm({ projects, onCancel }: { projects: Project[]; onCancel: () => void }) {
  const navigate = useNavigate()
  const directory = useApi((signal) => getUserDirectory(signal), 'directory')
  const { user } = useAuth()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [lead, setLead] = useState(user?.id ?? '')
  const [mode, setMode] = useState<Mode>('starter')
  const [source, setSource] = useState('')
  const { busy, error, run } = useAction()

  const submit = (event: FormEvent) => {
    event.preventDefault()
    void run(async () => {
      const project = await createProject({
        name,
        description,
        lead_user_id: lead,
        codebook: { mode, source_project_id: mode === 'copy' ? source : undefined },
      })
      navigate(`/projects/${project.id}`)
    })
  }

  return (
    <form className="panel stack" onSubmit={submit}>
      <h2>New project</h2>
      <ErrorMessage error={error} />
      <label className="field">Name<input required autoFocus value={name} onChange={(event) => setName(event.target.value)} /></label>
      <label className="field">
        Research question or description
        <textarea rows={2} value={description} onChange={(event) => setDescription(event.target.value)} />
      </label>
      <label className="field">
        Project lead
        <select value={lead} onChange={(event) => setLead(event.target.value)}>
          {directory.data?.map((person) => <option key={person.id} value={person.id}>{person.display_name}</option>)}
        </select>
      </label>
      <fieldset className="choice-group">
        <legend>Start the codebook</legend>
        <label><input type="radio" name="mode" checked={mode === 'starter'} onChange={() => setMode('starter')} /> With the starter codes</label>
        <label><input type="radio" name="mode" checked={mode === 'empty'} onChange={() => setMode('empty')} /> Empty</label>
        <label>
          <input type="radio" name="mode" disabled={projects.length === 0} checked={mode === 'copy'} onChange={() => setMode('copy')} /> Copied from another project
        </label>
      </fieldset>
      {mode === 'copy' && (
        <label className="field">
          Copy from
          <select required value={source} onChange={(event) => setSource(event.target.value)}>
            <option value="">Choose a project</option>
            {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
          </select>
        </label>
      )}
      <div className="row">
        <button type="submit" disabled={busy}>{busy ? 'Creating…' : 'Create project'}</button>
        <button type="button" className="button-quiet" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  )
}

const plural = (count: number, one: string) => `${count.toLocaleString()} ${one}${count === 1 ? '' : 's'}`

export function ProjectsPage() {
  const { user } = useAuth()
  const { data, error, loading } = useApi((signal) => listProjects(signal), 'projects')
  const [creating, setCreating] = useState(false)

  return (
    <div className="stack">
      <div className="page-title">
        <h1>Projects</h1>
        {user?.is_admin && !creating && <button type="button" onClick={() => setCreating(true)}>New project</button>}
      </div>
      {creating && <NewProjectForm projects={data ?? []} onCancel={() => setCreating(false)} />}
      <ErrorMessage error={error} />
      {loading && !data && <p className="result-count">Loading projects…</p>}
      {data?.length === 0 && (
        <p className="message">
          {user?.is_admin ? 'There are no projects yet. Create the first one.' : "You aren't in a project yet. Ask a project lead or an admin to add you."}
        </p>
      )}
      <ul className="project-list">
        {data?.map((project) => (
          <li key={project.id} className="panel">
            <h2><Link to={`/projects/${project.id}`}>{project.name}</Link></h2>
            {project.description && <p>{project.description}</p>}
            <p className="result-meta">
              {project.role ? `Your role: ${project.role}` : 'Not a member (admin view)'}
              {project.archived && ' · Archived'}
              {` · ${plural(project.member_count, 'member')} · ${plural(project.code_count, 'code')} · ${plural(project.article_count, 'article')} · ${plural(project.segment_count, 'segment')}`}
            </p>
          </li>
        ))}
      </ul>
    </div>
  )
}
