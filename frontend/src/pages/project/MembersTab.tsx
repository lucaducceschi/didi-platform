import { type FormEvent, useState } from 'react'
import { type Member, type Project, addMember, getUserDirectory, listMembers, removeMember, updateMember } from '../../api'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { ErrorMessage } from '../../components/Message'
import { useAction } from '../../useAction'
import { useApi } from '../../useApi'

function AddMemberForm({ project, members, onAdded }: { project: Project; members: Member[]; onAdded: () => void }) {
  const directory = useApi((signal) => getUserDirectory(signal), 'directory')
  const [userId, setUserId] = useState('')
  const [role, setRole] = useState<Member['role']>('coder')
  const { busy, error, run } = useAction()
  const existing = new Set(members.map((member) => member.user.id))
  const available = directory.data?.filter((person) => !existing.has(person.id)) ?? []

  const submit = (event: FormEvent) => {
    event.preventDefault()
    void run(async () => {
      await addMember(project.id, userId, role)
      setUserId('')
      onAdded()
    })
  }

  return (
    <form className="panel stack" onSubmit={submit}>
      <h2>Add a member</h2>
      <ErrorMessage error={error ?? directory.error} />
      <label className="field">
        Person
        <select required value={userId} onChange={(event) => setUserId(event.target.value)}>
          <option value="">{!directory.data ? 'Loading people…' : available.length ? 'Choose a person' : 'Everyone is already a member'}</option>
          {available.map((person) => <option key={person.id} value={person.id}>{person.display_name} ({person.username})</option>)}
        </select>
      </label>
      <label className="field">
        Role
        <select value={role} onChange={(event) => setRole(event.target.value as Member['role'])}>
          <option value="coder">Coder</option>
          <option value="lead">Lead</option>
        </select>
      </label>
      <div><button type="submit" disabled={busy || !userId}>Add member</button></div>
    </form>
  )
}

export function MembersTab({ project, onChanged }: { project: Project; onChanged: () => void }) {
  const members = useApi((signal) => listMembers(project.id, signal), project.id)
  const [removing, setRemoving] = useState<Member | null>(null)
  const { busy, error, run } = useAction()
  const editable = project.can_manage && !project.archived

  const refresh = () => {
    members.reload()
    onChanged()
  }

  return (
    <div className="two-column">
      <section className="stack" aria-label="Members">
        <ErrorMessage error={error ?? members.error} />
        <div className="table-wrap">
          <table>
            <thead><tr><th>Name</th><th>Username</th><th>Role</th>{editable && <th><span className="visually-hidden">Actions</span></th>}</tr></thead>
            <tbody>
              {members.data?.map((member) => (
                <tr key={member.user.id}>
                  <td>{member.user.display_name}{!member.active && <span className="tag">Deactivated</span>}</td>
                  <td>{member.user.username}</td>
                  <td>
                    {editable ? (
                      <select
                        aria-label={`Role of ${member.user.display_name}`}
                        value={member.role}
                        disabled={busy}
                        onChange={(event) => void run(async () => {
                          await updateMember(project.id, member.user.id, event.target.value as Member['role'])
                          refresh()
                        })}
                      >
                        <option value="coder">Coder</option>
                        <option value="lead">Lead</option>
                      </select>
                    ) : member.role === 'lead' ? 'Lead' : 'Coder'}
                  </td>
                  {editable && (
                    <td className="cell-action">
                      <div>
                        <button type="button" className="button-quiet" onClick={() => setRemoving(member)}>Remove…</button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      {editable && members.data && <AddMemberForm project={project} members={members.data} onAdded={refresh} />}
      {removing && (
        <ConfirmDialog
          title={`Remove ${removing.user.display_name} from this project?`}
          confirmLabel="Remove member"
          danger
          busy={busy}
          onCancel={() => setRemoving(null)}
          onConfirm={() => {
            const member = removing
            setRemoving(null)
            void run(async () => {
              await removeMember(project.id, member.user.id)
              refresh()
            })
          }}
        >
          <p>Their segments stay in the project. They just won't be able to open it any more.</p>
        </ConfirmDialog>
      )}
    </div>
  )
}
