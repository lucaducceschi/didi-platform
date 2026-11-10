export interface SnippetPart {
  text: string
  match: boolean
}

export interface ArticleSummary {
  id: string
  source: string
  source_label: string
  source_type?: string
  language: string
  language_label: string
  url: string
  title: string
  publish_date: string
  author: string | null
  category: string | null
  word_count: number
  snippet: SnippetPart[]
}

export interface ExpansionTerm {
  term: string
  language?: string
  category: string
}

export interface QueryInterpretation {
  original_query: string
  normalized_query: string
  search_mode: 'exact' | 'word_family' | 'concept'
  effective_fts: string
  expansion_terms: ExpansionTerm[]
  expansion_language?: string | null
  expansion_category?: string | null
  warnings: string[]
  total_results: number
  active_filters: Record<string, unknown>
}

export interface SearchResponse {
  total: number
  page: number
  page_size: number
  results: ArticleSummary[]
  hidden_articles?: number
  query_interpretation?: QueryInterpretation | null
}

export interface ArticleDetail {
  id: string
  source: string
  source_label: string
  source_type?: string
  twin_article_id?: string | null
  language: string
  language_label: string
  url: string
  title: string
  publish_date: string
  author: string | null
  category: string | null
  word_count: number
  full_text: string
  metrics: {
    net_sentiment: number | null
    moral_density: number | null
    emotional_density: number | null
    readability_score?: number | null
    readability_metric?: string | null
    readability_grade?: string | null
    lix?: number | null
  }
}

export interface Facet {
  id: string
  label: string
  count: number
}

export interface CorpusSummary {
  total_articles: number
  total_words: number
  min_date: string
  max_date: string
  sources: Facet[]
  languages: Facet[]
  source_types?: Facet[]
}

export interface SearchFilters {
  q: string
  mode?: 'exact' | 'word_family' | 'concept'
  sources: string[]
  languages: string[]
  types?: string[]
  min_date?: string
  max_date?: string
  page: number
}

export interface ConcordanceLine {
  article_id: string
  title: string
  source: string
  source_label: string
  source_type: string
  language: string
  language_label: string
  publish_date: string
  start_char: number
  end_char: number
  left_context: string
  keyword: string
  right_context: string
}

export interface ConcordanceResponse {
  total_lines: number
  total_articles: number
  page: number
  page_size: number
  items: ConcordanceLine[]
}

export interface SearchDistribution {
  total: number
  by_language: Record<string, number>
  by_source: Record<string, number>
  by_source_type: Record<string, number>
  by_year: Record<string, number>
}

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export const UNAUTHORIZED_EVENT = 'didi:unauthorized'

async function request<T>(method: string, path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      method,
      signal,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'The server could not be reached. Check that the app is running.')
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const detail = typeof payload?.detail === 'string' ? payload.detail : 'Something went wrong on the server.'
    if (response.status === 401 && path !== '/api/auth/login') window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
    throw new ApiError(response.status, detail)
  }
  return (response.status === 204 ? undefined : await response.json()) as T
}

const getJson = <T,>(path: string, signal?: AbortSignal) => request<T>('GET', path, undefined, signal)

export function searchPath({ q, mode, sources, languages, types, min_date, max_date, page }: SearchFilters): string {
  const params = new URLSearchParams()
  if (q.trim()) params.set('q', q.trim())
  if (mode && mode !== 'concept') params.set('mode', mode)
  sources.forEach((source) => params.append('source', source))
  languages.forEach((language) => params.append('language', language))
  types?.forEach((type) => params.append('type', type))
  if (min_date) params.set('min_date', min_date)
  if (max_date) params.set('max_date', max_date)
  params.set('page', String(page))
  return `/api/articles/search?${params}`
}

export const searchArticles = (filters: SearchFilters, signal?: AbortSignal) =>
  getJson<SearchResponse>(searchPath(filters), signal)

export function concordancePath({ q, mode, sources, languages, types, min_date, max_date, page, page_size = 50 }: SearchFilters & { page_size?: number }): string {
  const params = new URLSearchParams()
  if (q.trim()) params.set('q', q.trim())
  if (mode) params.set('mode', mode)
  sources.forEach((source) => params.append('source', source))
  languages.forEach((language) => params.append('language', language))
  types?.forEach((type) => params.append('type', type))
  if (min_date) params.set('min_date', min_date)
  if (max_date) params.set('max_date', max_date)
  params.set('page', String(page))
  params.set('page_size', String(page_size))
  return `/api/articles/concordance?${params}`
}

