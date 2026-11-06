import { type FormEvent, useState } from 'react'
import { type User, createUser, listUsers, updateUser } from '../api'
import { useAuth } from '../auth'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { ErrorMessage } from '../components/Message'
import { useAction } from '../useAction'
import { useApi } from '../useApi'

function AddUserForm({ onAdded }: { onAdded: () => void }) {
  const [username, setUsername] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [isAdmin, setIsAdmin] = useState(false)
  const { busy, error, run } = useAction()

  const submit = (event: FormEvent) => {
    event.preventDefault()
    void run(async () => {
      await createUser({ username, display_name: displayName, password, is_admin: isAdmin })
      setUsername('')
      setDisplayName('')
      setPassword('')
      setIsAdmin(false)
      onAdded()
    })
  }

  return (
    <form className="panel stack" onSubmit={submit}>
      <h2>Add a user</h2>
      <ErrorMessage error={error} />
      <label className="field">Display name<input required value={displayName} onChange={(event) => setDisplayName(event.target.value)} /></label>
      <label className="field">Username<input required autoComplete="off" value={username} onChange={(event) => setUsername(event.target.value)} /></label>
      <label className="field">
        Temporary password
        <input type="password" required minLength={10} autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} />
      </label>
      <p className="hint">At least 10 characters. They can change it under Account.</p>
      <label className="checkbox"><input type="checkbox" checked={isAdmin} onChange={(event) => setIsAdmin(event.target.checked)} /> Admin</label>
      <div><button type="submit" disabled={busy}>Add user</button></div>
    </form>
  )
}

export function UsersPage() {
  const { user: me } = useAuth()
  const users = useApi((signal) => listUsers(signal), 'users')
  const [resetting, setResetting] = useState<User | null>(null)
  const [newPassword, setNewPassword] = useState('')
  const { busy, error, run } = useAction()

  const change = (user: User, body: { active?: boolean; is_admin?: boolean }) =>
    void run(async () => {
      await updateUser(user.id, body)
      users.reload()
    })

  return (
    <div className="stack">
      <h1>Users</h1>
      <div className="two-column">
        <section className="stack" aria-label="All users">
          <ErrorMessage error={error ?? users.error} />
          <div className="table-wrap">
            <table>
              <thead><tr><th>Name</th><th>Username</th><th>Admin</th><th>Status</th><th><span className="visually-hidden">Actions</span></th></tr></thead>
              <tbody>
                {users.data?.map((user) => (
                  <tr key={user.id}>
                    <td>{user.display_name}</td>
                    <td>{user.username}</td>
                    <td>
                      <input
                        type="checkbox"
                        aria-label={`${user.display_name} is an admin`}
                        checked={user.is_admin}
                        disabled={busy || user.id === me?.id}
                        onChange={(event) => change(user, { is_admin: event.target.checked })}
                      />
                    </td>
                    <td>{user.active ? 'Active' : 'Deactivated'}</td>
                    <td className="cell-action">
                      <div>
                        <button type="button" className="button-quiet" onClick={() => { setNewPassword(''); setResetting(user) }}>Reset password…</button>
                        {user.id !== me?.id && (
                          <button type="button" className="button-quiet" disabled={busy} onClick={() => change(user, { active: !user.active })}>
                            {user.active ? 'Deactivate' : 'Reactivate'}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <AddUserForm onAdded={users.reload} />
      </div>
      {resetting && (
        <ConfirmDialog
          title={`Reset the password of ${resetting.display_name}?`}
          confirmLabel="Reset password"
          busy={busy || newPassword.length < 10}
          onCancel={() => setResetting(null)}
          onConfirm={() => {
            const user = resetting
            setResetting(null)
            void run(async () => { await updateUser(user.id, { password: newPassword }) })
          }}
        >
          <label className="field">
            New temporary password
            <input type="password" autoFocus minLength={10} autoComplete="new-password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />
          </label>
          <p className="hint">At least 10 characters. They'll be logged out everywhere.</p>
        </ConfirmDialog>
      )}
    </div>
  )
}
