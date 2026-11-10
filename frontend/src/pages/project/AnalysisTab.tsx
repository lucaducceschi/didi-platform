import { useState } from 'react'
import { Link } from 'react-router'
import {
  type CodeMetrics,
  type Project,
  type RadarLanguageData,
  type SavedSelection,
  type SelectionCompareResponse,
  compareSelections,
  getInterCoderAgreement,
  getProjectAnalysis,
  getProjectComparisonGrid,
  getProjectCorpusComparison,
  listSelections,
} from '../../api'
import { GaugeChart } from '../../components/charts/GaugeChart'
import { KeynessBarChart } from '../../components/charts/KeynessBarChart'
import { RadarChart } from '../../components/charts/RadarChart'
import { ErrorMessage } from '../../components/Message'
import { formatNumber } from '../../format'
import { useApi } from '../../useApi'

interface Props {
  project: Project
}

type AnalysisView = 'corpus' | 'codes' | 'grid' | 'reliability' | 'subcorpus'

export function AnalysisTab({ project }: Props) {
  const [activeView, setActiveView] = useState<AnalysisView>('corpus')
  const [selectedCodeId, setSelectedCodeId] = useState<string | null>(null)
  const [gridRowBy, setGridRowBy] = useState<string>('language')
  const [gridMeasure, setGridMeasure] = useState<string>('count')
  const [expandedCellKey, setExpandedCellKey] = useState<string | null>(null)

  // Subcorpus Comparison State (Milestone 5)
  const [subcorpSelAId, setSubcorpSelAId] = useState<string | null>(null)
  const [subcorpTarget, setSubcorpTarget] = useState<string>('baseline')

  const { data: selectionsData } = useApi<SavedSelection[]>(
    (signal) => listSelections(project.id, signal),
    `selections/${project.id}`
  )
  const selections: SavedSelection[] = selectionsData || []
  const effectiveSelAId = subcorpSelAId || (selections.length > 0 ? selections[0].id : null)

  const isPartition = subcorpTarget.startsWith('partition:')
  const partitionBy = isPartition ? subcorpTarget.replace('partition:', '') : null
  const selBId = !isPartition && subcorpTarget !== 'baseline' ? subcorpTarget : null

  const {
    data: subcorpComp,
    error: subcorpError,
    loading: subcorpLoading,
  } = useApi(
    (signal) => {
      if (!effectiveSelAId) return Promise.resolve(null as unknown as SelectionCompareResponse)
      return compareSelections(
        project.id,
        {
          selection_a_id: effectiveSelAId,
          selection_b_id: selBId,
          partition_by: partitionBy,
        },
        signal
      )
    },
    activeView === 'subcorpus' && effectiveSelAId
      ? `subcorp-comp/${project.id}/${effectiveSelAId}/${subcorpTarget}`
      : 'subcorp:disabled'
  )

  const { data: analysis, error: analysisError, loading: analysisLoading } = useApi(
    (signal) => getProjectAnalysis(project.id, signal),
    `analysis/${project.id}`
  )

  const { data: comparison, error: comparisonError, loading: comparisonLoading } = useApi(
    (signal) => getProjectCorpusComparison(project.id, signal),
    `corpus-comp/${project.id}`
  )

  const { data: gridData, error: gridError, loading: gridLoading } = useApi(
    (signal) => getProjectComparisonGrid(project.id, gridRowBy, gridMeasure, signal),
    `grid/${project.id}/${gridRowBy}/${gridMeasure}`
  )

  const { data: agreementData, error: agreementError, loading: agreementLoading } = useApi(
    (signal) => getInterCoderAgreement(project.id, signal),
    activeView === 'reliability' ? `agreement/${project.id}` : 'agreement:disabled'
  )

  if (analysisError || comparisonError) {
    return <ErrorMessage error={analysisError || comparisonError} />
  }

  if (analysisLoading || comparisonLoading || !analysis || !comparison) {
    return <p className="result-count">Computing project linguistic measures & corpus comparison…</p>
  }

  const summary = analysis.summary
  const codes = analysis.codes
  const selectedCode: CodeMetrics | undefined = codes.find((c) => c.code_id === selectedCodeId) || codes[0]

  const pProfile = comparison.project_profile
  const cBaseline = comparison.corpus_baseline
  const divergence = comparison.divergence

  // Prepare Radar chart overlay data: Project Texts vs Corpus Baseline
  const radarComparisonData: RadarLanguageData[] = []
  if (pProfile) {
    radarComparisonData.push({
      language: pProfile.dominant_language === 'it' ? 'it' : 'de',
      language_label: `Project Texts (${pProfile.dominant_language.toUpperCase()})`,
      article_count: pProfile.article_count,
      net_sentiment: pProfile.net_sentiment,
      moral_density: pProfile.moral_density,
      foundations: pProfile.foundations,
      emotions: {
        anger: pProfile.emotions.anger || 0,
        anticipation: pProfile.emotions.anticipation || 0,
        disgust: pProfile.emotions.disgust || 0,
        fear: pProfile.emotions.fear || 0,
        joy: pProfile.emotions.joy || 0,
        sadness: pProfile.emotions.sadness || 0,
        surprise: pProfile.emotions.surprise || 0,
        trust: pProfile.emotions.trust || 0,
      },
    })
  }
  if (cBaseline) {
    radarComparisonData.push({
      language: cBaseline.language === 'it' ? 'lld_gherd' : 'lld_badia', // Uses secondary distinct color
      language_label: `Corpus Baseline (${cBaseline.language.toUpperCase()})`,
      article_count: cBaseline.article_count,
      net_sentiment: cBaseline.net_sentiment,
      moral_density: cBaseline.moral_density,
      foundations: cBaseline.foundations,
      emotions: {
        anger: cBaseline.emotions.anger || 0,
        anticipation: cBaseline.emotions.anticipation || 0,
        disgust: cBaseline.emotions.disgust || 0,
        fear: cBaseline.emotions.fear || 0,
        joy: cBaseline.emotions.joy || 0,
        sadness: cBaseline.emotions.sadness || 0,
        surprise: cBaseline.emotions.surprise || 0,
        trust: cBaseline.emotions.trust || 0,
      },
    })
  }

  return (
    <div className="stack" style={{ gap: '1.75rem' }}>
      {/* 1. View Switcher Tabs */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border)', paddingBottom: '8px', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            type="button"
            className={activeView === 'corpus' ? 'button' : 'button-quiet'}
            onClick={() => setActiveView('corpus')}
            style={{ fontSize: '13px', padding: '6px 14px' }}
          >
            📊 Project Texts vs. Corpus Baseline
          </button>
          <button
            type="button"
            className={activeView === 'codes' ? 'button' : 'button-quiet'}
            onClick={() => setActiveView('codes')}
            style={{ fontSize: '13px', padding: '6px 14px' }}
          >
            🏷️ Qualitative Codes & Coded Segments ({codes.length})
          </button>
          <button
            type="button"
            className={activeView === 'grid' ? 'button' : 'button-quiet'}
            onClick={() => setActiveView('grid')}
            style={{ fontSize: '13px', padding: '6px 14px' }}
          >
            ▦ Comparison Grid
          </button>
          <button
            type="button"
            className={activeView === 'reliability' ? 'button' : 'button-quiet'}
            onClick={() => setActiveView('reliability')}
            style={{ fontSize: '13px', padding: '6px 14px' }}
          >
            🤝 Inter-Coder Reliability
          </button>
          <button
            type="button"
            className={activeView === 'subcorpus' ? 'button' : 'button-quiet'}
            onClick={() => setActiveView('subcorpus')}
            style={{ fontSize: '13px', padding: '6px 14px' }}
          >
            🔀 Subcorpus Comparison
          </button>
        </div>

        <span style={{ fontSize: '12px', color: 'var(--muted)' }}>
          {summary.total_articles.toLocaleString()} articles in project · {summary.total_passages.toLocaleString()} coded passages
        </span>
      </div>

      {/* VIEW 1: Project Texts vs Corpus Baseline */}
      {activeView === 'corpus' && (
        <div className="stack" style={{ gap: '24px' }}>
          {/* Comparative Benchmark Metric Cards */}
          <section
            aria-label="Comparative Linguistic Benchmarks"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: '14px',
            }}
          >
            <div className="card" style={{ padding: '16px', textAlign: 'center' }}>
              <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>NET SENTIMENT</div>
              <div style={{ fontSize: '24px', fontWeight: 700, margin: '6px 0' }}>
                <span style={{ color: (pProfile?.net_sentiment || 0) >= 0 ? '#1f6f43' : '#a32a2a' }}>
                  {(pProfile?.net_sentiment || 0) > 0 ? `+${pProfile?.net_sentiment}` : pProfile?.net_sentiment}
                </span>
              </div>
              <div style={{ fontSize: '12px', color: 'var(--muted)' }}>
                Corpus Baseline: <strong>{(cBaseline?.net_sentiment || 0) > 0 ? `+${cBaseline?.net_sentiment}` : cBaseline?.net_sentiment}</strong>
              </div>
            </div>

            <div className="card" style={{ padding: '16px', textAlign: 'center' }}>
              <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>READABILITY INDEX</div>
              <div style={{ fontSize: '24px', fontWeight: 700, margin: '6px 0' }}>
                {pProfile?.readability.score.toFixed(1)}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--muted)' }}>
                Baseline: <strong>{cBaseline?.readability.score.toFixed(1)}</strong> ({pProfile?.readability.metric})
              </div>
            </div>

            <div className="card" style={{ padding: '16px', textAlign: 'center' }}>
              <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>TEXT COMPLEXITY (BIBER)</div>
              <div style={{ fontSize: '24px', fontWeight: 700, margin: '6px 0' }}>
                {pProfile?.nominal_ratio.toFixed(2)}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--muted)' }}>
                Nominal ratio (Baseline: <strong>{cBaseline?.nominal_ratio.toFixed(2)}</strong>)
              </div>
            </div>

            <div className="card" style={{ padding: '16px', textAlign: 'center' }}>
              <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>CONCRETENESS (1–5)</div>
              <div style={{ fontSize: '24px', fontWeight: 700, margin: '6px 0' }}>
                {pProfile?.concreteness.toFixed(2)}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--muted)' }}>
                Cognitive construal (Baseline: <strong>{cBaseline?.concreteness.toFixed(2)}</strong>)
              </div>
            </div>
          </section>

          {/* Moral Foundations Radar & JSD Divergence */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
              gap: '20px',
              alignItems: 'start',
            }}
          >
            {/* Radar Overlay Card */}
            <div className="card" style={{ padding: '20px', textAlign: 'center' }}>
              <h3 style={{ fontSize: '16px', margin: '0 0 4px' }}>
                Moral Framing Radar: Project Texts vs. Corpus Baseline
              </h3>
              <p style={{ fontSize: '12px', color: 'var(--muted)', margin: '0 0 16px' }}>
                Comparing 5 moral foundations between your project's articles and regional media
              </p>
              <div style={{ display: 'flex', justifyContent: 'center' }}>
                <RadarChart data={radarComparisonData} size={380} />
              </div>
            </div>

            {/* JSD Divergence & Keyness */}
            <div className="stack" style={{ gap: '16px' }}>
              <div className="card" style={{ padding: '20px' }}>
                <h3 style={{ fontSize: '16px', margin: '0 0 8px' }}>
                  Moral Framing Divergence (JSD)
                </h3>
                <p style={{ fontSize: '12px', color: 'var(--muted)', margin: '0 0 14px' }}>
                  Quantifies how strongly this project's framing deviates from the general corpus
                </p>
                <div style={{ display: 'flex', justifyContent: 'center', margin: '8px 0' }}>
                  <GaugeChart value={divergence?.jsd || 0} width={240} height={140} />
                </div>
                {divergence && (
                  <p style={{ textAlign: 'center', fontSize: '12px', color: 'var(--muted)', margin: '4px 0 0' }}>
                    Primary divergence foundation: <strong style={{ textTransform: 'capitalize', color: 'var(--text)' }}>{divergence.primary_divergence_foundation}</strong>
                  </p>
                )}
              </div>

              {/* Distinctive Keyness Terms */}
              <div className="card" style={{ padding: '20px' }}>
                <h3 style={{ fontSize: '16px', margin: '0 0 6px' }}>
                  Distinctive Project Vocabulary (Dunning G²)
                </h3>
                <p style={{ fontSize: '12px', color: 'var(--muted)', margin: '0 0 12px' }}>
                  Vocabulary statistically overrepresented in this project's texts compared to the rest of the corpus
                </p>
                {comparison.distinctive_terms.length > 0 ? (
                  <KeynessBarChart
                    items={comparison.distinctive_terms}
                    targetLabel={project.name}
                    refLabel="Corpus"
                    width={480}
                  />
                ) : (
                  <p className="result-count">Not enough text to compute differential keyness.</p>
                )}
              </div>
            </div>
          </div>

          {/* Project Articles Quantitative Breakdown Table */}
          <section className="card" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '14px', flexWrap: 'wrap', gap: '8px' }}>
              <div>
                <h3 style={{ fontSize: '16px', margin: '0 0 4px' }}>Project Articles Quantitative Explorer</h3>
                <p style={{ fontSize: '12px', color: 'var(--muted)', margin: 0 }}>
                  Linguistic measures calculated across all {comparison.articles.length.toLocaleString()} articles in this project
                </p>
              </div>
            </div>

            <div style={{ overflowX: 'auto' }}>
              <table className="table" style={{ width: '100%', fontSize: '13px' }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: 'left' }}>Article Title</th>
                    <th style={{ textAlign: 'left' }}>Date</th>
                    <th style={{ textAlign: 'left' }}>Source / Type</th>
                    <th style={{ textAlign: 'right' }}>Words</th>
                    <th style={{ textAlign: 'right' }}>Sentiment</th>
                    <th style={{ textAlign: 'right' }}>Readability</th>
                    <th style={{ textAlign: 'right' }}>Nominal Style</th>
                    <th style={{ textAlign: 'right' }}>Concreteness</th>
                    <th style={{ textAlign: 'left' }}>Top Foundation</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.articles.map((art) => (
                    <tr key={art.id}>
                      <td style={{ fontWeight: 600, maxWidth: '280px' }}>
                        <Link to={`/projects/${project.id}/articles/${encodeURIComponent(art.id)}`}>
                          {art.title}
                        </Link>
                      </td>
                      <td style={{ whiteSpace: 'nowrap' }}>{art.publish_date}</td>
                      <td>
                        <span style={{ display: 'block', fontSize: '12px' }}>{art.source_label}</span>
                        <span className="tag" style={{ fontSize: '10px' }}>{art.source_type_label}</span>
                      </td>
                      <td style={{ textAlign: 'right' }}>{art.word_count.toLocaleString()}</td>
                      <td
                        style={{
                          textAlign: 'right',
                          fontWeight: 600,
                          color: art.net_sentiment >= 0 ? '#1f6f43' : '#a32a2a',
                        }}
                      >
                        {art.net_sentiment >= 0 ? `+${art.net_sentiment}` : art.net_sentiment}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        {art.readability_score != null ? (
                          <span title={art.readability_grade || undefined}>
                            {art.readability_score} ({art.readability_metric})
                          </span>
                        ) : '—'}
                      </td>
                      <td style={{ textAlign: 'right' }}>{art.nominal_ratio.toFixed(2)}</td>
                      <td style={{ textAlign: 'right' }}>{art.concreteness_score.toFixed(2)}</td>
                      <td>
                        <span className="tag" style={{ fontSize: '11px' }}>{art.top_moral_foundation}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}

      {/* VIEW 2: Qualitative Codes & Coded Segments */}
      {activeView === 'codes' && (
        <div className="stack" style={{ gap: '24px' }}>
          {/* Project High-Level KPIs */}
          <section
            aria-label="Project Statistics"
            className="stats-grid"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: '1rem',
            }}
          >
            <div className="card" style={{ padding: '1rem' }}>
              <span style={{ fontSize: '0.85rem', opacity: 0.75, display: 'block' }}>Articles in Project</span>
              <strong style={{ fontSize: '1.6rem' }}>{summary.total_articles.toLocaleString()}</strong>
              <span style={{ fontSize: '0.8rem', opacity: 0.65, display: 'block', marginTop: '0.25rem' }}>
                {summary.total_words.toLocaleString()} words total
              </span>
            </div>

            <div className="card" style={{ padding: '1rem' }}>
              <span style={{ fontSize: '0.85rem', opacity: 0.75, display: 'block' }}>Coded Passages</span>
              <strong style={{ fontSize: '1.6rem' }}>{summary.total_passages.toLocaleString()}</strong>
              <span style={{ fontSize: '0.8rem', opacity: 0.65, display: 'block', marginTop: '0.25rem' }}>
                Across {summary.total_coders} {summary.total_coders === 1 ? 'coder' : 'coders'}
              </span>
            </div>

            <div className="card" style={{ padding: '1rem' }}>
              <span style={{ fontSize: '0.85rem', opacity: 0.75, display: 'block' }}>Language Balance</span>
              <div style={{ marginTop: '0.4rem', fontSize: '0.9rem' }}>
                {Object.entries(summary.languages).map(([lang, count]) => (
                  <span key={lang} className="tag" style={{ marginRight: '0.4rem', textTransform: 'uppercase' }}>
                    {lang}: {count}
                  </span>
                ))}
              </div>
            </div>

            <div className="card" style={{ padding: '1rem' }}>
              <span style={{ fontSize: '0.85rem', opacity: 0.75, display: 'block' }}>Discourse Provenance</span>
              <div style={{ marginTop: '0.4rem', fontSize: '0.9rem' }}>
                {Object.entries(summary.source_types).map(([stype, count]) => (
                  <span key={stype} className="tag" style={{ marginRight: '0.4rem' }}>
                    {stype === 'official_press' ? 'Press office' : 'Journalism'}: {count}
                  </span>
                ))}
              </div>
            </div>
          </section>

          {/* Code Measures Matrix */}
          <section aria-label="Linguistic Measures per Code">
            <div className="row" style={{ justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '8px' }}>
              <div>
                <h2 style={{ fontSize: '1.25rem', margin: 0 }}>Linguistic & Framing Profiler by Code</h2>
                <span style={{ fontSize: '0.85rem', opacity: 0.75 }}>
                  Click a code row to inspect distinctive vocabulary and keyness
                </span>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <a
                  href={`/api/projects/${project.id}/exports/code-measures.csv`}
                  download
                  className="button-quiet"
                  style={{ fontSize: '12px' }}
                >
                  ⬇️ Export Code Measures (CSV)
                </a>
                <a
                  href={`/api/projects/${project.id}/exports/passage-measures.csv`}
                  download
                  className="button-quiet"
                  style={{ fontSize: '12px' }}
                >
                  ⬇️ Export Passage Measures (CSV)
                </a>
              </div>
            </div>

            {codes.length === 0 ? (
              <p className="message">No coded passages found in this project yet.</p>
            ) : (
              <div className="table-wrapper" style={{ overflowX: 'auto' }}>
                <table className="table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid var(--border)', textAlign: 'left' }}>
                      <th style={{ padding: '0.6rem' }}>Code</th>
                      <th style={{ padding: '0.6rem' }}>Passages</th>
                      <th style={{ padding: '0.6rem' }}>Words</th>
                      <th style={{ padding: '0.6rem' }}>Sentiment</th>
                      <th style={{ padding: '0.6rem' }}>Top Moral Foundation</th>
                      <th style={{ padding: '0.6rem' }}>Readability</th>
                      <th style={{ padding: '0.6rem' }}>Concreteness</th>
                      <th style={{ padding: '0.6rem' }}>Nominal Style</th>
                      <th style={{ padding: '0.6rem' }}>Ingroup (1k)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {codes.map((c) => {
                      const isSelected = selectedCode?.code_id === c.code_id
                      return (
                        <tr
                          key={c.code_id}
                          onClick={() => setSelectedCodeId(c.code_id)}
                          style={{
                            cursor: 'pointer',
                            backgroundColor: isSelected ? 'var(--mark)' : undefined,
                            borderBottom: '1px solid var(--border)',
                          }}
                        >
                          <td style={{ padding: '0.6rem', fontWeight: 600 }}>
                            <span
                              style={{
                                display: 'inline-block',
                                width: '10px',
                                height: '10px',
                                borderRadius: '2px',
                                backgroundColor: c.code_color,
                                marginRight: '0.5rem',
                              }}
                            />
                            {c.code_name}
                          </td>
                          <td style={{ padding: '0.6rem' }}>{c.passage_count}</td>
                          <td style={{ padding: '0.6rem' }}>
                            {c.word_count.toLocaleString()}
                            {c.small_sample && (
                              <span
                                className="tag"
                                style={{ marginLeft: '0.4rem', fontSize: '0.7rem', opacity: 0.8 }}
                                title="Fewer than 1,000 words. Interpret linguistic measures as preliminary."
                              >
                                Small sample
                              </span>
                            )}
                          </td>
                          <td style={{ padding: '0.6rem', color: c.sentiment >= 0 ? '#1f6f43' : '#a32a2a', fontWeight: 600 }}>
                            {c.sentiment >= 0 ? `+${formatNumber(c.sentiment, 2)}` : formatNumber(c.sentiment, 2)}
                          </td>
                          <td style={{ padding: '0.6rem' }}>
                            <span className="tag">{c.top_moral_foundation}</span>
                          </td>
                          <td style={{ padding: '0.6rem' }}>
                            {c.readability ? (
                              <span title={c.readability.grade}>
                                {c.readability.metric}: {formatNumber(c.readability.score, 1)}
                              </span>
                            ) : '—'}
                          </td>
                          <td style={{ padding: '0.6rem' }}>
                            {c.concreteness ? (
                              <span title={c.concreteness.label}>
                                {formatNumber(c.concreteness.score, 2)}{' '}
                                <small style={{ opacity: 0.7 }}>({c.concreteness.label.split(' ')[0]})</small>
                              </span>
                            ) : '—'}
                          </td>
                          <td style={{ padding: '0.6rem' }}>
                            {c.complexity ? (
                              <span title={c.complexity.style_label}>
                                {formatNumber(c.complexity.nominal_ratio, 2)}{' '}
                                <small style={{ opacity: 0.7 }}>({c.complexity.style_label.split(' ')[0]})</small>
                              </span>
                            ) : '—'}
                          </td>
                          <td style={{ padding: '0.6rem' }}>
                            {formatNumber(c.ingroup_pronouns.rate_per_1k, 1)}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* Code Deep Dive: Distinctive Keyness (Dunning G²) */}
          {selectedCode && (
            <section
              aria-label="Code Vocabulary Deep Dive"
              className="card"
              style={{ padding: '1.25rem', borderLeft: `4px solid ${selectedCode.code_color}` }}
            >
              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.15rem' }}>
                    Distinctive Keyness for &ldquo;{selectedCode.code_name}&rdquo;
                  </h3>
                  <p style={{ margin: '0.2rem 0 0', fontSize: '0.85rem', opacity: 0.75 }}>
                    Statistically over-represented lemmas (Dunning G² log-likelihood) compared to the rest of the project
                  </p>
                </div>
                <Link
                  to={`/projects/${project.id}/passages?code=${selectedCode.code_id}`}
                  className="button-secondary"
                  style={{ fontSize: '0.85rem' }}
                >
                  View all {selectedCode.passage_count} passages &rarr;
                </Link>
              </div>

              {selectedCode.distinctive_lemmas && selectedCode.distinctive_lemmas.length > 0 ? (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.75rem' }}>
                  {selectedCode.distinctive_lemmas.map((item) => (
                    <Link
                      key={item.lemma}
                      to={`/projects/${project.id}/passages?code=${selectedCode.code_id}&q=${encodeURIComponent(item.lemma)}`}
                      className="tag"
                      style={{
                        padding: '0.4rem 0.6rem',
                        fontSize: '0.9rem',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.4rem',
                        textDecoration: 'none',
                        cursor: 'pointer',
                      }}
                      title={`Click to view passages for '${selectedCode.code_name}' containing '${item.lemma}'. Count: ${item.target_count} | Reference: ${item.reference_count} | G²: ${item.g2}`}
                    >
                      <strong>{item.lemma}</strong>
                      <span style={{ opacity: 0.65, fontSize: '0.75rem' }}>G² {item.g2}</span>
                    </Link>
                  ))}
                </div>
              ) : (
                <p style={{ fontSize: '0.9rem', opacity: 0.75 }}>
                  Not enough passage tokens to compute distinctive lemmas for this code yet.
                </p>
              )}

              {/* Konjunktiv I notice for German */}
              {selectedCode.konjunktiv_i.available && selectedCode.konjunktiv_i.count > 0 && (
                <div style={{ marginTop: '1rem', fontSize: '0.8rem', opacity: 0.75 }}>
                  <em>
                    Reported speech: {selectedCode.konjunktiv_i.count} Konjunktiv I instances (
                    {selectedCode.konjunktiv_i.rate_per_1k} per 1k words). Labelled unvalidated until manual review.
                  </em>
                </div>
              )}
            </section>
          )}
        </div>
      )}

      {/* VIEW 3: Comparison Grid (Stage 4) */}
      {activeView === 'grid' && (
        <div className="stack" style={{ gap: '20px' }}>
          {/* Controls Bar */}
          <div
            className="card"
            style={{
              padding: '16px 20px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '16px',
            }}
          >
            <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'center' }}>
              <label style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ fontWeight: 600 }}>Group Rows By:</span>
                <select
                  value={gridRowBy}
                  onChange={(e) => setGridRowBy(e.target.value)}
                  style={{ padding: '4px 8px', borderRadius: '4px' }}
                >
                  <option value="language">Language (German vs. Italian)</option>
                  <option value="source">News Source (Tageszeitung, Salto, etc.)</option>
                  <option value="source_type">Discourse Type (Journalism vs. Official Press)</option>
                  <option value="year">Publication Year</option>
                </select>
              </label>

              <label style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ fontWeight: 600 }}>Cell Metric:</span>
                <select
                  value={gridMeasure}
                  onChange={(e) => setGridMeasure(e.target.value)}
                  style={{ padding: '4px 8px', borderRadius: '4px' }}
                >
                  <option value="count">Passage Count (Volume)</option>
                  <option value="sentiment">Net Sentiment (-1 to +1)</option>
                  <option value="moral_density">Moral Framing Density (per 1k)</option>
                  <option value="readability">Readability (Gulpease / WSTF)</option>
                  <option value="concreteness">Concreteness (1.0 to 5.0)</option>
                  <option value="nominal_ratio">Nominal Style Ratio</option>
                  <option value="ingroup">Ingroup Pronouns Rate (per 1k)</option>
                </select>
              </label>
            </div>

            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <a
                href={`/api/projects/${project.id}/exports/comparison-grid.csv?row_by=${encodeURIComponent(gridRowBy)}&measure=${encodeURIComponent(gridMeasure)}`}
                download
                className="button-quiet"
                style={{ fontSize: '12px' }}
              >
                ⬇️ Export Matrix (CSV)
              </a>
            </div>
          </div>

          <ErrorMessage error={gridError} />
          {gridLoading && <p className="result-count">Computing comparison matrix…</p>}

          {gridData && (
            <div className="card" style={{ padding: '20px', overflowX: 'auto' }}>
              <div style={{ marginBottom: '14px' }}>
                <h3 style={{ fontSize: '16px', margin: '0 0 4px' }}>
                  Cross-Tabulation Matrix: {gridRowBy.toUpperCase()} × Qualitative Codes
                </h3>
                <p style={{ fontSize: '12px', color: 'var(--muted)', margin: 0 }}>
                  Showing {gridMeasure.replace('_', ' ')} for each cross-section. Click any cell to view contributing passages or example quotes.
                </p>
              </div>

              <table className="table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid var(--border)' }}>
                    <th style={{ textAlign: 'left', padding: '10px 12px', minWidth: '160px', backgroundColor: 'var(--surface)' }}>
                      {gridRowBy === 'language' ? 'Language Variety' : gridRowBy === 'source' ? 'News Source' : gridRowBy === 'source_type' ? 'Discourse Type' : 'Publication Year'}
                    </th>
                    {gridData.columns.map((col) => (
                      <th
                        key={col.id}
                        style={{
                          textAlign: 'center',
                          padding: '10px 12px',
                          minWidth: '180px',
                          borderLeft: '1px solid var(--border)',
                          backgroundColor: 'var(--surface)',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
                          <span style={{ width: 10, height: 10, borderRadius: 2, backgroundColor: col.color }} />
                          <span style={{ fontWeight: 600 }}>{col.name}</span>
                        </div>
                        <span style={{ fontSize: '11px', color: 'var(--muted)', display: 'block', marginTop: '2px' }}>
                          {col.total_passages.toLocaleString()} passages total
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {gridData.rows.map((row) => (
                    <tr key={row.id} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '12px', fontWeight: 600, verticalAlign: 'top', backgroundColor: 'var(--canvas-subtle, rgba(0,0,0,0.01))' }}>
                        <div>{row.label}</div>
                        <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '2px' }}>
                          {row.total_passages} passages across {row.total_articles} articles
                        </div>
                      </td>
                      {gridData.columns.map((col) => {
                        const cellKey = `${row.id}:${col.id}`
                        const cell = gridData.cells[cellKey]
                        const isExpanded = expandedCellKey === cellKey
                        const rowParam = gridRowBy === 'language' ? `language=${encodeURIComponent(row.id)}` : gridRowBy === 'source' ? `source=${encodeURIComponent(row.id)}` : gridRowBy === 'source_type' ? `type=${encodeURIComponent(row.id)}` : `q=${encodeURIComponent(row.id)}`

                        if (!cell || cell.passage_count === 0) {
                          return (
                            <td
                              key={col.id}
                              style={{
                                textAlign: 'center',
                                padding: '12px',
                                color: 'var(--muted)',
                                borderLeft: '1px solid var(--border)',
                                verticalAlign: 'middle',
                              }}
                            >
                              <span style={{ opacity: 0.4 }}>—</span>
                            </td>
                          )
                        }

                        return (
                          <td
                            key={col.id}
                            style={{
                              padding: '12px',
                              borderLeft: '1px solid var(--border)',
                              verticalAlign: 'top',
                              backgroundColor: isExpanded ? 'rgba(31, 95, 139, 0.05)' : undefined,
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '4px' }}>
                              <span style={{ fontSize: '15px', fontWeight: 700 }}>
                                {cell.measure_label}
                              </span>
                              {cell.small_sample && (
                                <span
                                  className="tag"
                                  style={{ fontSize: '9px', padding: '1px 4px' }}
                                  title="Fewer than 30 passages or 1,000 words. Small sample flag."
                                >
                                  Small sample
                                </span>
                              )}
                            </div>

                            <div style={{ fontSize: '11px', color: 'var(--muted)', marginBottom: '6px' }}>
                              {cell.passage_count} passages · {cell.article_count} {cell.article_count === 1 ? 'article' : 'articles'} · {cell.coder_count} {cell.coder_count === 1 ? 'coder' : 'coders'}
                            </div>

                            {/* Distinctive lemmas in cell */}
                            {cell.distinctive_lemmas && cell.distinctive_lemmas.length > 0 && (
                              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginBottom: '8px' }}>
                                {cell.distinctive_lemmas.map((lem) => (
                                  <Link
                                    key={lem}
                                    to={`/projects/${project.id}/passages?code=${col.id}&${rowParam}&q=${encodeURIComponent(lem)}`}
                                    className="tag"
                                    style={{ fontSize: '10px', textDecoration: 'none' }}
                                    title={`Click to filter passages for ${lem}`}
                                  >
                                    {lem}
                                  </Link>
                                ))}
                              </div>
                            )}

                            {/* Drill-down Actions */}
                            <div style={{ display: 'flex', gap: '8px', fontSize: '11px', marginTop: '6px', alignItems: 'center' }}>
                              <Link
                                to={`/projects/${project.id}/passages?code=${col.id}&${rowParam}`}
                                style={{ fontWeight: 600 }}
                              >
                                View {cell.passage_count} passages &rarr;
                              </Link>
                              {cell.example_quotes.length > 0 && (
                                <button
                                  type="button"
                                  className="button-quiet"
                                  style={{ fontSize: '11px', padding: '2px 6px' }}
                                  onClick={() => setExpandedCellKey(isExpanded ? null : cellKey)}
                                >
                                  {isExpanded ? 'Hide quotes' : 'Quotes (3)'}
                                </button>
                              )}
                            </div>

                            {/* Expanded Example Quotes */}
                            {isExpanded && cell.example_quotes.length > 0 && (
                              <div
                                style={{
                                  marginTop: '10px',
                                  padding: '8px 10px',
                                  backgroundColor: 'var(--canvas-subtle, rgba(0,0,0,0.03))',
                                  borderRadius: '6px',
                                  fontSize: '11px',
                                  display: 'flex',
                                  flexDirection: 'column',
                                  gap: '8px',
                                }}
                              >
                                <span style={{ fontWeight: 600, color: 'var(--muted)' }}>Example Quotes:</span>
                                {cell.example_quotes.map((q, idx) => (
                                  <div key={idx} style={{ borderLeft: `2px solid ${col.color}`, paddingLeft: '6px' }}>
                                    <div style={{ fontStyle: 'italic', marginBottom: '2px' }}>&ldquo;{q.quote}&rdquo;</div>
                                    <Link
                                      to={`/projects/${project.id}/articles/${encodeURIComponent(q.article_id)}?segment=${q.annotation_id}`}
                                      style={{ color: 'var(--muted)', fontSize: '10px' }}
                                    >
                                      {q.article_title} ({q.publish_date})
                                    </Link>
                                  </div>
                                ))}
                              </div>
                            )}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* VIEW 4: Inter-Coder Reliability (Milestone 4) */}
      {activeView === 'reliability' && (
        <div className="stack" style={{ gap: '20px' }}>
          <div className="card" style={{ padding: '16px 20px' }}>
            <h3 style={{ fontSize: '16px', margin: '0 0 4px' }}>
              Inter-Coder Reliability & Agreement (Cohen&apos;s &kappa;)
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--muted)', margin: 0 }}>
              Calculates coding consistency across independent coders on overlapping passage spans (Intersection-over-Union &ge; 0.3) within the same articles. Grounded in Landis &amp; Koch (1977) benchmark criteria.
            </p>
          </div>

          <ErrorMessage error={agreementError} />
          {agreementLoading && <p className="result-count">Computing inter-coder agreement…</p>}

          {agreementData && (
            <>
              {agreementData.total_coders < 2 ? (
                <div className="card" style={{ padding: '24px', textAlign: 'center' }}>
                  <div style={{ fontSize: '32px', marginBottom: '8px' }}>👥</div>
                  <h4 style={{ margin: '0 0 8px', fontSize: '15px' }}>Multiple Coders Required</h4>
                  <p style={{ fontSize: '13px', color: 'var(--muted)', maxWidth: '520px', margin: '0 auto' }}>
                    At least 2 independent coders with overlapping annotated text passages are required to compute Cohen&apos;s &kappa; and pairwise agreement. Currently, {agreementData.total_coders} coder has coded passages in this project.
                  </p>
                </div>
              ) : (
                <>
                  {/* Reliability KPI Cards */}
                  <section
                    aria-label="Reliability Metrics"
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                      gap: '14px',
                    }}
                  >
                    <div className="card" style={{ padding: '16px', textAlign: 'center' }}>
                      <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>GLOBAL COHEN&apos;S &kappa;</div>
                      <div style={{ fontSize: '26px', fontWeight: 700, margin: '6px 0' }}>
                        <span
                          style={{
                            color:
                              agreementData.global_kappa >= 0.8
                                ? '#1f6f43'
                                : agreementData.global_kappa >= 0.6
                                ? '#1f5f8b'
                                : agreementData.global_kappa >= 0.4
                                ? '#d97706'
                                : '#dc2626',
                          }}
                        >
                          {agreementData.global_kappa.toFixed(3)}
                        </span>
                      </div>
                      <span
                        className="tag"
                        style={{
                          fontSize: '11px',
                          padding: '2px 8px',
                          backgroundColor:
                            agreementData.global_kappa >= 0.6
                              ? 'rgba(31, 111, 67, 0.1)'
                              : 'rgba(217, 119, 6, 0.1)',
                          color:
                            agreementData.global_kappa >= 0.6
                              ? '#1f6f43'
                              : '#d97706',
                          fontWeight: 600,
                        }}
                      >
                        {agreementData.global_interpretation}
                      </span>
                    </div>

                    <div className="card" style={{ padding: '16px', textAlign: 'center' }}>
                      <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>OBSERVED AGREEMENT (P<sub>o</sub>)</div>
                      <div style={{ fontSize: '26px', fontWeight: 700, margin: '6px 0' }}>
                        {(agreementData.global_observed_agreement * 100).toFixed(1)}%
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--muted)' }}>
                        {agreementData.total_agreed_segments} of {agreementData.total_overlapping_segments} segments agreed
                      </div>
                    </div>

                    <div className="card" style={{ padding: '16px', textAlign: 'center' }}>
                      <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>OVERLAPPING PASSAGES</div>
                      <div style={{ fontSize: '26px', fontWeight: 700, margin: '6px 0' }}>
                        {agreementData.total_overlapping_segments}
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--muted)' }}>
                        Across {agreementData.total_coders} active coders
                      </div>
                    </div>

                    <div className="card" style={{ padding: '16px', textAlign: 'center' }}>
                      <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>DISAGREEMENTS</div>
                      <div style={{ fontSize: '26px', fontWeight: 700, margin: '6px 0', color: agreementData.disagreements.length > 0 ? '#dc2626' : 'inherit' }}>
                        {agreementData.disagreements.length}
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--muted)' }}>
                        {agreementData.disagreements.length > 0 ? 'Requiring adjudication' : 'Perfect agreement'}
                      </div>
                    </div>
                  </section>

                  {/* Pairwise Coder Grid */}
                  <div className="card" style={{ padding: '20px' }}>
                    <h4 style={{ fontSize: '14px', margin: '0 0 12px' }}>Pairwise Coder Agreement</h4>
                    <table className="table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                      <thead>
                        <tr style={{ borderBottom: '2px solid var(--border)', textAlign: 'left' }}>
                          <th style={{ padding: '8px 12px' }}>Coder Pair</th>
                          <th style={{ padding: '8px 12px', textAlign: 'right' }}>Overlapping</th>
                          <th style={{ padding: '8px 12px', textAlign: 'right' }}>Agreed</th>
                          <th style={{ padding: '8px 12px', textAlign: 'right' }}>Observed (P<sub>o</sub>)</th>
                          <th style={{ padding: '8px 12px', textAlign: 'right' }}>Chance (P<sub>e</sub>)</th>
                          <th style={{ padding: '8px 12px', textAlign: 'right' }}>Cohen&apos;s &kappa;</th>
                          <th style={{ padding: '8px 12px' }}>Interpretation</th>
                        </tr>
                      </thead>
                      <tbody>
                        {agreementData.pairs.map((p, idx) => (
                          <tr key={idx} style={{ borderBottom: '1px solid var(--border)' }}>
                            <td style={{ padding: '10px 12px', fontWeight: 500 }}>
                              {p.coder_1.display_name} &amp; {p.coder_2.display_name}
                            </td>
                            <td style={{ padding: '10px 12px', textAlign: 'right' }}>{p.overlapping_segments}</td>
                            <td style={{ padding: '10px 12px', textAlign: 'right' }}>{p.agreed_segments}</td>
                            <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600 }}>
                              {(p.observed_agreement * 100).toFixed(1)}%
                            </td>
                            <td style={{ padding: '10px 12px', textAlign: 'right', color: 'var(--muted)' }}>
                              {(p.chance_agreement * 100).toFixed(1)}%
                            </td>
                            <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 700 }}>
                              {p.cohens_kappa.toFixed(3)}
                            </td>
                            <td style={{ padding: '10px 12px' }}>
                              <span className="tag" style={{ fontSize: '11px', padding: '1px 6px' }}>
                                {p.interpretation}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Code Confusion Matrix */}
                  {agreementData.confusion_matrix.length > 0 && (
                    <div className="card" style={{ padding: '20px' }}>
                      <h4 style={{ fontSize: '14px', margin: '0 0 4px' }}>Code Confusion Frequency</h4>
                      <p style={{ fontSize: '12px', color: 'var(--muted)', margin: '0 0 12px' }}>
                        Pairs of qualitative codes most frequently assigned to the same text passages by different coders.
                      </p>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                        {agreementData.confusion_matrix.map((c, idx) => (
                          <div
                            key={idx}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '6px',
                              padding: '6px 12px',
                              borderRadius: '6px',
                              border: '1px solid var(--border)',
                              backgroundColor: 'var(--surface)',
                              fontSize: '12px',
                            }}
                          >
                            <span style={{ width: 8, height: 8, borderRadius: 2, backgroundColor: c.code_1.color }} />
                            <span style={{ fontWeight: 600 }}>{c.code_1.name}</span>
                            <span style={{ color: 'var(--muted)' }}>&harr;</span>
                            <span style={{ width: 8, height: 8, borderRadius: 2, backgroundColor: c.code_2.color }} />
                            <span style={{ fontWeight: 600 }}>{c.code_2.name}</span>
                            <span
                              className="tag"
                              style={{
                                fontSize: '11px',
                                padding: '1px 5px',
                                marginLeft: '4px',
                                backgroundColor: 'rgba(220, 38, 38, 0.1)',
                                color: '#dc2626',
                                fontWeight: 700,
                              }}
                            >
                              {c.count} {c.count === 1 ? 'disagreement' : 'disagreements'}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Disagreements Table */}
                  <div className="card" style={{ padding: '20px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                      <div>
                        <h4 style={{ fontSize: '14px', margin: '0 0 4px' }}>Disagreement Passages &amp; Adjudication</h4>
                        <p style={{ fontSize: '12px', color: 'var(--muted)', margin: 0 }}>
                          Passages where coders selected overlapping text but applied different qualitative codes. Click to adjudicate directly in the reader.
                        </p>
                      </div>
                      <span style={{ fontSize: '12px', color: 'var(--muted)' }}>
                        {agreementData.disagreements.length} total
                      </span>
                    </div>

                    {agreementData.disagreements.length === 0 ? (
                      <p style={{ fontSize: '13px', color: 'var(--muted)', textAlign: 'center', padding: '16px' }}>
                        🎉 No code disagreements found among overlapping passages!
                      </p>
                    ) : (
                      <div className="stack" style={{ gap: '10px' }}>
                        {agreementData.disagreements.map((d, idx) => (
                          <div
                            key={idx}
                            style={{
                              padding: '12px 14px',
                              border: '1px solid var(--border)',
                              borderRadius: '6px',
                              backgroundColor: 'var(--canvas-subtle, rgba(0,0,0,0.01))',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '8px',
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
                              <div style={{ fontSize: '13px', fontStyle: 'italic', lineHeight: 1.5 }}>
                                &ldquo;{d.quote}&rdquo;
                              </div>
                              <Link
                                to={`/projects/${project.id}/articles/${encodeURIComponent(d.article_id)}?pos=${d.start_pos}&q=${encodeURIComponent(d.quote.slice(0, 30))}`}
                                className="button-secondary"
                                style={{ fontSize: '11px', padding: '3px 8px', whiteSpace: 'nowrap' }}
                              >
                                Resolve in Reader &rarr;
                              </Link>
                            </div>

                            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '12px', flexWrap: 'wrap' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <span style={{ color: 'var(--muted)' }}>{d.coder_1}:</span>
                                <span
                                  className="tag"
                                  style={{
                                    fontSize: '11px',
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: '4px',
                                  }}
                                >
                                  <span style={{ width: 8, height: 8, borderRadius: 2, backgroundColor: d.code_1_color }} />
                                  <strong>{d.code_1_name}</strong>
                                </span>
                              </div>

                              <span style={{ color: 'var(--muted)' }}>vs</span>

                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <span style={{ color: 'var(--muted)' }}>{d.coder_2}:</span>
                                <span
                                  className="tag"
                                  style={{
                                    fontSize: '11px',
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: '4px',
                                  }}
                                >
                                  <span style={{ width: 8, height: 8, borderRadius: 2, backgroundColor: d.code_2_color }} />
                                  <strong>{d.code_2_name}</strong>
                                </span>
                              </div>

                              <span style={{ fontSize: '11px', color: 'var(--muted)', marginLeft: 'auto' }}>
                                Span overlap (IoU): {(d.iou * 100).toFixed(0)}% · Pos: {d.start_pos}&ndash;{d.end_pos}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}
            </>
          )}
        </div>
      )}
      {/* VIEW 5: Subcorpus Comparison (Milestone 5) */}
      {activeView === 'subcorpus' && (
        <div className="stack" style={{ gap: '20px' }}>
          {/* Controls Bar */}
          <div className="card" style={{ padding: '16px 20px' }}>
            <div style={{ marginBottom: '12px' }}>
              <h3 style={{ fontSize: '16px', margin: '0 0 4px' }}>
                Subcorpus Comparative Analysis Engine
              </h3>
              <p style={{ fontSize: '13px', color: 'var(--muted)', margin: 0 }}>
                Compare moral framing, discrete emotions, vocabulary keyness (Dunning G&sup2;), and stylistic metrics across saved corpus selections, partitions, or against the regional baseline.
              </p>
            </div>

            {selections.length === 0 ? (
              <div style={{ padding: '16px', textAlign: 'center', backgroundColor: 'var(--canvas-subtle, rgba(0,0,0,0.02))', borderRadius: '6px' }}>
                <p style={{ fontSize: '13px', color: 'var(--muted)', margin: '0 0 8px' }}>
                  No saved corpus selections found in this project yet.
                </p>
                <Link to="/search" className="button-secondary" style={{ fontSize: '12px' }}>
                  Go to Corpus Search to Save Selections &rarr;
                </Link>
              </div>
            ) : (
              <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'center' }}>
                <label style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ fontWeight: 600 }}>Selection A:</span>
                  <select
                    value={effectiveSelAId || ''}
                    onChange={(e) => setSubcorpSelAId(e.target.value)}
                    style={{ padding: '6px 10px', borderRadius: '4px', fontSize: '13px' }}
                  >
                    {selections.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name} ({s.article_count} articles)
                      </option>
                    ))}
                  </select>
                </label>

                <span style={{ fontWeight: 600, color: 'var(--muted)' }}>vs.</span>

                <label style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ fontWeight: 600 }}>Compare Against:</span>
                  <select
                    value={subcorpTarget}
                    onChange={(e) => setSubcorpTarget(e.target.value)}
                    style={{ padding: '6px 10px', borderRadius: '4px', fontSize: '13px' }}
                  >
                    <option value="baseline">Regional Corpus Baseline</option>
                    {selections.filter((s) => s.id !== effectiveSelAId).length > 0 && (
                      <optgroup label="Other Saved Selections">
                        {selections
                          .filter((s) => s.id !== effectiveSelAId)
                          .map((s) => (
                            <option key={s.id} value={s.id}>
                              {s.name} ({s.article_count} articles)
                            </option>
                          ))}
                      </optgroup>
                    )}
                    <optgroup label="Partition Selection A Subsets">
                      <option value="partition:language">Partition by Language (German vs. Italian)</option>
                      <option value="partition:source_type">Partition by Discourse (Journalism vs. Press)</option>
                      <option value="partition:source">Partition by News Source (Top 2)</option>
                      <option value="partition:year">Partition by Publication Period</option>
                    </optgroup>
                  </select>
                </label>
              </div>
            )}
          </div>

          <ErrorMessage error={subcorpError} />
          {subcorpLoading && <p className="result-count">Computing comparative linguistics, radar, and Dunning G&sup2; keyness…</p>}

          {subcorpComp && (
            <>
              {/* Header Title with Comparison Profiles */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'baseline',
                  flexWrap: 'wrap',
                  gap: '12px',
                  borderBottom: '1px solid var(--border)',
                  paddingBottom: '10px',
                }}
              >
                <div>
                  <h4 style={{ fontSize: '17px', margin: '0 0 4px' }}>
                    <span style={{ color: '#1f77b4' }}>{subcorpComp.profile_a.label}</span>
                    <span style={{ margin: '0 8px', color: 'var(--muted)' }}>vs.</span>
                    <span style={{ color: '#ff7f0e' }}>{subcorpComp.profile_b.label}</span>
                  </h4>
                  <span style={{ fontSize: '12px', color: 'var(--muted)' }}>
                    {subcorpComp.profile_a.article_count.toLocaleString()} articles ({formatNumber(subcorpComp.profile_a.total_words)} words) vs.{' '}
                    {subcorpComp.profile_b.article_count.toLocaleString()} articles ({formatNumber(subcorpComp.profile_b.total_words)} words)
                  </span>
                </div>

                <div style={{ display: 'flex', gap: '8px' }}>
                  <span className="tag" style={{ fontSize: '11px' }}>
                    Mode: {subcorpComp.comparison_type.replace(/_/g, ' ')}
                  </span>
                </div>
              </div>

              {/* Side-by-Side KPI Cards */}
              <section
                aria-label="Subcorpus Comparison Metrics"
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                  gap: '14px',
                }}
              >
                <div className="card" style={{ padding: '16px', textAlign: 'center' }}>
                  <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>NET SENTIMENT</div>
                  <div style={{ fontSize: '20px', fontWeight: 700, margin: '6px 0', display: 'flex', justifyContent: 'center', gap: '12px' }}>
                    <span style={{ color: subcorpComp.profile_a.net_sentiment >= 0 ? '#1f6f43' : '#a32a2a' }}>
                      {subcorpComp.profile_a.net_sentiment > 0 ? `+${subcorpComp.profile_a.net_sentiment}` : subcorpComp.profile_a.net_sentiment}
                    </span>
                    <span style={{ color: 'var(--muted)', opacity: 0.5 }}>/</span>
                    <span style={{ color: subcorpComp.profile_b.net_sentiment >= 0 ? '#1f6f43' : '#a32a2a' }}>
                      {subcorpComp.profile_b.net_sentiment > 0 ? `+${subcorpComp.profile_b.net_sentiment}` : subcorpComp.profile_b.net_sentiment}
                    </span>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--muted)' }}>
                    &Delta; = {(subcorpComp.profile_a.net_sentiment - subcorpComp.profile_b.net_sentiment).toFixed(3)}
                  </div>
                </div>

                <div className="card" style={{ padding: '16px', textAlign: 'center' }}>
                  <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>READABILITY (GULPEASE/WSTF)</div>
                  <div style={{ fontSize: '20px', fontWeight: 700, margin: '6px 0', display: 'flex', justifyContent: 'center', gap: '12px' }}>
                    <span style={{ color: '#1f77b4' }}>{subcorpComp.profile_a.readability.score.toFixed(1)}</span>
                    <span style={{ color: 'var(--muted)', opacity: 0.5 }}>/</span>
                    <span style={{ color: '#ff7f0e' }}>{subcorpComp.profile_b.readability.score.toFixed(1)}</span>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--muted)' }}>
                    {subcorpComp.profile_a.readability.metric} vs. {subcorpComp.profile_b.readability.metric}
                  </div>
                </div>

                <div className="card" style={{ padding: '16px', textAlign: 'center' }}>
                  <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>MORAL DENSITY (PER 1K)</div>
                  <div style={{ fontSize: '20px', fontWeight: 700, margin: '6px 0', display: 'flex', justifyContent: 'center', gap: '12px' }}>
                    <span style={{ color: '#1f77b4' }}>{subcorpComp.profile_a.moral_density.toFixed(1)}</span>
                    <span style={{ color: 'var(--muted)', opacity: 0.5 }}>/</span>
                    <span style={{ color: '#ff7f0e' }}>{subcorpComp.profile_b.moral_density.toFixed(1)}</span>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--muted)' }}>
                    Moral tokens per 1,000 words
                  </div>
                </div>

                <div className="card" style={{ padding: '16px', textAlign: 'center' }}>
                  <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>TEXT COMPLEXITY (BIBER)</div>
                  <div style={{ fontSize: '20px', fontWeight: 700, margin: '6px 0', display: 'flex', justifyContent: 'center', gap: '12px' }}>
                    <span style={{ color: '#1f77b4' }}>{subcorpComp.profile_a.nominal_ratio.toFixed(2)}</span>
                    <span style={{ color: 'var(--muted)', opacity: 0.5 }}>/</span>
                    <span style={{ color: '#ff7f0e' }}>{subcorpComp.profile_b.nominal_ratio.toFixed(2)}</span>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--muted)' }}>
                    Nominal Style Ratio (Nouns/Verbs)
                  </div>
                </div>

                <div className="card" style={{ padding: '16px', textAlign: 'center' }}>
                  <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>INGROUP PRONOUNS (PER 1K)</div>
                  <div style={{ fontSize: '20px', fontWeight: 700, margin: '6px 0', display: 'flex', justifyContent: 'center', gap: '12px' }}>
                    <span style={{ color: '#1f77b4' }}>{subcorpComp.profile_a.ingroup_pronouns_rate.toFixed(1)}</span>
                    <span style={{ color: 'var(--muted)', opacity: 0.5 }}>/</span>
                    <span style={{ color: '#ff7f0e' }}>{subcorpComp.profile_b.ingroup_pronouns_rate.toFixed(1)}</span>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--muted)' }}>
                    wir/uns/unser vs noi/ci/nostro
                  </div>
                </div>
              </section>

              {/* Charts Section: Radar Overlay + JSD Gauges + Emotions */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'minmax(340px, 1fr) minmax(340px, 1fr)',
                  gap: '20px',
                }}
              >
                {/* 5-Axis Moral Foundations Radar Overlay */}
                <div className="card" style={{ padding: '20px' }}>
                  <h4 style={{ fontSize: '14px', margin: '0 0 4px' }}>
                    5-Axis Moral Foundations Framing (Overlay)
                  </h4>
                  <p style={{ fontSize: '12px', color: 'var(--muted)', margin: '0 0 16px' }}>
                    Comparing foundation density vectors: Care, Fairness, Loyalty, Authority, Sanctity.
                  </p>
                  <div style={{ display: 'flex', justifyContent: 'center' }}>
                    <RadarChart
                      data={[
                        {
                          language: 'de',
                          language_label: subcorpComp.profile_a.label,
                          article_count: subcorpComp.profile_a.article_count,
                          net_sentiment: subcorpComp.profile_a.net_sentiment,
                          moral_density: subcorpComp.profile_a.moral_density,
                          foundations: subcorpComp.profile_a.foundations,
                          emotions: subcorpComp.profile_a.emotions as any,
                        },
                        {
                          language: 'lld_gherd', // Distinct orange color
                          language_label: subcorpComp.profile_b.label,
                          article_count: subcorpComp.profile_b.article_count,
                          net_sentiment: subcorpComp.profile_b.net_sentiment,
                          moral_density: subcorpComp.profile_b.moral_density,
                          foundations: subcorpComp.profile_b.foundations,
                          emotions: subcorpComp.profile_b.emotions as any,
                        },
                      ]}
                      size={360}
                    />
                  </div>
                </div>

                {/* Framing Divergence & Discrete Emotions */}
                <div className="stack" style={{ gap: '16px' }}>
                  <div className="card" style={{ padding: '20px', display: 'flex', alignItems: 'center', justifyContent: 'space-around' }}>
                    <GaugeChart
                      value={subcorpComp.divergence.mfdi}
                      title="MFDI (Moral Divergence)"
                      width={200}
                      height={130}
                    />
                    <GaugeChart
                      value={subcorpComp.divergence.emotion_jsd}
                      title="Emotion Divergence (JSD)"
                      width={200}
                      height={130}
                    />
                  </div>

                  {/* Discrete Emotions Comparison */}
                  <div className="card" style={{ padding: '20px' }}>
                    <h4 style={{ fontSize: '14px', margin: '0 0 10px' }}>Discrete Emotions Comparison (Plutchik)</h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12px' }}>
                      {['anger', 'anticipation', 'disgust', 'fear', 'joy', 'sadness', 'surprise', 'trust'].map((em) => {
                        const valA = subcorpComp.profile_a.emotions[em] || 0
                        const valB = subcorpComp.profile_b.emotions[em] || 0
                        const maxVal = Math.max(valA, valB, 1)
                        return (
                          <div key={em} style={{ display: 'grid', gridTemplateColumns: '80px 1fr 60px 1fr 60px', alignItems: 'center', gap: '8px' }}>
                            <span style={{ fontWeight: 600, textTransform: 'capitalize' }}>{em}</span>
                            <div style={{ height: '8px', backgroundColor: 'var(--border)', borderRadius: '4px', overflow: 'hidden' }}>
                              <div style={{ height: '100%', width: `${(valA / (maxVal * 1.5)) * 100}%`, backgroundColor: '#1f77b4' }} />
                            </div>
                            <span style={{ textAlign: 'right', fontSize: '11px', color: '#1f77b4', fontWeight: 600 }}>{valA.toFixed(1)}</span>
                            <div style={{ height: '8px', backgroundColor: 'var(--border)', borderRadius: '4px', overflow: 'hidden' }}>
                              <div style={{ height: '100%', width: `${(valB / (maxVal * 1.5)) * 100}%`, backgroundColor: '#ff7f0e' }} />
                            </div>
                            <span style={{ textAlign: 'right', fontSize: '11px', color: '#ff7f0e', fontWeight: 600 }}>{valB.toFixed(1)}</span>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                </div>
              </div>

              {/* Differential Vocabulary Keyness (Dunning G²) */}
              <div className="card" style={{ padding: '20px' }}>
                <div style={{ marginBottom: '14px' }}>
                  <h4 style={{ fontSize: '15px', margin: '0 0 4px' }}>
                    Distinctive Differential Vocabulary (Dunning Log-Likelihood G&sup2;)
                  </h4>
                  <p style={{ fontSize: '12px', color: 'var(--muted)', margin: 0 }}>
                    Identifies terms with statistically significant over-representation. Click any lemma to open KWIC concordance or filter passages.
                  </p>
                </div>

                {subcorpComp.distinctive_terms_a.length === 0 && subcorpComp.distinctive_terms_b.length === 0 ? (
                  <p style={{ fontSize: '13px', color: 'var(--muted)', textAlign: 'center', padding: '16px' }}>
                    Not enough text in one of the subsets to compute statistically significant differential keyness.
                  </p>
                ) : (
                  <>
                    <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '16px' }}>
                      <KeynessBarChart
                        items={[
                          ...subcorpComp.distinctive_terms_a.map((t) => ({
                            term: t.term,
                            target_per_1k: t.target_per_1k,
                            ref_per_1k: t.ref_per_1k,
                            g2: t.g2,
                          })),
                          ...subcorpComp.distinctive_terms_b.map((t) => ({
                            term: t.term,
                            target_per_1k: t.ref_per_1k,
                            ref_per_1k: t.target_per_1k,
                            g2: -t.g2,
                          })),
                        ]}
                        targetLabel={subcorpComp.profile_a.label}
                        refLabel={subcorpComp.profile_b.label}
                        width={680}
                      />
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
                      <div>
                        <div style={{ fontSize: '12px', fontWeight: 600, color: '#1f77b4', marginBottom: '8px' }}>
                          Distinctive to {subcorpComp.profile_a.label}:
                        </div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                          {subcorpComp.distinctive_terms_a.map((t) => (
                            <Link
                              key={t.term}
                              to={`/search?q=${encodeURIComponent(t.term)}&view=kwic`}
                              className="tag"
                              style={{
                                fontSize: '12px',
                                textDecoration: 'none',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                              }}
                              title={`Click to open KWIC Concordance for '${t.term}'. Count: ${t.target_count} vs ${t.ref_count} | G²: ${t.g2}`}
                            >
                              <strong>{t.term}</strong>
                              <span style={{ fontSize: '10px', opacity: 0.65 }}>G&sup2; {t.g2}</span>
                            </Link>
                          ))}
                        </div>
                      </div>

                      <div>
                        <div style={{ fontSize: '12px', fontWeight: 600, color: '#ff7f0e', marginBottom: '8px' }}>
                          Distinctive to {subcorpComp.profile_b.label}:
                        </div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                          {subcorpComp.distinctive_terms_b.map((t) => (
                            <Link
                              key={t.term}
                              to={`/search?q=${encodeURIComponent(t.term)}&view=kwic`}
                              className="tag"
                              style={{
                                fontSize: '12px',
                                textDecoration: 'none',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                              }}
                              title={`Click to open KWIC Concordance for '${t.term}'. Count: ${t.target_count} vs ${t.ref_count} | G²: ${t.g2}`}
                            >
                              <strong>{t.term}</strong>
                              <span style={{ fontSize: '10px', opacity: 0.65 }}>G&sup2; {t.g2}</span>
                            </Link>
                          ))}
                        </div>
                      </div>
                    </div>
                  </>
                )}
              </div>

              {/* Longitudinal Trajectory Table */}
              {subcorpComp.profile_a.timeline.length > 0 && (
                <div className="card" style={{ padding: '20px' }}>
                  <h4 style={{ fontSize: '14px', margin: '0 0 10px' }}>
                    Longitudinal Trajectory ({subcorpComp.profile_a.label})
                  </h4>
                  <table className="table" style={{ width: '100%', fontSize: '12px' }}>
                    <thead>
                      <tr style={{ borderBottom: '2px solid var(--border)', textAlign: 'left' }}>
                        <th style={{ padding: '6px 10px' }}>Year</th>
                        <th style={{ padding: '6px 10px', textAlign: 'right' }}>Articles</th>
                        <th style={{ padding: '6px 10px', textAlign: 'right' }}>Net Sentiment</th>
                        <th style={{ padding: '6px 10px', textAlign: 'right' }}>Moral Framing Density</th>
                      </tr>
                    </thead>
                    <tbody>
                      {subcorpComp.profile_a.timeline.map((tp) => (
                        <tr key={tp.period} style={{ borderBottom: '1px solid var(--border)' }}>
                          <td style={{ padding: '6px 10px', fontWeight: 600 }}>{tp.period}</td>
                          <td style={{ padding: '6px 10px', textAlign: 'right' }}>{tp.count}</td>
                          <td style={{ padding: '6px 10px', textAlign: 'right', color: tp.sentiment >= 0 ? '#1f6f43' : '#a32a2a', fontWeight: 600 }}>
                            {tp.sentiment > 0 ? `+${tp.sentiment}` : tp.sentiment}
                          </td>
                          <td style={{ padding: '6px 10px', textAlign: 'right' }}>{tp.moral_density.toFixed(1)}/1k</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
