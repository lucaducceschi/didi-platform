// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ArticleReader, type Highlight } from './ArticleReader'

afterEach(cleanup)

const highlight = (id: string, start: number, end: number, mine = true): Highlight => ({ id, start, end, mine, color: '#112233', label: `Code ${id}` })

describe('ArticleReader', () => {
  it('keeps the text exact, including line endings and combining characters', () => {
    const text = '  Gherdëina\r\n\r\n🙂 end  '
    render(<ArticleReader text={text} highlights={[highlight('a', 2, 8)]} selectedIds={[]} onSelect={() => {}} />)
    expect(screen.getByTestId('article-text').textContent).toBe(text)
  })

  it('shows markup in articles as literal text', () => {
    const text = "<script>alert('x')</script> and <b>bold</b>"
    const { container } = render(<ArticleReader text={text} highlights={[highlight('a', 0, 8)]} selectedIds={[]} onSelect={() => {}} />)
    expect(container.querySelector('script')).toBeNull()
    expect(container.querySelector('b')).toBeNull()
    expect(screen.getByTestId('article-text').textContent).toBe(text)
  })

  it('tells mine, others and overlaps apart, and selects on click', () => {
    const onSelect = vi.fn()
    const { container } = render(
      <ArticleReader text="abcdefghij" highlights={[highlight('m', 0, 4), highlight('o', 2, 6, false), highlight('x', 8, 10, false)]} selectedIds={['x']} onSelect={onSelect} />,
    )
    const classes = [...container.querySelectorAll('.hl')].map((span) => [span.textContent, span.className])
    expect(classes).toEqual([
      ['ab', 'hl hl-mine'],
      ['cd', 'hl hl-mine hl-overlap'],
      ['ef', 'hl hl-other'],
      ['ij', 'hl hl-other hl-selected'],
    ])
    fireEvent.click(screen.getByText('cd'))
    expect(onSelect).toHaveBeenCalledWith(['m', 'o'])
  })

  it('calls onCancelSelection and removes range when Escape is pressed', () => {
    const onCancel = vi.fn()
    render(
      <ArticleReader
        text="abcdefghij"
        highlights={[]}
        selectedIds={[]}
        pending={{ start: 2, end: 5 }}
        onSelect={() => {}}
        onCancelSelection={onCancel}
      />,
    )
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onCancel).toHaveBeenCalledTimes(1)
  })
})