export const getConcordance = (filters: SearchFilters & { page_size?: number }, signal?: AbortSignal) =>
  getJson<ConcordanceResponse>(concordancePath(filters), signal)

export function distributionPath({ q, mode, sources, languages, types, min_date, max_date }: Omit<SearchFilters, 'page'>): string {
  const params = new URLSearchParams()
  if (q.trim()) params.set('q', q.trim())
  if (mode) params.set('mode', mode)
  sources.forEach((source) => params.append('source', source))
  languages.forEach((language) => params.append('language', language))
  types?.forEach((type) => params.append('type', type))
  if (min_date) params.set('min_date', min_date)
  if (max_date) params.set('max_date', max_date)
  return `/api/articles/distribution?${params}`
}

export const getSearchDistribution = (filters: Omit<SearchFilters, 'page'>, signal?: AbortSignal) =>
  getJson<SearchDistribution>(distributionPath(filters), signal)

export const getArticle = (id: string, signal?: AbortSignal) =>
  getJson<ArticleDetail>(`/api/articles/${encodeURIComponent(id)}`, signal)

export const getCorpusSummary = (signal?: AbortSignal) => getJson<CorpusSummary>('/api/corpus/summary', signal)

export interface User {
  id: string
  username: string
  display_name: string
  is_admin: boolean
  active: boolean
}

export type UserBrief = Pick<User, 'id' | 'username' | 'display_name'>

export const getMe = (signal?: AbortSignal) => getJson<User>('/api/me', signal)
export const login = (username: string, password: string) => request<User>('POST', '/api/auth/login', { username, password })
export const logout = () => request<void>('POST', '/api/auth/logout')
export const changePassword = (current_password: string, new_password: string) =>
  request<void>('POST', '/api/me/password', { current_password, new_password })

export const listUsers = (signal?: AbortSignal) => getJson<User[]>('/api/users', signal)
export const getUserDirectory = (signal?: AbortSignal) => getJson<UserBrief[]>('/api/users/directory', signal)
export const createUser = (body: { username: string; display_name: string; password: string; is_admin: boolean }) =>
  request<User>('POST', '/api/users', body)
export const updateUser = (id: string, body: { display_name?: string; password?: string; active?: boolean; is_admin?: boolean }) =>
  request<User>('PATCH', `/api/users/${id}`, body)

export interface Project {
  id: string
  name: string
  description: string
  archived: boolean
  revision: number
  role: 'lead' | 'coder' | null
  can_manage: boolean
  can_edit_codebook: boolean
  member_count: number
  code_count: number
  article_count: number
  segment_count: number
}

export interface ProjectCreate {
  name: string
  description: string
  lead_user_id?: string
  codebook: { mode: 'empty' | 'starter' | 'copy'; source_project_id?: string }
}

export const listProjects = (signal?: AbortSignal) => getJson<Project[]>('/api/projects', signal)
export const getProject = (id: string, signal?: AbortSignal) => getJson<Project>(`/api/projects/${id}`, signal)
export const createProject = (body: ProjectCreate) => request<Project>('POST', '/api/projects', body)
export const updateProject = (id: string, body: { revision: number; name?: string; description?: string; archived?: boolean }) =>
  request<Project>('PATCH', `/api/projects/${id}`, body)

export interface Member {
  user: UserBrief
  role: 'lead' | 'coder'
  active: boolean
}

export const listMembers = (projectId: string, signal?: AbortSignal) => getJson<Member[]>(`/api/projects/${projectId}/members`, signal)
export const addMember = (projectId: string, user_id: string, role: Member['role']) =>
  request<Member>('POST', `/api/projects/${projectId}/members`, { user_id, role })
export const updateMember = (projectId: string, userId: string, role: Member['role']) =>
  request<Member>('PATCH', `/api/projects/${projectId}/members/${userId}`, { role })
export const removeMember = (projectId: string, userId: string) => request<void>('DELETE', `/api/projects/${projectId}/members/${userId}`)

