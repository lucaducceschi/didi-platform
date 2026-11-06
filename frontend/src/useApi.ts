import { useCallback, useEffect, useState } from 'react'

export interface ApiState<T> {
  data: T | null
  error: Error | null
  loading: boolean
  reload: () => void
}

/** Run a request whenever `key` changes, and cancel the previous one. */
export function useApi<T>(request: (signal: AbortSignal) => Promise<T>, key: string): ApiState<T> {
  const [state, setState] = useState<Omit<ApiState<T>, 'reload'>>({ data: null, error: null, loading: true })
  const [attempt, setAttempt] = useState(0)
  const reload = useCallback(() => setAttempt((current) => current + 1), [])

  useEffect(() => {
    const controller = new AbortController()
    setState((previous) => ({ ...previous, error: null, loading: true }))
    request(controller.signal)
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((error: Error) => {
        if (error.name !== 'AbortError') setState({ data: null, error, loading: false })
      })
    return () => controller.abort()
    // `key` identifies the request, so an unstable `request` closure must not trigger a refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, attempt])

  return { ...state, reload }
}
