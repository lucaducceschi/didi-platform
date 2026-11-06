import { type ReactNode, useEffect, useRef } from 'react'

export function ConfirmDialog({ title, children, confirmLabel, danger, busy, onConfirm, onCancel }: {
  title: string
  children: ReactNode
  confirmLabel: string
  danger?: boolean
  busy?: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  const dialog = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const element = dialog.current
    if (element && !element.open) element.showModal()
    return () => element?.close()
  }, [])

  return (
    <dialog ref={dialog} className="dialog" aria-labelledby="dialog-title" onCancel={(event) => { event.preventDefault(); onCancel() }}>
      <h2 id="dialog-title">{title}</h2>
      <div>{children}</div>
      <div className="dialog-actions">
        <button type="button" className="button-quiet" onClick={onCancel}>Cancel</button>
        <button type="button" className={danger ? 'button-danger' : undefined} disabled={busy} onClick={onConfirm}>{confirmLabel}</button>
      </div>
    </dialog>
  )
}
