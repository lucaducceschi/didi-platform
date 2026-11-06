import { type FormEvent, useState } from 'react'
import { ErrorMessage } from '../components/Message'
import { useAuth } from '../auth'
import { useAction } from '../useAction'

export function LoginPage() {
  const { login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const { busy, error, run } = useAction()

  const submit = (event: FormEvent) => {
    event.preventDefault()
    void run(() => login(username, password))
  }

  return (
    <form className="login-card" onSubmit={submit}>
      <h1>Log in to DIDI</h1>
      <ErrorMessage error={error} />
      <label className="field">
        Username
        <input autoComplete="username" autoFocus required value={username} onChange={(event) => setUsername(event.target.value)} />
      </label>
      <label className="field">
        Password
        <input type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} />
      </label>
      <button type="submit" disabled={busy}>{busy ? 'Logging in…' : 'Log in'}</button>
      <p className="hint">Accounts are created by an admin. Ask yours if you need one or forgot your password.</p>
    </form>
  )
}
