// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router'
import type { WordBubbleItem } from '../api'
import { WordBubbleChart } from './charts/WordBubbleChart'
import { LexicalDossierModal } from './LexicalDossierModal'

afterEach(cleanup)

const mockItems: WordBubbleItem[] = [
  {
    id: 'autonomie',
    term: 'Autonomie',
    twin_term: 'Autonomia',
    category: 'Autonomy & Rights',
    category_color: '#2b6cb0',
    count: 12500,
    salience: 0.95,
    de_ratio: 0.85,
    it_ratio: 0.15,
    journalism_ratio: 0.70,
    official_press_ratio: 0.30,
    primary_moral: 'Authority',
    sentiment: 0.12,
    collocates: ['Statut', 'Zuständigkeiten', 'Rom'],
    sample_snippet: 'Die Weiterentwicklung des Autonomiestatuts.',
    years: ['2016', '2017', '2018', '2019', '2020', '2021', '2022', '2023', '2024', '2025'],
    yearly_trend: [1000, 1100, 1200, 1300, 1400, 1500, 1400, 1300, 1200, 1100],
  },
  {
    id: 'wolf',
    term: 'Wolf',
    twin_term: 'Lupo',
    category: 'Environment',
    category_color: '#38a169',
    count: 3200,
    salience: 0.55,
    de_ratio: 0.92,
    it_ratio: 0.08,
    journalism_ratio: 0.90,
    official_press_ratio: 0.10,
    primary_moral: 'Harm / Care',
    sentiment: -0.28,
    collocates: ['Almen', 'Abschuss'],
    sample_snippet: 'Zunahme von Wolfsrissen auf den Almen.',
    years: ['2016', '2017', '2018', '2019', '2020', '2021', '2022', '2023', '2024', '2025'],
    yearly_trend: [50, 120, 200, 310, 450, 600, 520, 480, 390, 350],
  },
]

describe('WordBubbleChart', () => {
  it('renders packed SVG bubbles for terms', () => {
    const handleSelect = vi.fn()
    const { container } = render(
      <WordBubbleChart data={mockItems} onSelectWord={handleSelect} />
    )

    expect(screen.getByText('Autonomie')).toBeDefined()
    expect(screen.getByText('Wolf')).toBeDefined()
    expect(container.querySelectorAll('circle').length).toBeGreaterThan(2)
  })

  it('triggers onSelectWord callback when bubble is clicked', () => {
    const handleSelect = vi.fn()
    render(<WordBubbleChart data={mockItems} onSelectWord={handleSelect} />)

    const bubbleGroup = screen.getByRole('button', { name: /Autonomie/i })
    fireEvent.click(bubbleGroup)
    expect(handleSelect).toHaveBeenCalledWith(mockItems[0])
  })
})

describe('LexicalDossierModal', () => {
  beforeEach(() => {
    // Mock HTMLDialogElement methods for JSDOM
    HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
      this.open = true
    }
    HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
      this.open = false
    }
  })

  it('renders lexical dossier details including ratios, collocates and snippet', () => {
    const handleClose = vi.fn()
    render(
      <MemoryRouter>
        <LexicalDossierModal item={mockItems[0]} onClose={handleClose} />
      </MemoryRouter>
    )

    expect(screen.getByText('Autonomie')).toBeDefined()
    expect(screen.getByText('/ Autonomia')).toBeDefined()
    expect(screen.getByText('Autonomy & Rights')).toBeDefined()
    expect(screen.getByText(/Authority/)).toBeDefined()
    expect(screen.getByText(/Statut/)).toBeDefined()
    expect(screen.getByText(/Die Weiterentwicklung des Autonomiestatuts/)).toBeDefined()
  })

  it('calls onClose when close button is clicked', () => {
    const handleClose = vi.fn()
    render(
      <MemoryRouter>
        <LexicalDossierModal item={mockItems[0]} onClose={handleClose} />
      </MemoryRouter>
    )

    const closeBtn = screen.getByRole('button', { name: 'Close' })
    fireEvent.click(closeBtn)
    expect(handleClose).toHaveBeenCalled()
  })
})
