import { type Project, listActivity } from '../../api'
import { describeActivity } from '../../activity'
import { ErrorMessage } from '../../components/Message'
import { useApi } from '../../useApi'

export function ActivityTab({ project }: { project: Project }) {
  const { data, error, loading } = useApi((signal) => listActivity(project.id, signal), project.id)
  return (
    <section aria-label="Project activity" className="stack">
      <ErrorMessage error={error} />
      {loading && !data && <p className="result-count">Loading activity…</p>}
      {data?.length === 0 && <p className="message">Nothing has happened in this project yet.</p>}
      <ol className="activity-list">
        {data?.map((entry) => (
          <li key={entry.id}>
            <time dateTime={entry.occurred_at}>{new Date(entry.occurred_at).toLocaleString()}</time>
            <span>{describeActivity(entry)}</span>
          </li>
        ))}
      </ol>
    </section>
  )
}
