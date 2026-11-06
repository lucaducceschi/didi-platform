import { type FormEvent, useState } from 'react'
import { changePassword } from '../api'
import { useAuth } from '../auth'
import { ErrorMessage } from '../components/Message'
import { useAction } from '../useAction'

export function AccountPage() {
  const { user } = useAuth()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [saved, setSaved] = useState(false)
  const { busy, error, run } = useAction()

  const submit = (event: FormEvent) => {
    event.preventDefault()
    setSaved(false)
    void run(async () => {
      await changePassword(current, next)
      setCurrent('')
      setNext('')
      setSaved(true)
    })
  }

  return (
    <div className="narrow stack">
      <h1>Account</h1>
      <p>{user?.display_name} ({user?.username})</p>
      <form className="panel stack" onSubmit={submit}>
        <h2>Change your password</h2>
        <ErrorMessage error={error} />
        {saved && <p className="message" role="status">Your password was changed.</p>}
        <label className="field">
          Current password
          <input type="password" required autoComplete="current-password" value={current} onChange={(event) => setCurrent(event.target.value)} />
        </label>
        <label className="field">
          New password
          <input type="password" required minLength={10} autoComplete="new-password" value={next} onChange={(event) => setNext(event.target.value)} />
        </label>
        <p className="hint">At least 10 characters.</p>
        <div><button type="submit" disabled={busy}>Change password</button></div>
      </form>
    </div>
  )
}
