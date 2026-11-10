// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { TopicShareChart } from './TopicShareChart'

afterEach(cleanup)

const series = [
  {
    source_type: 'journalism',
    points: [
      { period: '2021', share: 0.01, articles: 3, words: 900, small_sample: true },
      { period: '2022', share: 0.05, articles: 120, words: 40000, small_sample: false },
    ],
  },
  {
    source_type: 'official_press',
    points: [{ period: '2022', share: 0.07, articles: 900, words: 300000, small_sample: false }],
  },
]

describe('TopicShareChart', () => {
  it('labels each series and draws small samples hollow', () => {
    const { container } = render(<TopicShareChart series={series} smallSampleArticles={30} />)
    expect(screen.getByText('Journalism 5.0%')).toBeTruthy()
    expect(screen.getByText('Official press 7.0%')).toBeTruthy()
    const hollow = Array.from(container.querySelectorAll('circle')).filter((c) => c.getAttribute('fill') === 'var(--surface)')
    expect(hollow.length).toBe(2) // the small-sample point and its legend key
  })

  it('offers every value in a table', () => {
    render(<TopicShareChart series={series} smallSampleArticles={30} />)
    const rows = screen.getAllByRole('row')
    expect(rows).toHaveLength(3)
    expect(rows[1].textContent).toContain('1.0% (3, small)')
    expect(rows[1].textContent).toContain('–')
  })
})