export interface Code {
  id: string
  name: string
  parent_id: string | null
  definition: string
  color: string
  sort_order: number
  revision: number
  segment_count: number
  coder_count: number
}

export interface MergePreview {
  segments: number
  duplicates: number
  coders: number
  name_conflicts: string[]
}

export const listCodes = (projectId: string, signal?: AbortSignal) => getJson<Code[]>(`/api/projects/${projectId}/codes`, signal)
export const createCode = (projectId: string, body: { name: string; parent_id: string | null; definition: string }) =>
  request<Code>('POST', `/api/projects/${projectId}/codes`, body)
export const updateCode = (
  projectId: string,
  codeId: string,
  body: { revision: number; name?: string; parent_id?: string | null; definition?: string; color?: string },
) => request<Code>('PATCH', `/api/projects/${projectId}/codes/${codeId}`, body)
export const deleteCode = (projectId: string, code: Code) =>
  request<void>('DELETE', `/api/projects/${projectId}/codes/${code.id}?revision=${code.revision}`)
export const getMergePreview = (projectId: string, sourceId: string, targetId: string) =>
  getJson<MergePreview>(`/api/projects/${projectId}/codes/${sourceId}/merge-preview?into=${targetId}`)
export const mergeCodes = (projectId: string, source: Code, target: Code) =>
  request<Code>('POST', `/api/projects/${projectId}/codes/${source.id}/merge`, {
    target_id: target.id,
    source_revision: source.revision,
    target_revision: target.revision,
  })

export interface ActivityEntry {
  id: number
  occurred_at: string
  user: UserBrief | null
  action: string
  target: string
  details: Record<string, unknown>
}

export const listActivity = (projectId: string, signal?: AbortSignal) =>
  getJson<ActivityEntry[]>(`/api/projects/${projectId}/activity`, signal)

export interface SavedSelection {
  id: string
  project_id: string
  name: string
  description: string
  query_definition: Record<string, any>
  article_count: number
  created_by: string
  created_at: string
  updated_at: string
  user?: UserBrief
}

export interface SavedSelectionDetail extends SavedSelection {
  article_ids: string[]
}

export const listSelections = (projectId: string, signal?: AbortSignal) =>
  getJson<SavedSelection[]>(`/api/projects/${projectId}/selections`, signal)

export const getSelection = (projectId: string, selectionId: string, signal?: AbortSignal) =>
  getJson<SavedSelectionDetail>(`/api/projects/${projectId}/selections/${selectionId}`, signal)

export const createSelection = (
  projectId: string,
  body: { name: string; description?: string; query_definition?: Record<string, any>; article_ids?: string[] },
) => request<SavedSelection>('POST', `/api/projects/${projectId}/selections`, body)

export const deleteSelection = (projectId: string, selectionId: string) =>
  request<void>('DELETE', `/api/projects/${projectId}/selections/${selectionId}`)

export const refreshSelection = (projectId: string, selectionId: string) =>
  request<SavedSelectionDetail>('POST', `/api/projects/${projectId}/selections/${selectionId}/refresh`)

export interface KeynessTerm {
  term: string
  target_count: number
  ref_count: number
  target_per_1k: number
  ref_per_1k: number
  g2: number
  direction: string
}

export interface SelectionTimelinePoint {
  period: string
  count: number
  sentiment: number
  moral_density: number
}

export interface SelectionProfileData {
  id: string
  label: string
  article_count: number
  total_words: number
  dominant_language: string
  net_sentiment: number
  moral_density: number
  foundations: {
    care: number
    fairness: number
    loyalty: number
    authority: number
    sanctity: number
  }
  emotions: Record<string, number>
  readability: {
    score: number
    metric: string
    grade: string
  }
  nominal_ratio: number
  concreteness: number
  ingroup_pronouns_rate: number
  languages: Record<string, number>
  sources: Record<string, number>
  source_types: Record<string, number>
  timeline: SelectionTimelinePoint[]
}

export interface SelectionCompareResponse {
  comparison_type: 'selection_vs_selection' | 'selection_vs_baseline' | 'partition'
  partition_label: string | null
  profile_a: SelectionProfileData
  profile_b: SelectionProfileData
  divergence: {
    mfdi: number
    moral_divergence: any
    emotion_jsd: number
    emotion_divergence: any
  }
  distinctive_terms_a: KeynessTerm[]
  distinctive_terms_b: KeynessTerm[]
}

