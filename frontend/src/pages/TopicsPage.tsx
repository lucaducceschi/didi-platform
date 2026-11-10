import { useRef, useState } from 'react'
import { Link } from 'react-router'
import { type TopicModel, getTopicArticles, getTopicTerms, getTopicTimeline, listProjects, listTopicModels } from '../api'
import { ErrorMessage } from '../components/Message'
import { SaveSelectionDialog } from '../components/SaveSelectionDialog'
import { TopicShareChart } from '../components/TopicShareChart'
import { TopicTermChart } from '../components/TopicTermChart'
import { useApi } from '../useApi'

const SOURCE_TYPES = [
  { value: '', label: 'All' },
  { value: 'journalism', label: 'Journalism' },
  { value: 'official_press', label: 'Official press' },
]
const WEIGHTS = [0.2, 0.3, 0.5]
const DEFAULT_LAMBDA = 0.6

const pct = (x: number) => `${(x * 100).toFixed(1)}%`
const relevantTerms = (model: TopicModel, topicId: number, n: number) =>
  model.topics[topicId].relevant_terms.slice(0, n).join(', ')

export function TopicsPage() {
  const models = useApi((signal) => listTopicModels(signal), 'topic-models')
  const projects = useApi((signal) => listProjects(signal), 'projects')
  const [modelId, setModelId] = useState<string | null>(null)
  const [topicId, setTopicId] = useState<number | null>(null)
  const [lambda, setLambda] = useState(DEFAULT_LAMBDA)
  const [granularity, setGranularity] = useState<'year' | 'month'>('year')
  const [minWeight, setMinWeight] = useState(0.3)
  const [sourceType, setSourceType] = useState('')
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const detailRef = useRef<HTMLDivElement>(null)

  const all = models.data?.models ?? []
  const model = all.find((m) => m.model_id === modelId) ?? all[0]
  const selected = model && topicId !== null ? { modelId: model.model_id, topicId } : null

  const terms = useApi(
    (signal) => (selected ? getTopicTerms(selected.modelId, selected.topicId, lambda, signal) : Promise.resolve(null)),
    `topic-terms|${selected?.modelId}|${selected?.topicId}|${lambda}`,
  )
  const timeline = useApi(
    (signal) =>
      selected ? getTopicTimeline(selected.modelId, selected.topicId, granularity, signal) : Promise.resolve(null),
    `topic-timeline|${selected?.modelId}|${selected?.topicId}|${granularity}`,
  )
  const articles = useApi(
    (signal) =>
      selected
        ? getTopicArticles(selected.modelId, selected.topicId, { min_weight: minWeight, source_type: sourceType || undefined }, signal)
        : Promise.resolve(null),
    `topic-articles|${selected?.modelId}|${selected?.topicId}|${minWeight}|${sourceType}`,
  )
  const addable = (projects.data ?? []).filter((p) => p.can_manage && !p.archived)

  if (models.error) return <ErrorMessage error={models.error} />
  if (models.loading) return <p className="message">Loading topic models…</p>
  if (!model)
    return (
      <p className="message">
        No topic models yet. Train them with <code>.venv/bin/python scripts/train_topics.py</code>.
      </p>
    )

  const bySize = [...model.topics].sort((a, b) => b.word_share - a.word_share)
  const choose = (id: number) => {
    setTopicId(id)
    setNotice(null)
    // On a phone the details sit below all the topics: bring them into view.
    if (window.matchMedia('(max-width: 760px)').matches) {
      requestAnimationFrame(() => detailRef.current?.scrollIntoView({ block: 'start', behavior: 'smooth' }))
    }
  }

  return (
    <div className="stack">
      <h1 className="page-title">Topics</h1>
      <p className="hint">
        Exploratory LDA topics, one model per language, on Stanza lemmas of nouns, proper nouns, adjectives and verbs
        ({model.n_documents.toLocaleString()} articles, {model.vocabulary_size.toLocaleString()} terms). Topics are
        numbered, not named, and sorted by their share of all words: read the articles before interpreting one.
      </p>

      <div className="segmented" role="group" aria-label="Language">
        {all.map((m) => (
          <button
            key={m.model_id}
            type="button"
            aria-pressed={m.model_id === model.model_id}
            onClick={() => {
              setModelId(m.model_id)
              setTopicId(null)
            }}
          >
            {m.language.toUpperCase()} · {m.n_topics} topics
          </button>
        ))}
      </div>

      <div className="topics-layout">
        <ul className="result-list" aria-label="Topics">
          {bySize.map((t) => (
            <li key={t.topic_id} style={{ padding: '6px 0' }}>
              <button
                type="button"
                className="segment-item"
                aria-pressed={t.topic_id === topicId}
                aria-label={`Topic ${t.topic_id + 1}, ${pct(t.word_share)} of words, leads in ${t.dominant_articles} articles: ${relevantTerms(model, t.topic_id, 8)}`}
                onClick={() => choose(t.topic_id)}
              >
                <strong>Topic {t.topic_id + 1}</strong>
                <span className="tag">{pct(t.word_share)} of words</span>
                <span className="tag">{t.dominant_articles.toLocaleString()} articles lead</span>
                <br />
                {relevantTerms(model, t.topic_id, 8)}
              </button>
            </li>
          ))}
        </ul>

        <div className="stack" ref={detailRef}>
          {selected === null ? (
            <p className="hint">Choose a topic to see its terms and articles.</p>
          ) : (
            <>
              <h2 style={{ margin: 0 }}>
                Topic {selected.topicId + 1}
                <span className="tag">{pct(model.topics[selected.topicId].word_share)} of words</span>
              </h2>

              <label className="field">
                <span>
                  Term ranking: λ = {lambda.toFixed(1)}{' '}
                  <span className="hint">
                    (0 = distinctive for this topic, 1 = most frequent in it; 0.6 is the LDAvis default)
                  </span>
                </span>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.1}
                  value={lambda}
                  onChange={(e) => setLambda(Number(e.target.value))}
                  style={{ minHeight: 0, padding: 0 }}
                />
              </label>

              {terms.error && <ErrorMessage error={terms.error} />}
              {terms.data && (
                <>
                  <TopicTermChart terms={terms.data.terms} language={model.language} />
                  <p className="hint">
                    Closest topics (Jensen-Shannon divergence):{' '}
                    {terms.data.closest.map((c, i) => (
                      <span key={c.topic_id}>
                        {i > 0 && ', '}
                        <button type="button" className="link-button" onClick={() => choose(c.topic_id)}>
                          Topic {c.topic_id + 1}
                        </button>{' '}
                        ({c.jsd.toFixed(2)})
                      </span>
                    ))}
                  </p>
                </>
              )}

              <h3 className="section-divider" style={{ margin: 0 }}>Share of words over time</h3>
              <div className="segmented" role="group" aria-label="Period">
                {(['year', 'month'] as const).map((g) => (
                  <button key={g} type="button" aria-pressed={g === granularity} onClick={() => setGranularity(g)}>
                    {g === 'year' ? 'By year' : 'By month'}
                  </button>
                ))}
              </div>
              {timeline.error && <ErrorMessage error={timeline.error} />}
              {timeline.data && (
                <TopicShareChart
                  series={timeline.data.series}
                  smallSampleArticles={timeline.data.small_sample_articles}
                />
              )}
              <p className="hint">
                Coverage differs by source: Tageszeitung from 2015, the press office from mid-2021, and Italian
                journalism is thin before 2025.
              </p>

              <h3 className="section-divider" style={{ margin: 0 }}>Articles</h3>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
                <div className="segmented" role="group" aria-label="Minimum topic weight">
                  {WEIGHTS.map((w) => (
                    <button key={w} type="button" aria-pressed={w === minWeight} onClick={() => setMinWeight(w)}>
                      ≥ {Math.round(w * 100)}%
                    </button>
                  ))}
                </div>
                <div className="segmented" role="group" aria-label="Source type">
                  {SOURCE_TYPES.map((s) => (
                    <button key={s.value} type="button" aria-pressed={s.value === sourceType} onClick={() => setSourceType(s.value)}>
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>

              {notice && <p className="message">{notice}</p>}
              {articles.error && <ErrorMessage error={articles.error} />}
              {articles.loading && <p className="message">Loading articles…</p>}
              {articles.data && (
                <>
                  <p className="result-count">
                    {articles.data.total.toLocaleString()} articles where this topic weighs at least{' '}
                    {Math.round(minWeight * 100)}%
                    {addable.length > 0 && articles.data.total > 0 && (
                      <button type="button" className="link-button" style={{ marginLeft: 12 }} onClick={() => setSaving(true)}>
                        Save as selection
                      </button>
                    )}
                  </p>
                  <ul className="result-list">
                    {articles.data.articles.map((a) => (
                      <li key={a.id}>
                        <Link to={`/articles/${encodeURIComponent(a.id)}`}>{a.title || a.id}</Link>
                        <p className="result-meta">
                          {a.publish_date?.slice(0, 10)} · {a.source} · weight {Math.round(a.weight * 100)}%
                        </p>
                      </li>
                    ))}
                  </ul>
                  {articles.data.total > articles.data.articles.length && (
                    <p className="hint">Showing the {articles.data.articles.length} strongest; a saved selection keeps all.</p>
                  )}
                </>
              )}
            </>
          )}
        </div>
      </div>

      {saving && selected && articles.data && (
        <SaveSelectionDialog
          filters={{ q: '', sources: [], languages: [model.language], page: 1 }}
          totalCount={articles.data.total}
          selectedIds={articles.data.article_ids}
          projects={addable}
          idsOnly
          defaultName={`Topic ${selected.topicId + 1} (${model.language}): ${relevantTerms(model, selected.topicId, 3)}`}
          defaultDescription={`${model.model_id}, topic ${selected.topicId + 1}, weight ≥ ${minWeight}${
            sourceType ? `, ${sourceType}` : ''
          }. Terms (λ = 0.6): ${relevantTerms(model, selected.topicId, 10)}.`}
          onCancel={() => setSaving(false)}
          onSuccess={(sel, projectName) => {
            setSaving(false)
            setNotice(`Saved "${sel.name}" (${sel.article_count} articles) in ${projectName}.`)
          }}
        />
      )}
    </div>
  )
}
