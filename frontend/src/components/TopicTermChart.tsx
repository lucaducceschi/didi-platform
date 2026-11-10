import { useState } from 'react'
import { Link } from 'react-router'
import type { TopicTermItem } from '../api'

interface TopicTermChartProps {
  terms: TopicTermItem[]
  language: string
}

const fmt = (n: number) => Math.round(n).toLocaleString()

/**
 * LDAvis-style term list (Sievert & Shirley 2014): each row's track is the term's corpus count,
 * the fill its estimated count in this topic, on one shared scale. The figure is the share of
 * the term's occurrences that falls in this topic. Each term opens its concordance.
 */
export function TopicTermChart({ terms, language }: TopicTermChartProps) {
  const [hover, setHover] = useState<number | null>(null)
  const max = Math.max(1, ...terms.map((t) => t.corpus_count))
  const active = hover === null ? null : terms[hover]

  return (
    <div className="term-chart">
      <p className="term-legend hint">
        <span className="term-key term-key-topic" aria-hidden="true" /> in this topic
        <span className="term-key term-key-corpus" aria-hidden="true" /> whole corpus
        <span className="term-legend-figure">share in topic</span>
      </p>
      <ol className="term-rows" onPointerLeave={() => setHover(null)}>
        {terms.map((t, i) => {
          const share = t.corpus_count ? t.topic_count / t.corpus_count : 0
          const label = `${t.term}: about ${fmt(t.topic_count)} of ${fmt(t.corpus_count)} occurrences in this topic (${Math.round(share * 100)}%)`
          return (
            <li key={t.term} onPointerEnter={() => setHover(i)}>
              <Link
                className="term-row"
                to={`/search?q=${encodeURIComponent(t.term)}&mode=word_family&language=${language}&view=kwic`}
                aria-label={`${label}. Open concordance`}
                onFocus={() => setHover(i)}
                onBlur={() => setHover(null)}
              >
                <span className="term-name">{t.term}</span>
                <span className="term-bar" aria-hidden="true">
                  <span className="term-track" style={{ width: `${(t.corpus_count / max) * 100}%` }}>
                    <span className="term-fill" style={{ width: `${share * 100}%` }} />
                  </span>
                </span>
                <span className="term-figure">{Math.round(share * 100)}%</span>
              </Link>
            </li>
          )
        })}
      </ol>
      <p className="hint term-readout" aria-live="polite">
        {active ? (
          <>
            <strong>{active.term}</strong>: about <strong>{fmt(active.topic_count)}</strong> of{' '}
            {fmt(active.corpus_count)} occurrences in this topic · p(term | topic){' '}
            {(active.p_term_topic * 100).toFixed(2)}%
          </>
        ) : (
          'Point at a term for its counts; select it to open the concordance.'
        )}
      </p>
    </div>
  )
}
