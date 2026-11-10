// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it } from 'vitest'
import { TopicTermChart } from './TopicTermChart'

afterEach(cleanup)

const terms = [
  { term: 'autonomie', relevance: -3, p_term_topic: 0.02, topic_count: 800, corpus_count: 1000 },
  { term: 'land', relevance: -4, p_term_topic: 0.01, topic_count: 100, corpus_count: 500 },
]

describe('TopicTermChart', () => {
  it('scales tracks to corpus counts and fills to the share in the topic', () => {
    const { container } = render(<MemoryRouter><TopicTermChart terms={terms} language="de" /></MemoryRouter>)
    const tracks = container.querySelectorAll<HTMLElement>('.term-track')
    const fills = container.querySelectorAll<HTMLElement>('.term-fill')
    expect([tracks[0].style.width, tracks[1].style.width]).toEqual(['100%', '50%'])
    expect([fills[0].style.width, fills[1].style.width]).toEqual(['80%', '20%'])
    expect(screen.getByText('80%')).toBeTruthy()
  })

  it('links each term to its concordance and reads out counts on focus', () => {
    render(<MemoryRouter><TopicTermChart terms={terms} language="it" /></MemoryRouter>)
    const link = screen.getByRole('link', { name: /^land:/ })
    expect(link.getAttribute('href')).toBe('/search?q=land&mode=word_family&language=it&view=kwic')
    fireEvent.focus(link)
    expect(screen.getByText(/occurrences in this topic ·/).textContent).toContain('100')
  })
})
