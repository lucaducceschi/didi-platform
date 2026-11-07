import { type APIRequestContext, type Page, expect, test } from '@playwright/test'
import { ADMIN, failOnThirdPartyRequests, logIn, PASSWORD } from './helpers'

test.describe.configure({ mode: 'serial' })

let projectId = ''
const articles: Record<string, { id: string; title: string; text: string }> = {}
let oskarSegment = ''
const codes: Record<string, string> = {}

async function apiAs(playwright: { request: { newContext: (options: object) => Promise<APIRequestContext> } }, baseURL: string, username: string, password = PASSWORD) {
  const context = await playwright.request.newContext({ baseURL })
  expect((await context.post('/api/auth/login', { data: { username, password } })).ok()).toBe(true)
  return context
}

// oxlint-disable-next-line typescript/no-explicit-any -- test data, shaped by the API
async function json(response: Awaited<ReturnType<APIRequestContext['get']>>): Promise<any> {
  expect(response.ok(), await response.text()).toBe(true)
  return response.json()
}

const open = async (page: Page, baseURL: string, username: string) => {
  failOnThirdPartyRequests(page, baseURL)
  await logIn(page, username)
  await page.goto(`/projects/${projectId}/passages`)
}
const cards = (page: Page) => page.locator('.passage-list > li')

test('set up two coders with passages in two varieties', async ({ playwright, baseURL }) => {
  const admin = await apiAs(playwright, baseURL!, ADMIN.username, ADMIN.password)
  const ids: Record<string, string> = {}
  for (const username of ['pia', 'oskar']) ids[username] = (await json(await admin.post('/api/users', { data: { username, display_name: username, password: PASSWORD } }))).id
  projectId = (await json(await admin.post('/api/projects', { data: { name: 'Passages study', lead_user_id: ids.pia, codebook: { mode: 'empty' } } }))).id
  await json(await admin.post(`/api/projects/${projectId}/members`, { data: { user_id: ids.oskar, role: 'coder' } }))

  for (const language of ['de', 'lld_gherd', 'it']) {
    const found = (await json(await admin.get(`/api/articles/search?q=&language=${language}&page_size=1`))).results[0]
    const full = await json(await admin.get(`/api/articles/${encodeURIComponent(found.id)}`))
    articles[language] = { id: found.id, title: found.title, text: full.full_text }
  }
  const pia = await apiAs(playwright, baseURL!, 'pia')
  const oskar = await apiAs(playwright, baseURL!, 'oskar')
  await json(await pia.post(`/api/projects/${projectId}/articles`, { data: { article_ids: Object.values(articles).map((article) => article.id) } }))
  const url = `/api/projects/${projectId}`
  codes.parent = (await json(await pia.post(`${url}/codes`, { data: { name: 'Autonomy' } }))).id
  codes.child = (await json(await pia.post(`${url}/codes`, { data: { name: 'Language rights', parent_id: codes.parent } }))).id

  const save = (client: APIRequestContext, language: string, code: string, memo = '') =>
    client.post(`${url}/articles/${encodeURIComponent(articles[language].id)}/annotations`, { data: { start: 20, end: 60, code_id: code, memo } })
  await json(await save(pia, 'de', codes.parent, 'A note by Pia'))
  oskarSegment = (await json(await save(oskar, 'lld_gherd', codes.child))).id
})

test('a member starts on their own passages, and can see everyone', async ({ page, baseURL }) => {
  await open(page, baseURL!, 'pia')
  await expect(cards(page)).toHaveCount(1)
  await expect(page.getByText('1 passage · 1 hidden by these filters')).toBeVisible()
  await expect(page.getByText('A note by Pia')).toBeVisible()
  await expect(cards(page).locator('.passage-quote')).toHaveText(articles.de.text.slice(20, 60))

  await page.getByLabel('Coder').selectOption({ label: 'Everyone' })
  await expect(cards(page)).toHaveCount(2)
})

test('a code includes its subcodes unless turned off, and counts roll up', async ({ page, baseURL }) => {
  await open(page, baseURL!, 'pia')
  await page.getByLabel('Coder').selectOption({ label: 'Everyone' })
  await expect(cards(page)).toHaveCount(2)
  const parent = page.getByRole('button', { name: /^Autonomy/ })
  await expect(parent.locator('.count')).toHaveText('2')
  await parent.click()
  await expect(cards(page)).toHaveCount(2)
  // The filter lives in the URL, so the box changes once the URL does, a moment after the click.
  await page.getByLabel('Include subcodes').click()
  await expect(page.getByLabel('Include subcodes')).not.toBeChecked()
  await expect(cards(page)).toHaveCount(1)
  await expect(page).toHaveURL(/subcodes=false/)
})

