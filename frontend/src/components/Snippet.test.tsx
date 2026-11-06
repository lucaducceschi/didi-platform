// @vitest-environment jsdom
import { cleanup, render } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { Snippet } from './Snippet'

afterEach(cleanup)

describe('Snippet', () => {
  it('marks only the matching parts', () => {
    const { container } = render(<Snippet parts={[{ text: 'la ', match: false }, { text: 'scuola', match: true }, { text: ' bilingue', match: false }]} />)
    expect(container.textContent).toBe('la scuola bilingue')
    expect([...container.querySelectorAll('mark')].map((mark) => mark.textContent)).toEqual(['scuola'])
  })

  it('shows markup from articles as plain text', () => {
    const { container } = render(<Snippet parts={[{ text: "<script>alert('x')</script> <b>bold</b>", match: false }]} />)
    expect(container.querySelector('script')).toBeNull()
    expect(container.querySelector('b')).toBeNull()
    expect(container.textContent).toContain('<script>')
  })
})