export const compareSelections = (
  projectId: string,
  body: {
    selection_a_id: string
    selection_b_id?: string | null
    partition_by?: string | null
  },
  signal?: AbortSignal
) => request<SelectionCompareResponse>('POST', `/api/projects/${projectId}/selections/compare`, body, signal)

export interface CoderPairAgreement {
  coder_1: UserBrief
  coder_2: UserBrief
  overlapping_segments: number
  agreed_segments: number
  observed_agreement: number
  chance_agreement: number
  cohens_kappa: number
  interpretation: string
}

export interface CodeConfusionItem {
  code_1: { id: string; name: string; color: string }
  code_2: { id: string; name: string; color: string }
  count: number
}

export interface DisagreementItem {
  article_id: string
  start_pos: number
  end_pos: number
  quote: string
  coder_1: string
  code_1_name: string
  code_1_color: string
  coder_2: string
  code_2_name: string
  code_2_color: string
  iou: number
}

export interface InterCoderAgreementResponse {
  total_coders: number
  total_overlapping_segments: number
  total_agreed_segments: number
  global_observed_agreement: number
  global_kappa: number
  global_interpretation: string
  pairs: CoderPairAgreement[]
  confusion_matrix: CodeConfusionItem[]
  disagreements: DisagreementItem[]
}

export const getInterCoderAgreement = (projectId: string, signal?: AbortSignal) =>
  getJson<InterCoderAgreementResponse>(`/api/projects/${projectId}/codes/inter-coder-agreement`, signal)

export interface LibraryCoder {
  user: UserBrief
  status: 'in_progress' | 'done' | null
  segments: number
  stale_segments: number
}

export type MyStatus = 'not_started' | 'in_progress' | 'done'

export interface LibraryArticle {
  id: string
  in_corpus: boolean
  title: string
  source_label: string | null
  source_type?: string | null
  language_label: string | null
  publish_date: string | null
  word_count: number | null
  my_status: MyStatus
  coders: LibraryCoder[]
}

export interface LibraryResponse {
  project_total: number
  unstarted_total: number
  total: number
  page: number
  page_size: number
  results: LibraryArticle[]
  languages: Facet[]
  sources: Facet[]
  source_types: Facet[]
  hidden_articles?: number
}

export interface LibraryFilters {
  languages: string[]
  sources: string[]
  types: string[]
  status: MyStatus | ''
  page: number
}

export function libraryPath(projectId: string, { languages, sources, types, status, page }: LibraryFilters): string {
  const params = new URLSearchParams()
  languages.forEach((language) => params.append('language', language))
  sources.forEach((source) => params.append('source', source))
  types.forEach((type) => params.append('type', type))
  if (status) params.set('status', status)
  params.set('page', String(page))
  return `/api/projects/${projectId}/library?${params}`
}

export const getLibrary = (projectId: string, filters: LibraryFilters, signal?: AbortSignal) =>
  getJson<LibraryResponse>(libraryPath(projectId, filters), signal)

export interface ProjectSearchResult {
  id: string
  title: string
  source_label: string
  source_type?: string
  language_label: string
  publish_date: string
  word_count: number
  snippet: SnippetPart[]
  in_project: boolean
}

export interface ProjectSearchResponse {
  total: number
  in_project_total: number
  page: number
  page_size: number
  results: ProjectSearchResult[]
  hidden_articles?: number
}

export const searchForProject = (projectId: string, filters: SearchFilters, signal?: AbortSignal) =>
  getJson<ProjectSearchResponse>(searchPath(filters).replace('/api/articles/search', `/api/projects/${projectId}/article-search`), signal)

export interface ArticlesAdded {
  added: number
  already_present: number
}

export interface ArticleProject {
  id: string
  name: string
  archived: boolean
  role: 'lead' | 'coder'
  in_project: boolean
}

export const getArticleProjects = (articleId: string, signal?: AbortSignal) =>
  getJson<ArticleProject[]>(`/api/articles/${encodeURIComponent(articleId)}/projects`, signal)
