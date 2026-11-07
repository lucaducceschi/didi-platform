import { Link, useNavigate } from 'react-router'
import { addArticles, getArticleProjects } from '../api'
import { useAction } from '../useAction'
import { useApi } from '../useApi'
import { ErrorMessage } from './Message'

/** Coding happens inside a project, so the read-only corpus page has to lead there. */
export function CodeInProject({ articleId }: { articleId: string }) {
  const navigate = useNavigate()
  const { data: projects, error } = useApi((signal) => getArticleProjects(articleId, signal), articleId)
  const { busy, error: addError, run } = useAction()

  if (error) return <ErrorMessage error={error} />
  if (!projects) return null

  const readerPath = (projectId: string) => `/projects/${projectId}/articles/${encodeURIComponent(articleId)}`
  const holding = projects.filter((project) => project.in_project)
  const addable = projects.filter((project) => !project.in_project && project.role === 'lead' && !project.archived)
  const add = (projectId: string) =>
    run(async () => {
      await addArticles(projectId, [articleId])
      navigate(readerPath(projectId))
    })

  if (holding.length === 0 && addable.length === 0) {
    return (
      <p className="message code-in-project">
        This page is read-only. Coding happens inside a project.{' '}
        {projects.some((project) => !project.archived)
          ? 'This article is not in your projects, so ask a project lead to add it.'
          : 'You are not in an active project yet, so ask a project lead to add you.'}
      </p>
    )
  }
  return (
    <section className="panel code-in-project" aria-label="Code this article">
      <p>This page is read-only. Coding happens inside a project.</p>
      <div className="code-in-project-actions">
        {holding.map((project) => (
          <Link key={project.id} className="button-link" to={readerPath(project.id)}>
            {project.archived ? `Open in ${project.name} (archived, read-only)` : `Open in ${project.name} to code`}
          </Link>
        ))}
        {addable.map((project) => (
          <button key={project.id} type="button" className="button-quiet" disabled={busy} onClick={() => add(project.id)}>
            Add to {project.name} and code
          </button>
        ))}
      </div>
      <ErrorMessage error={addError} />
    </section>
  )
}
