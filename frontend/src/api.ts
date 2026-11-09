export interface SnippetPart {
  text: string
  match: boolean
}

export interface ArticleSummary {
  id: string
  source: string
  source_label: string
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

export interface SearchResponse {
  total: number
  page: number
  page_size: number
  results: ArticleSummary[]
  hidden_articles?: number
}

export interface ArticleDetail {
  id: string
  source: string
  source_label: string
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
}

export interface SearchFilters {
  q: string
  sources: string[]
  languages: string[]
  page: number
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

export function searchPath({ q, sources, languages, page }: SearchFilters): string {
  const params = new URLSearchParams()
  if (q.trim()) params.set('q', q.trim())
  sources.forEach((source) => params.append('source', source))
  languages.forEach((language) => params.append('language', language))
  params.set('page', String(page))
  return `/api/articles/search?${params}`
}

export const searchArticles = (filters: SearchFilters, signal?: AbortSignal) =>
  getJson<SearchResponse>(searchPath(filters), signal)

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
  hidden_articles?: number
}

export interface LibraryFilters {
  languages: string[]
  sources: string[]
  status: MyStatus | ''
  page: number
}

export function libraryPath(projectId: string, { languages, sources, status, page }: LibraryFilters): string {
  const params = new URLSearchParams()
  languages.forEach((language) => params.append('language', language))
  sources.forEach((source) => params.append('source', source))
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
export const addArticlesFromSearch = (projectId: string, body: { q: string; source: string[]; language: string[] }) =>
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
  coders: { user: UserBrief; count: number }[]
  hidden_passages?: number
}

export const getPassages = (projectId: string, query: URLSearchParams, signal?: AbortSignal) =>
  getJson<PassagesResponse>(`/api/projects/${projectId}/passages?${query}`, signal)
export const passagesCsvPath = (projectId: string, query: URLSearchParams) => `/api/projects/${projectId}/passages.csv?${query}`

export const getProjectArticle = (projectId: string, articleId: string, signal?: AbortSignal) =>
  getJson<ArticleDetail>(`/api/projects/${projectId}/articles/${encodeURIComponent(articleId)}`, signal)

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