export const addArticles = (projectId: string, article_ids: string[]) =>
  request<ArticlesAdded>('POST', `/api/projects/${projectId}/articles`, { article_ids })
export const addArticlesFromSearch = (projectId: string, body: { q: string; source: string[]; language: string[]; type?: string[] }) =>
  request<ArticlesAdded>('POST', `/api/projects/${projectId}/articles/from-search`, body)

export const removeArticle = (projectId: string, articleId: string) =>
  request<void>('DELETE', `/api/projects/${projectId}/articles/${encodeURIComponent(articleId)}`)
export const removeUnstartedArticles = (projectId: string) =>
  request<{ removed: number }>('POST', `/api/projects/${projectId}/articles/remove-unstarted`)

export interface Passage {
  id: string
  article_id: string
  in_corpus: boolean
  article_title: string
  publish_date: string | null
  source_label: string | null
  source_type?: string | null
  language: string | null
  language_label: string | null
  code_id: string
  code_path: string
  code_color: string
  user: UserBrief
  quote: string
  memo: string
  status: 'active' | 'stale'
  before: string
  after: string
}

export interface PassagesResponse {
  project_total: number
  total: number
  page: number
  page_size: number
  results: Passage[]
  codes: { id: string; direct: number; total: number }[]
  languages: { id: string; label: string; count: number }[]
  sources: { id: string; label: string; count: number }[]
  source_types: { id: string; label: string; count: number }[]
  coders: { user: UserBrief; count: number }[]
  hidden_passages?: number
}

export const getPassages = (projectId: string, query: URLSearchParams, signal?: AbortSignal) =>
  getJson<PassagesResponse>(`/api/projects/${projectId}/passages?${query}`, signal)
export const passagesCsvPath = (projectId: string, query: URLSearchParams) => `/api/projects/${projectId}/passages.csv?${query}`

export const getProjectArticle = (projectId: string, articleId: string, signal?: AbortSignal) =>
  getJson<ArticleDetail>(`/api/projects/${projectId}/articles/${encodeURIComponent(articleId)}`, signal)

export interface DictionarySpan {
  start: number
  end: number
  form: string
  lemma: string
  kind: 'moral' | 'ingroup' | 'konjunktiv_i'
  category?: string
  label: string
  color: string
}

export const getArticleDictionarySpans = (projectId: string, articleId: string, signal?: AbortSignal) =>
  getJson<DictionarySpan[]>(`/api/projects/${projectId}/articles/${encodeURIComponent(articleId)}/dictionary-spans`, signal)

export interface Annotation {
  id: string
  article_id: string
  code_id: string
  user: UserBrief
  start_pos: number
  end_pos: number
  quote: string
  memo: string
  status: 'active' | 'stale'
  revision: number
  created_at: string
  updated_at: string
  created?: boolean | null
  merged_from?: string | null
}

export const listAnnotations = (projectId: string, articleId: string, scope: 'mine' | 'all', signal?: AbortSignal) =>
  getJson<Annotation[]>(`/api/projects/${projectId}/articles/${encodeURIComponent(articleId)}/annotations?scope=${scope}`, signal)

export const createAnnotation = (projectId: string, articleId: string, body: { start: number; end: number; code_id: string; memo: string }) =>
  request<Annotation>('POST', `/api/projects/${projectId}/articles/${encodeURIComponent(articleId)}/annotations`, body)
export const updateAnnotation = (projectId: string, id: string, body: { revision: number; code_id?: string; memo?: string }) =>
  request<Annotation>('PATCH', `/api/projects/${projectId}/annotations/${id}`, body)
export const deleteAnnotation = (projectId: string, annotation: Annotation) =>
  request<void>('DELETE', `/api/projects/${projectId}/annotations/${annotation.id}?revision=${annotation.revision}`)

export const getProgress = (projectId: string, articleId: string, signal?: AbortSignal) =>
  getJson<{ status: MyStatus }>(`/api/projects/${projectId}/articles/${encodeURIComponent(articleId)}/progress`, signal)
export const setProgress = (projectId: string, articleId: string, status: 'in_progress' | 'done') =>
  request<{ status: MyStatus }>('PUT', `/api/projects/${projectId}/articles/${encodeURIComponent(articleId)}/progress`, { status })

