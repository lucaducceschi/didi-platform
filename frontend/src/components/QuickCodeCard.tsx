import { useEffect, useMemo, useRef, useState } from 'react'
import { type Code, type Project, createAnnotation } from '../api'
import { flattenCodeTree } from '../codebook'
import { useAction } from '../useAction'

interface QuickCodeCardProps {
  project: Project
  articleId: string
  selection: { start: number; end: number }
  codes: Code[]
  quickCodes: Code[]
  coords: { top: number; left: number; placeAbove?: boolean }
  onSaved: (message: string | null) => void
  onCancel: () => void
}

export function QuickCodeCard({
  project,
  articleId,
  selection,
  codes,
  quickCodes,
  coords,
  onSaved,
  onCancel,
}: QuickCodeCardProps) {
  const [filter, setFilter] = useState('')
  const [memo, setMemo] = useState('')
  const [showMemo, setShowMemo] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const { busy, run } = useAction()
  const inputRef = useRef<HTMLInputElement>(null)
  const cardRef = useRef<HTMLDivElement>(null)

  const nodes = useMemo(() => flattenCodeTree(codes), [codes])

  // Filtered code list
  const visible = useMemo(() => {
    const term = filter.trim().toLowerCase()
    if (!term) return nodes
    return nodes.filter(
      (node) =>
        node.path.toLowerCase().includes(term) ||
        node.code.definition?.toLowerCase().includes(term)
    )
  }, [filter, nodes])

  // Reset active index when filter changes
  useEffect(() => {
    setActiveIndex(0)
  }, [filter])

  // Auto-focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  // Close when clicking outside
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (cardRef.current && !cardRef.current.contains(e.target as Node)) {
        onCancel()
      }
    }
    document.addEventListener('mousedown', handleOutsideClick)
    return () => document.removeEventListener('mousedown', handleOutsideClick)
  }, [onCancel])

  const handleSave = (codeId: string) => {
    if (busy) return
    void run(async () => {
      const saved = await createAnnotation(project.id, articleId, {
        start: selection.start,
        end: selection.end,
        code_id: codeId,
        memo: memo.trim(),
      })
      const current = codes.find((c) => c.id === saved.code_id)
      let message: string | null = null
      if (saved.merged_from) {
        message = `"${saved.merged_from}" was merged, so saved under "${current?.name ?? 'the new code'}".`
      } else if (saved.created === false) {
        message = 'You already coded this passage with this code.'
      }
      onSaved(message)
    })
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.preventDefault()
      onCancel()
      return
    }

    // Number hotkeys (1-9) when search is empty and not typing in memo
    if (!filter && !showMemo && /^[1-9]$/.test(e.key)) {
      const num = parseInt(e.key, 10)
      if (num <= quickCodes.length) {
        e.preventDefault()
        handleSave(quickCodes[num - 1].id)
        return
      }
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex((prev) => (prev + 1) % Math.max(1, visible.length))
      return
    }

    if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((prev) => (prev - 1 + visible.length) % Math.max(1, visible.length))
      return
    }

    if (e.key === 'Enter') {
      e.preventDefault()
      if (visible.length > 0 && activeIndex < visible.length) {
        handleSave(visible[activeIndex].code.id)
      }
    }
  }

  return (
    <div
      ref={cardRef}
      className="quick-code-card"
      style={{
        position: 'absolute',
        top: coords.top,
        left: coords.left,
        zIndex: 100,
        width: '320px',
        backgroundColor: 'var(--canvas, #ffffff)',
        color: 'var(--text, #1f2328)',
        borderRadius: '8px',
        border: '1px solid var(--border, #d0d7de)',
        boxShadow: '0 8px 24px rgba(0, 0, 0, 0.18), 0 2px 6px rgba(0, 0, 0, 0.08)',
        padding: '10px 12px',
        fontSize: '12px',
        animation: 'quick-code-in 120ms ease-out',
      }}
      onKeyDown={handleKeyDown}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '8px',
          fontWeight: 600,
          color: 'var(--muted, #656d76)',
          fontSize: '11px',
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
        }}
      >
        <span>⚡ Quick Code</span>
        <button
          type="button"
          onClick={onCancel}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: '2px 4px',
            fontSize: '11px',
            color: 'var(--muted, #656d76)',
          }}
          title="Cancel (Esc)"
        >
          esc ✕
        </button>
      </div>

      {/* Top / Recent Quick Codes */}
      {!filter && quickCodes.length > 0 && (
        <div style={{ marginBottom: '8px' }}>
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '6px',
            }}
          >
            {quickCodes.map((code, idx) => (
              <button
                key={code.id}
                type="button"
                disabled={busy}
                onClick={() => handleSave(code.id)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '4px 8px',
                  borderRadius: '14px',
                  border: '1px solid var(--border, #d0d7de)',
                  backgroundColor: 'var(--canvas-subtle, #f6f8fa)',
                  cursor: 'pointer',
                  fontSize: '11px',
                  fontWeight: 500,
                  color: 'var(--text, #1f2328)',
                  transition: 'background-color 0.1s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--canvas-inset, #eaeef2)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--canvas-subtle, #f6f8fa)'
                }}
                title={`Press ${idx + 1} to apply`}
              >
                <span
                  style={{
                    display: 'inline-block',
                    width: '14px',
                    height: '14px',
                    lineHeight: '14px',
                    textAlign: 'center',
                    fontSize: '9px',
                    fontWeight: 700,
                    borderRadius: '50%',
                    backgroundColor: 'rgba(0,0,0,0.08)',
                    color: 'var(--muted, #555)',
                  }}
                >
                  {idx + 1}
                </span>
                <span
                  style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '2px',
                    backgroundColor: code.color,
                    flexShrink: 0,
                  }}
                />
                <span style={{ maxWidth: '100px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {code.name}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Search Input */}
      <div style={{ position: 'relative', marginBottom: '6px' }}>
        <input
          ref={inputRef}
          type="search"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder={quickCodes.length > 0 ? "Or search other code (Enter to save)..." : "Search code (Enter to save)..."}
          style={{
            width: '100%',
            boxSizing: 'border-box',
            padding: '5px 8px',
            fontSize: '12px',
            borderRadius: '4px',
            border: '1px solid var(--border, #d0d7de)',
            backgroundColor: 'var(--canvas, #fff)',
            color: 'var(--text, #1f2328)',
            outline: 'none',
          }}
        />
      </div>

      {/* Filtered Code Dropdown */}
      <div
        style={{
          maxHeight: '140px',
          overflowY: 'auto',
          border: '1px solid var(--border, #e1e4e8)',
          borderRadius: '4px',
          marginBottom: '6px',
        }}
      >
        {visible.length === 0 ? (
          <div style={{ padding: '8px', color: 'var(--muted, #656d76)', textAlign: 'center' }}>
            No matching codes
          </div>
        ) : (
          visible.map(({ code, path }, idx) => {
            const isSelected = idx === activeIndex
            return (
              <div
                key={code.id}
                onClick={() => handleSave(code.id)}
                onMouseEnter={() => setActiveIndex(idx)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '5px 8px',
                  cursor: 'pointer',
                  backgroundColor: isSelected
                    ? 'var(--canvas-inset, #eaeef2)'
                    : 'transparent',
                  borderBottom: idx < visible.length - 1 ? '1px solid var(--border-subtle, #f0f2f5)' : 'none',
                }}
              >
                <span
                  style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '2px',
                    backgroundColor: code.color,
                    flexShrink: 0,
                  }}
                />
                <span
                  style={{
                    flex: 1,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    fontWeight: isSelected ? 600 : 400,
                  }}
                >
                  {path}
                </span>
                {isSelected && (
                  <span style={{ fontSize: '10px', color: 'var(--muted, #666)' }}>↵ enter</span>
                )}
              </div>
            )
          })
        )}
      </div>

      {/* Optional Quick Memo */}
      <div>
        {!showMemo ? (
          <button
            type="button"
            onClick={() => setShowMemo(true)}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--accent, #0969da)',
              fontSize: '11px',
              padding: '0',
            }}
          >
            + Add memo
          </button>
        ) : (
          <textarea
            rows={2}
            value={memo}
            onChange={(e) => setMemo(e.target.value)}
            placeholder="Write a brief memo..."
            style={{
              width: '100%',
              boxSizing: 'border-box',
              padding: '4px 6px',
              fontSize: '11px',
              borderRadius: '4px',
              border: '1px solid var(--border, #d0d7de)',
              marginTop: '4px',
              resize: 'vertical',
            }}
          />
        )}
      </div>
    </div>
  )
}

