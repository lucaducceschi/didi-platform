export function ErrorMessage({ error }: { error: string | Error | null | undefined }) {
  if (!error) return null
  return <p className="message message-error" role="alert">{typeof error === 'string' ? error : error.message}</p>
}