const presencePath = (projectId: string, articleId: string) => `/api/projects/${projectId}/articles/${encodeURIComponent(articleId)}/presence`
// A check-in waits for any leave still on its way. Otherwise the leave can arrive second and erase the
// person who just checked in, as when reopening an article or under React's double effects in development.
let pendingLeave: Promise<unknown> = Promise.resolve()

export const sendHeartbeat = (projectId: string, articleId: string, signal?: AbortSignal) =>
  pendingLeave.then(() => request<{ others: UserBrief[] }>('POST', presencePath(projectId, articleId), undefined, signal))
/** Uses keepalive, so it still gets through while a tab is closing. */
export const leaveArticle = (projectId: string, articleId: string) => {
  pendingLeave = fetch(presencePath(projectId, articleId), { method: 'DELETE', keepalive: true }).catch(() => {})
}

export interface DistinctiveLemma {
  lemma: string
  target_count: number
  reference_count: number
  g2: number
}

export interface CodeMetrics {
  code_id: string
  code_name: string
  code_color: string
  passage_count: number
  word_count: number
  small_sample: boolean
  dominant_language: string
  sentiment: number
  moral_density: number
  top_moral_foundation: string
  readability: {
    metric: string
    score: number
    grade: string
    lix: number
  } | null
  concreteness: {
    score: number
    label: string
    abstract_density: number
    entity_density: number
  } | null
  complexity: {
    nominal_ratio: number
    style_label: string
    guiraud_richness: number
    subordination_density: number
  } | null
  ingroup_pronouns: {
    count: number
    rate_per_1k: number
  }
  konjunktiv_i: {
    count: number
    rate_per_1k: number
    unvalidated: boolean
    available: boolean
  }
  distinctive_lemmas?: DistinctiveLemma[]
}

export interface ProjectAnalysisSummary {
  project_id: string
  project_name: string
  summary: {
    total_articles: number
    total_words: number
    total_passages: number
    total_coders: number
    total_coded_words: number
    languages: Record<string, number>
    source_types: Record<string, number>
    sources: Record<string, number>
  }
  baseline: Record<string, unknown>
  codes: CodeMetrics[]
}

export const getProjectAnalysis = (projectId: string, signal?: AbortSignal) =>
  getJson<ProjectAnalysisSummary>(`/api/projects/${projectId}/analysis`, signal)

export interface RadarLanguageData {
  language: string
  language_label: string
  article_count: number
  net_sentiment: number
  moral_density: number
  foundations: {
    care: number
    fairness: number
    loyalty: number
    authority: number
    sanctity: number
  }
  emotions: {
    anger: number
    anticipation: number
    disgust: number
    fear: number
    joy: number
    sadness: number
    surprise: number
    trust: number
  }
}

export interface PairwiseJsd {
  jsd: number
  primary_divergence_foundation: string
  norm_vec_a?: Record<string, number>
  norm_vec_b?: Record<string, number>
  deltas?: Record<string, number>
}

export interface RadarAnalyticsResponse {
  languages: RadarLanguageData[]
  pairwise_jsd: Record<string, PairwiseJsd>
}

export interface TimelinePoint {
  period: string
  language: string
  article_count: number
  avg_sentiment: number
  avg_moral_density: number
  avg_word_count: number
}

export interface TimelineAnalyticsResponse {
  series: TimelinePoint[]
}

export interface FocusEventItem {
  id: string
  date: string
  title: string
  description: string
  category: string
  default_window: number
  coverage: Record<string, number>
}

export interface KeynessItem {
  term: string
  g2: number
  target_per_1k: number
  ref_per_1k: number
}

export interface ArticleMetricsDetail {
  id: string
  title: string
  publish_date: string
  source: string
  source_label: string
  source_type: string
  source_type_label: string
  language: string
  language_label: string
  word_count: number
  net_sentiment: number
  moral_density: number
  top_moral_foundation: string
  readability_metric: string | null
  readability_score: number | null
  readability_grade: string | null
  nominal_ratio: number
  concreteness_score: number
}

