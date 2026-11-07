import { NavLink, Navigate, Route, Routes, useParams } from 'react-router'
import { ApiError, getProject } from '../api'
import { ErrorMessage } from '../components/Message'
import { useApi } from '../useApi'
import { ActivityTab } from './project/ActivityTab'
import { AddArticlesPage } from './project/AddArticlesPage'
import { LibraryTab } from './project/LibraryTab'
import { PassagesTab } from './project/PassagesTab'
import { ReaderPage } from './project/ReaderPage'
import { CodebookTab } from './project/CodebookTab'
import { MembersTab } from './project/MembersTab'
import { SettingsTab } from './project/SettingsTab'

export function ProjectPage() {
  const { projectId = '' } = useParams()
  const { data: project, error, loading, reload } = useApi((signal) => getProject(projectId, signal), projectId)

  if (error) return <ErrorMessage error={error instanceof ApiError && error.status === 404 ? "This project doesn't exist, or you aren't a member of it." : error} />
  if (!project) return loading ? <p className="result-count">Loading project…</p> : null

  const base = `/projects/${project.id}`

  return (
    <div className="stack">
      <div>
        <h1 className="project-name">{project.name}{project.archived && <span className="tag">Archived</span>}</h1>
        {project.description && <p className="project-description">{project.description}</p>}
      </div>
      <nav className="tabs" aria-label="Project sections">
        <NavLink to={`${base}/articles`} end={false}>Articles</NavLink>
        <NavLink to={`${base}/passages`}>Passages</NavLink>
        <NavLink to={`${base}/codebook`}>Codebook</NavLink>
        <NavLink to={`${base}/members`}>Members</NavLink>
        <NavLink to={`${base}/activity`}>Activity</NavLink>
        {project.can_manage && <NavLink to={`${base}/settings`}>Settings</NavLink>}
        <span className="tabs-end">
          <a href={`/api/projects/${project.id}/exports/annotations.csv`} download>Download segments</a>
          <a href={`/api/projects/${project.id}/exports/codes.csv`} download>Download codes</a>
        </span>
      </nav>
      <Routes>
        <Route index element={<Navigate to={`${base}/articles`} replace />} />
        <Route path="articles" element={<LibraryTab project={project} />} />
        <Route path="articles/add" element={project.can_manage && !project.archived ? <AddArticlesPage project={project} /> : <Navigate to={`${base}/articles`} replace />} />
        <Route path="articles/:articleId" element={<ReaderPage project={project} />} />
        <Route path="passages" element={<PassagesTab project={project} />} />
        <Route path="codebook" element={<CodebookTab project={project} />} />
        <Route path="members" element={<MembersTab project={project} onChanged={reload} />} />
        <Route path="activity" element={<ActivityTab project={project} />} />
        <Route path="settings" element={project.can_manage ? <SettingsTab key={project.revision} project={project} onChanged={reload} /> : <Navigate to={`${base}/codebook`} replace />} />
      </Routes>
    </div>
  )
}
