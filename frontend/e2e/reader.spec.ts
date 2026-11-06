import { execFileSync } from 'node:child_process'
import { type APIRequestContext, type Page, expect, test } from '@playwright/test'
import { ADMIN, failOnThirdPartyRequests, logIn, PASSWORD } from './helpers'

test.describe.configure({ mode: 'serial' })

const REAL_ARTICLES: Record<string, string> = JSON.parse(execFileSync('../.venv/bin/python', ['../scripts/e2e_find_articles.py'], { encoding: 'utf-8' }))
const ALL_IDS = Object.values(REAL_ARTICLES)

let projectId = ''
let codes: { id: string; name: string; color: string }[] = []

// oxlint-disable-next-line typescript/no-explicit-any -- test data, shaped by the API
async function json(response: Awaited<ReturnType<APIRequestContext['get']>>): Promise<any> {
  expect(response.ok(), await response.text()).toBe(true)
  return response.json()
}

async function apiAs(playwright: { request: { newContext: (options: object) => Promise<APIRequestContext> } }, baseURL: string, username: string, password = PASSWORD) {
  const context = await playwright.request.newContext({ baseURL })
  await json(await context.post('/api/auth/login', { data: { username, password } }))
  return context
}

/** The visible text of one segment, which may be split across several spans by overlaps. */
async function highlightText(page: Page, segmentId: string) {
  return page.locator(`[data-segments~="${segmentId}"]`).evaluateAll((spans) => spans.map((span) => span.textContent).join(''))
}

test('set up a project, coders and overlapping segments', async ({ playwright, baseURL }) => {
  const admin = await apiAs(playwright, baseURL!, ADMIN.username, ADMIN.password)
  const users: Record<string, string> = {}
  for (const [username, display_name] of [['rita', 'Rita Reader'], ['otto', 'Otto Other'], ['nina', 'Nina Nonmember']]) {
    const user = await json(await admin.post('/api/users', { data: { username, display_name, password: PASSWORD } }))
    users[username] = user.id
  }
  const project = await json(await admin.post('/api/projects', { data: { name: 'Reader study', lead_user_id: users.rita, codebook: { mode: 'empty' } } }))
  projectId = project.id
  await json(await admin.post(`/api/projects/${projectId}/members`, { data: { user_id: users.otto, role: 'coder' } }))
  await json(await admin.post('/api/projects', { data: { name: 'Separate study', lead_user_id: users.nina, codebook: { mode: 'empty' } } }))

  const rita = await apiAs(playwright, baseURL!, 'rita')
  const otto = await apiAs(playwright, baseURL!, 'otto')
  await json(await rita.post(`/api/projects/${projectId}/articles`, { data: { article_ids: ALL_IDS } }))
  codes = [
    await json(await rita.post(`/api/projects/${projectId}/codes`, { data: { name: 'Autonomy' } })),
    await json(await rita.post(`/api/projects/${projectId}/codes`, { data: { name: 'Rights' } })),
  ]

  for (const id of ALL_IDS) {
    const url = `/api/projects/${projectId}/articles/${encodeURIComponent(id)}/annotations`
    await json(await rita.post(url, { data: { start: 10, end: 40, code_id: codes[0].id, memo: 'First reading' } }))
    await json(await rita.post(url, { data: { start: 25, end: 60, code_id: codes[1].id } }))
    await json(await otto.post(url, { data: { start: 30, end: 80, code_id: codes[0].id } }))
  }
})

for (const [kind, articleId] of Object.entries(REAL_ARTICLES)) {
  test(`${kind} article: text and every highlight are exact`, async ({ page, baseURL, request }) => {
    failOnThirdPartyRequests(page, baseURL!)
    await logIn(page, 'rita')
    await page.goto(`/projects/${projectId}/articles/${encodeURIComponent(articleId)}`)
    await request.post('/api/auth/login', { data: { username: 'rita', password: PASSWORD } })
    const article = await json(await request.get(`/api/articles/${encodeURIComponent(articleId)}`))
    const reader = page.getByTestId('article-text')
    await expect(reader).toBeVisible()
    await page.getByRole('button', { name: 'All coders' }).click()
    const segments = await json(await request.get(`/api/projects/${projectId}/articles/${encodeURIComponent(articleId)}/annotations?scope=all`))
    expect(segments).toHaveLength(3)
    await expect(page.locator('[data-segments]').first()).toBeVisible()
    await expect(page.locator('.hl-other').first()).toBeVisible()

    expect(await reader.evaluate((element) => element.textContent)).toBe(article.full_text)
    const codePoints = Array.from(article.full_text as string)
    for (const segment of segments) {
      expect(await highlightText(page, segment.id)).toBe(segment.quote)
      expect(codePoints.slice(segment.start_pos, segment.end_pos).join('')).toBe(segment.quote)
    }
  })
}