export interface ProjectProfileData {
  article_count: number
  total_words: number
  dominant_language: string
  net_sentiment: number
  moral_density: number
  foundations: {
    care: number
    fairness: number
    loyalty: number
    authority: number
    sanctity: number
  }
  emotions: Record<string, number>
  readability: {
    score: number
    metric: string
    grade: string
  }
  nominal_ratio: number
  concreteness: number
  languages: Record<string, number>
  source_types: Record<string, number>
  sources: Record<string, number>
}

export interface CorpusBaselineData {
  article_count: number
  language: string
  net_sentiment: number
  moral_density: number
  foundations: {
    care: number
    fairness: number
    loyalty: number
    authority: number
    sanctity: number
  }
  emotions: Record<string, number>
  readability: {
    score: number
    metric: string
  }
  nominal_ratio: number
  concreteness: number
}

export interface ProjectCorpusComparisonResponse {
  project_id: string
  project_name: string
  article_count: number
  total_words: number
  project_profile: ProjectProfileData | null
  corpus_baseline: CorpusBaselineData | null
  divergence: {
    jsd: number
    label: string
    primary_divergence_foundation: string
  } | null
  distinctive_terms: KeynessItem[]
  articles: ArticleMetricsDetail[]
}

export const getProjectCorpusComparison = (projectId: string, signal?: AbortSignal) =>
  getJson<ProjectCorpusComparisonResponse>(`/api/projects/${projectId}/corpus-comparison`, signal)

export interface GridRow {
  id: string
  label: string
  total_passages: number
  total_articles: number
}

export interface GridColumn {
  id: string
  name: string
  color: string
  total_passages: number
}

export interface ExampleQuote {
  annotation_id: string
  article_id: string
  article_title: string
  publish_date: string
  quote: string
}

export interface GridCell {
  passage_count: number
  article_count: number
  coder_count: number
  measure_value: number | null
  measure_label: string
  word_count: number
  small_sample: boolean
  distinctive_lemmas: string[]
  example_quotes: ExampleQuote[]
}

export interface ComparisonGridResponse {
  project_id: string
  project_name: string
  row_by: string
  measure: string
  rows: GridRow[]
  columns: GridColumn[]
  cells: Record<string, GridCell>
}

export const getProjectComparisonGrid = (
  projectId: string,
  rowBy = 'language',
  measure = 'count',
  signal?: AbortSignal
) =>
  getJson<ComparisonGridResponse>(
    `/api/projects/${projectId}/comparison-grid?row_by=${encodeURIComponent(rowBy)}&measure=${encodeURIComponent(measure)}`,
    signal
  )

export interface FocusEventDetails {
  event_date: string
  window_days: number
  pre_period: string
  post_period: string
  pre_count: number
  post_count: number
  pct_surge: number
  pre_sentiment: number
  post_sentiment: number
  delta_sentiment: number
  moral_divergence: PairwiseJsd
  pre_moral: Record<string, number>
  post_moral: Record<string, number>
  keyness: KeynessItem[]
}

export interface AnalyticsFilters {
  q?: string
  sources?: string[]
  languages?: string[]
  min_date?: string
  max_date?: string
}

function buildAnalyticsParams({ q, sources, languages, min_date, max_date }: AnalyticsFilters = {}): string {
  const params = new URLSearchParams()
  if (q) params.set('q', q)
  if (sources) sources.forEach((s) => params.append('source', s))
  if (languages) languages.forEach((l) => params.append('language', l))
  if (min_date) params.set('min_date', min_date)
  if (max_date) params.set('max_date', max_date)
  const qs = params.toString()
  return qs ? `?${qs}` : ''
}

export const getRadarAnalytics = (filters?: AnalyticsFilters, signal?: AbortSignal) =>
  getJson<RadarAnalyticsResponse>(`/api/analytics/radar${buildAnalyticsParams(filters)}`, signal)

export const getTimelineAnalytics = (filters?: AnalyticsFilters, signal?: AbortSignal) =>
  getJson<TimelineAnalyticsResponse>(`/api/analytics/timeline${buildAnalyticsParams(filters)}`, signal)

export const getFocusEvents = (signal?: AbortSignal) =>
  getJson<FocusEventItem[]>('/api/analytics/focus-events', signal)

