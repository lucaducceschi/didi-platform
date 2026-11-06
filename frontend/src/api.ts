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

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, { signal })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'The server could not be reached. Check that the app is running.')
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = typeof body?.detail === 'string' ? body.detail : 'Something went wrong on the server.'
    throw new ApiError(response.status, detail)
  }
  return response.json() as Promise<T>
}

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