test('filtering by a Ladin variety shows the caution, and only then', async ({ page, baseURL }) => {
  await open(page, baseURL!, 'pia')
  await page.getByLabel('Coder').selectOption({ label: 'Everyone' })
  await expect(cards(page)).toHaveCount(2)
  const caution = page.getByRole('note')
  await expect(caution).toHaveCount(0)
  await page.getByLabel('Variety').selectOption({ value: 'lld_gherd' })
  await expect(cards(page)).toHaveCount(1)
  await expect(caution).toContainText('No Ladin speaker has reviewed')
})

test("another coder's passage opens selected in its article, and the way back keeps the filters", async ({ page, baseURL }) => {
  await open(page, baseURL!, 'pia')
  await page.getByLabel('Coder').selectOption({ label: 'Everyone' })
  await page.getByLabel('Variety').selectOption({ value: 'lld_gherd' })
  await expect(cards(page)).toHaveCount(1)
  const filtered = page.url()
  await cards(page).getByRole('link', { name: articles.lld_gherd.title }).click()

  const highlight = page.locator(`[data-segments~="${oskarSegment}"]`).first()
  await expect(highlight).toHaveClass(/hl-selected/)
  await expect(highlight).toBeInViewport()
  await expect(page.getByRole('button', { name: 'All coders' })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByRole('button', { name: 'Delete' })).toHaveCount(0)

  await page.getByRole('link', { name: 'Back to passages' }).click()
  expect(page.url()).toBe(filtered)
  await expect(cards(page)).toHaveCount(1)
})

test('a link to a deleted passage says so', async ({ page, baseURL }) => {
  await open(page, baseURL!, 'pia')
  await page.goto(`/projects/${projectId}/articles/${encodeURIComponent(articles.de.id)}?segment=00000000-0000-0000-0000-000000000000`)
  await expect(page.getByText('That passage no longer exists')).toBeVisible()
})

test('the download holds what the filters show', async ({ page, baseURL }) => {
  await open(page, baseURL!, 'pia')
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('link', { name: 'Download these passages (CSV)' }).click()])
  expect(download.suggestedFilename()).toBe('didi_passages.csv')
  const stream = await download.createReadStream()
  const chunks: Buffer[] = []
  for await (const chunk of stream) chunks.push(chunk as Buffer)
  const content = Buffer.concat(chunks).toString('utf-8')
  expect(content).toContain('A note by Pia')
  expect(content).not.toContain(oskarSegment)
})

test('a lead removes articles, but never one with coded passages', async ({ page, baseURL }) => {
  await open(page, baseURL!, 'pia')
  await page.goto(`/projects/${projectId}/articles`)
  await page.getByRole('button', { name: `Remove ${articles.de.title}` }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Remove article' }).click()
  await expect(page.getByRole('alert')).toContainText("can't be removed")
  await expect(page.getByRole('heading', { name: articles.de.title })).toBeVisible()

  await page.getByRole('button', { name: 'Remove articles nobody has started (1)…' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Remove 1 articles' }).click()
  await expect(page.getByRole('status')).toContainText('Removed 1 article that nobody had started')
  await expect(page.getByRole('heading', { name: articles.it.title })).toHaveCount(0)
  await expect(page.getByRole('heading', { name: articles.de.title })).toBeVisible()
})

test('a coder gets no removal buttons', async ({ page, baseURL }) => {
  await open(page, baseURL!, 'oskar')
  await page.goto(`/projects/${projectId}/articles`)
  await expect(page.locator('.library-list li').first()).toBeVisible()
  await expect(page.getByRole('button', { name: /^Remove/ })).toHaveCount(0)
})

test('a lead takes a corpus search to the Add articles page; a coder is not offered it', async ({ page, baseURL }) => {
  await open(page, baseURL!, 'pia')
  await page.goto('/search?q=Autonomie&language=de')
  await page.getByRole('link', { name: 'Passages study' }).click()
  await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/articles/add\\?q=Autonomie&language=de`))
  await expect(page.getByLabel('Search the corpus')).toHaveValue('Autonomie')
  await expect(page.locator('.pick-row mark').first()).toBeVisible()
})

test('a coder is not offered adding from search', async ({ page, baseURL }) => {
  await open(page, baseURL!, 'oskar')
  await page.goto('/search?q=Autonomie')
  await expect(page.locator('.result-list li').first()).toBeVisible()
  await expect(page.getByText('Add these results to:')).toHaveCount(0)
})

test('markup in a passage displays literally', async ({ page, baseURL }) => {
  await page.route('**/passages?*', async (route) => {
    const response = await route.fetch()
    const body = await response.json()
    for (const item of body.results) item.quote = '<script>window.hacked = true</script><b>bold</b>'
    await route.fulfill({ response, json: body })
  })
  await open(page, baseURL!, 'pia')
  await expect(cards(page).locator('.passage-quote')).toHaveText('<script>window.hacked = true</script><b>bold</b>')
  expect(await page.evaluate(() => (window as unknown as { hacked?: boolean }).hacked)).toBeUndefined()
})