test('Mine shows only your segments by default, and All coders shows both', async ({ page }) => {
  await logIn(page, 'otto')
  await page.goto(`/projects/${projectId}/articles/${encodeURIComponent(REAL_ARTICLES.german)}`)
  await expect(page.locator('.hl-mine').first()).toBeVisible()
  await expect(page.locator('.hl-other')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Mine' })).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: 'All coders' }).click()
  await expect(page.locator('.hl-other').first()).toBeVisible()
  await expect(page.locator('.hl-overlap').first()).toBeVisible()
  await expect(page.locator('.segment-by', { hasText: 'Rita Reader' }).first()).toBeVisible()
})

test('clicking a highlight shows its details and offers no editing', async ({ page }) => {
  await logIn(page, 'otto')
  await page.goto(`/projects/${projectId}/articles/${encodeURIComponent(REAL_ARTICLES.italian)}`)
  await page.getByRole('button', { name: 'All coders' }).click()
  await page.locator('.hl-overlap').first().click()
  const panel = page.locator('.panel', { hasText: 'segments' })
  await expect(panel.getByText('Rita Reader').first()).toBeVisible()
  await expect(panel.getByText('First reading')).toBeVisible()
  await expect(panel.getByRole('button', { name: /edit|delete/i })).toHaveCount(0)
  await page.locator('.segment-item').first().click()
  await expect(page.locator('.hl-selected').first()).toBeVisible()
})

test('synthetic hard text: CRLF stays exact and markup is literal, with nothing executed', async ({ page }) => {
  const text = "Line one\r\nLine two\r\n\r\n<script>window.__pwned = true</script> <b>bold</b> <img src=x onerror=\"window.__pwned=true\"> *stars* end"
  await logIn(page, 'rita')
  await page.route(`**/api/projects/${projectId}/articles/synthetic`, (route) => route.fulfill({
    json: {
      id: 'synthetic', source: 'salto', source_label: 'Salto.bz', language: 'de', language_label: 'German (de)', url: 'https://example.org/',
      title: '<b>Synthetic</b>', publish_date: '2025-01-01T00:00:00', author: 'A', category: null, word_count: 10, full_text: text, metrics: {}, metadata: {},
    },
  }))
  await page.route(`**/api/projects/${projectId}/articles/synthetic/annotations*`, (route) => route.fulfill({
    json: [{
      id: 'seg', article_id: 'synthetic', code_id: codes[0].id, user: { id: 'x', username: 'rita', display_name: 'Rita Reader' },
      start_pos: 22, end_pos: 60, quote: text.slice(22, 60), memo: '', status: 'active', revision: 1, created_at: '2025-01-01T00:00:00Z', updated_at: '2025-01-01T00:00:00Z',
    }],
  }))
  await page.goto(`/projects/${projectId}/articles/synthetic`)
  const reader = page.getByTestId('article-text')
  await expect(reader).toBeVisible()
  expect(await reader.evaluate((element) => element.textContent)).toBe(text)
  expect(await reader.locator('script, b, img').count()).toBe(0)
  expect(await page.evaluate(() => (window as unknown as { __pwned?: boolean }).__pwned)).toBeUndefined()
  await expect(page.getByRole('heading', { name: '<b>Synthetic</b>' })).toBeVisible()
  expect(await highlightText(page, 'seg')).toBe(text.slice(22, 60))
})

test('the library shows counts per coder and filters by variety', async ({ page }) => {
  await logIn(page, 'rita')
  await page.getByRole('link', { name: 'Reader study' }).click()
  await expect(page).toHaveURL(/\/articles$/)
  await expect(page.locator('.library-list li').first()).toBeVisible()
  const chips = page.locator('.coder-chip')
  await expect(chips.filter({ hasText: 'Rita Reader · 2 segments' }).first()).toBeVisible()
  await expect(chips.filter({ hasText: 'Otto Other · 1 segment' }).first()).toBeVisible()
  await page.getByLabel('Variety').selectOption({ value: 'it' })
  await expect(page.getByText(/hidden by these filters/)).toBeVisible()
  await expect(page.locator('.library-list li')).not.toHaveCount(0)
  await page.getByLabel('My status').selectOption({ value: 'done' })
  await expect(page.getByText('No articles match these filters.')).toBeVisible()
})

test('a lead adds selected articles and all matches, seeing the count first', async ({ page }) => {
  await logIn(page, 'nina')
  await page.getByRole('link', { name: 'Separate study' }).click()
  await expect(page.getByText('This project has no articles yet')).toBeVisible()
  await page.getByRole('link', { name: 'Add articles' }).click()
  await page.getByLabel('Search the corpus').fill('Autonomie')
  await page.getByRole('button', { name: 'Search', exact: true }).click()
  await page.locator('.pick-row input').first().check()
  await page.getByRole('button', { name: 'Add selected (1)' }).click()
  await expect(page.getByRole('status')).toContainText('Added 1 article')
  await expect(page.locator('.pick-row .tag').first()).toBeVisible()

  await page.getByRole('button', { name: 'Add all new matches…' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByRole('heading')).toContainText(/Add [\d,]+ articles\?/)
  await dialog.getByRole('button', { name: /Add [\d,]+ articles/ }).click()
  await expect(page.getByRole('status')).toContainText('already in the project')
  await page.getByRole('link', { name: 'Back to articles' }).click()
  await expect(page.locator('.library-list li').first()).toBeVisible()
})

test('non-members and coders are refused', async ({ page, playwright, baseURL }) => {
  const nina = await apiAs(playwright, baseURL!, 'nina')
  expect((await nina.get(`/api/projects/${projectId}/library`)).status()).toBe(404)
  await logIn(page, 'nina')
  await page.goto(`/projects/${projectId}/articles`)
  await expect(page.getByRole('alert')).toContainText("aren't a member")

  const otto = await apiAs(playwright, baseURL!, 'otto')
  expect((await otto.post(`/api/projects/${projectId}/articles/from-search`, { data: { q: 'autonomia' } })).status()).toBe(403)
  await page.getByRole('button', { name: 'Log out' }).click()
  await logIn(page, 'otto')
  await page.goto(`/projects/${projectId}/articles`)
  await expect(page.locator('.library-list li').first()).toBeVisible()
  await expect(page.getByRole('link', { name: 'Add articles' })).toHaveCount(0)
  await page.goto(`/projects/${projectId}/articles/add`)
  await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/articles$`))
})
