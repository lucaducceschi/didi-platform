import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from 'react'
import { ApiError, UNAUTHORIZED_EVENT, type User, getMe, login as apiLogin, logout as apiLogout } from './api'

interface AuthState {
  user: User | null
  checking: boolean
  error: string | null
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [checking, setChecking] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    getMe(controller.signal)
      .then(setUser)
      .catch((reason: Error) => {
        if (reason.name === 'AbortError') return
        if (!(reason instanceof ApiError && reason.status === 401)) setError(reason.message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setChecking(false)
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    const expire = () => setUser(null)
    window.addEventListener(UNAUTHORIZED_EVENT, expire)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, expire)
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    setUser(await apiLogin(username, password))
    setError(null)
  }, [])

  const logout = useCallback(async () => {
    await apiLogout()
    setUser(null)
  }, [])

  return <AuthContext.Provider value={{ user, checking, error, login, logout }}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