export const getFocusEventDetails = (eventDate: string, windowDays = 30, q = '', signal?: AbortSignal) => {
  const params = new URLSearchParams({ window_days: String(windowDays) })
  if (q) params.set('q', q)
  return getJson<FocusEventDetails>(`/api/analytics/focus-events/${encodeURIComponent(eventDate)}?${params}`, signal)
}

export const getCrossLingualKeyness = (
  targetLang = 'de',
  refLang = 'it',
  q = '',
  sources?: string[],
  topN = 15,
  signal?: AbortSignal
) => {
  const params = new URLSearchParams({ target_lang: targetLang, ref_lang: refLang, top_n: String(topN) })
  if (q) params.set('q', q)
  if (sources) sources.forEach((s) => params.append('source', s))
  return getJson<KeynessItem[]>(`/api/analytics/keyness?${params}`, signal)
}

export interface WordBubbleItem {
  id: string
  term: string
  twin_term: string | null
  category: string
  category_color: string
  count: number
  salience: number
  de_ratio: number
  it_ratio: number
  journalism_ratio: number
  official_press_ratio: number
  primary_moral: string
  sentiment: number
  collocates: string[]
  sample_snippet: string
  years: string[]
  yearly_trend: number[]
}

export const getWordBubbles = (mode = 'focus', signal?: AbortSignal) =>
  getJson<WordBubbleItem[]>(`/api/analytics/word-bubbles?mode=${encodeURIComponent(mode)}`, signal)


// Light LDA topic models (backend/app/routers/topics.py)
export interface Topic {
  topic_id: number
  /** Share of all words in the model's corpus (LDAvis topic size). */
  word_share: number
  dominant_articles: number
  /** Most probable terms (lambda = 1). */
  top_terms: string[]
  /** Terms by LDAvis relevance at the default lambda (0.6). */
  relevant_terms: string[]
}

export interface TopicTermItem {
  term: string
  relevance: number
  p_term_topic: number
  topic_count: number
  corpus_count: number
}

export interface TopicTermsResponse {
  model_id: string
  topic_id: number
  lambda: number
  word_share: number
  terms: TopicTermItem[]
  closest: { topic_id: number; jsd: number }[]
}

export interface TopicModel {
  model_id: string
  method: string
  language: string
  n_topics: number
  n_documents: number
  vocabulary_size: number
  created_at: string
  topics: Topic[]
}

export interface TopicArticle {
  id: string
  weight: number
  title: string
  source: string
  source_type: string
  language: string
  publish_date: string
}

export interface TopicArticlesResponse {
  model_id: string
  topic_id: number
  min_weight: number
  total: number
  article_ids: string[]
  articles: TopicArticle[]
}

export const listTopicModels = (signal?: AbortSignal) =>
  getJson<{ models: TopicModel[] }>('/api/topics/models', signal)

export const getTopicTerms = (modelId: string, topicId: number, lambda: number, signal?: AbortSignal) =>
  getJson<TopicTermsResponse>(
    `/api/topics/models/${encodeURIComponent(modelId)}/topics/${topicId}/terms?lambda=${lambda}&n=30`,
    signal,
  )

export const getTopicArticles = (
  modelId: string,
  topicId: number,
  params: { min_weight: number; source_type?: string },
  signal?: AbortSignal,
) => {
  const query = new URLSearchParams({ min_weight: String(params.min_weight) })
  if (params.source_type) query.set('source_type', params.source_type)
  return getJson<TopicArticlesResponse>(
    `/api/topics/models/${encodeURIComponent(modelId)}/topics/${topicId}/articles?${query}`,
    signal,
  )
}

export interface TopicTimelinePoint {
  period: string
  share: number
  articles: number
  words: number
  small_sample: boolean
}

export interface TopicTimelineSeries {
  source_type: string
  points: TopicTimelinePoint[]
}

export interface TopicTimelineResponse {
  model_id: string
  topic_id: number
  granularity: 'year' | 'month'
  small_sample_articles: number
  series: TopicTimelineSeries[]
}

export const getTopicTimeline = (
  modelId: string,
  topicId: number,
  granularity: 'year' | 'month',
  signal?: AbortSignal,
) =>
  getJson<TopicTimelineResponse>(
    `/api/topics/models/${encodeURIComponent(modelId)}/topics/${topicId}/timeline?granularity=${granularity}`,
    signal,
  )
