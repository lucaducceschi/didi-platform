import { execFileSync } from 'node:child_process'
import { type APIRequestContext, type Page, expect, test } from '@playwright/test'
import { ADMIN, PASSWORD, failOnThirdPartyRequests, logIn } from './helpers'

test.describe.configure({ mode: 'serial' })

const ARTICLES: Record<string, string> = JSON.parse(execFileSync('../.venv/bin/python', ['../scripts/e2e_find_articles.py'], { encoding: 'utf-8' }))

// Tests run once per browser against one database, so each browser gets its own people and project.
let suffix = ''
let projectId = ''
let codes: Record<string, { id: string; revision: number }> = {}

// oxlint-disable-next-line typescript/no-explicit-any -- test data, shaped by the API
async function json(response: Awaited<ReturnType<APIRequestContext['get']>>): Promise<any> {
  expect(response.ok(), await response.text()).toBe(true)
  return response.json()
}

const name = (person: string) => `${person}_${suffix}`
const articleUrl = (id: string) => `/projects/${projectId}/articles/${encodeURIComponent(id)}`
const annotationsPath = (id: string, scope = 'all') => `/api/projects/${projectId}/articles/${encodeURIComponent(id)}/annotations?scope=${scope}`

async function open(page: Page, person: string, articleId: string) {
  await logIn(page, name(person))
  await page.goto(articleUrl(articleId))
  await expect(page.getByTestId('article-text')).toBeVisible()
}

/** Select by code-point position through the browser's own Range, across however many pieces there are. */
async function selectByPosition(page: Page, start: number, end: number) {
  await page.getByTestId('article-text').evaluate((root, [from, to]) => {
    const range = document.createRange()
    let seen = 0
    for (const span of Array.from(root.children) as HTMLElement[]) {
      const node = span.firstChild as Text | null
      if (!node) continue
      const points = Array.from(node.data)
      const utf16 = (count: number) => points.slice(0, count).join('').length
      if (from >= seen && from < seen + points.length) range.setStart(node, utf16(from - seen))
      if (to > seen && to <= seen + points.length) range.setEnd(node, utf16(to - seen))
      seen += points.length
    }
    const selection = window.getSelection()!
    selection.removeAllRanges()
    selection.addRange(range)
    root.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }))
  }, [start, end])
}

/** Find where a stretch of text is drawn, for real mouse movement. */
async function textEdges(page: Page, target: string) {
  return page.getByTestId('article-text').evaluate((root, wanted) => {
    const node = Array.from(root.childNodes).map((span) => span.firstChild as Text).find((text) => text?.data.includes(wanted))!
    const index = node.data.indexOf(wanted)
    const range = document.createRange()
    range.setStart(node, index)
    range.setEnd(node, index + wanted.length)
    // Bring the words themselves into view: their piece of text can be much taller than the window.
    window.scrollBy(0, range.getBoundingClientRect().top - window.innerHeight / 2)
    const rects = range.getClientRects()
    const first = rects[0]
    const last = rects[rects.length - 1]
    return { x1: first.left, y1: first.top + first.height / 2, x2: last.right, y2: last.top + last.height / 2 }
  }, target)
}

async function dragOver(page: Page, target: string) {
  const edges = await textEdges(page, target)
  await page.mouse.move(edges.x1, edges.y1)
  await page.mouse.down()
  await page.mouse.move(edges.x2, edges.y2, { steps: 8 })
  await page.mouse.up()
}

const panel = (page: Page) => page.getByRole('form', { name: 'Code this passage' })

async function saveWithCode(page: Page, code: string, memo = '') {
  await panel(page).getByRole('radio', { name: code }).check()
  if (memo) await panel(page).getByLabel('Memo').fill(memo)
  await panel(page).getByRole('button', { name: 'Save segment' }).click()
  await expect(panel(page)).toHaveCount(0)
}

async function highlightText(page: Page, segmentId: string) {
  return page.locator(`[data-segments~="${segmentId}"]`).evaluateAll((spans) => spans.map((span) => span.textContent).join(''))
}

test('set up a project and coders', async ({ playwright, baseURL }, testInfo) => {
  suffix = `${testInfo.project.name}${testInfo.retry || ''}` // A retry starts again with new people.
  const make = async (username: string, password: string) => {
    const context = await playwright.request.newContext({ baseURL })
    await json(await context.post('/api/auth/login', { data: { username, password } }))
    return context
  }
  const admin = await make(ADMIN.username, ADMIN.password)
  const ids: Record<string, string> = {}
  for (const person of ['lena', 'carl', 'dora', 'ivan']) {
    ids[person] = (await json(await admin.post('/api/users', { data: { username: name(person), display_name: `${person} ${suffix}`, password: PASSWORD } }))).id
  }
  projectId = (await json(await admin.post('/api/projects', { data: { name: `Coding ${suffix}`, lead_user_id: ids.lena, codebook: { mode: 'empty' } } }))).id
  await json(await admin.post(`/api/projects/${projectId}/members`, { data: { user_id: ids.carl, role: 'coder' } }))
  await json(await admin.post(`/api/projects/${projectId}/members`, { data: { user_id: ids.dora, role: 'coder' } }))
  const lena = await make(name('lena'), PASSWORD)
  await json(await lena.post(`/api/projects/${projectId}/articles`, { data: { article_ids: Object.values(ARTICLES) } }))
  codes = {}
  for (const code of ['Autonomy', 'Rights', 'To merge']) {
    codes[code] = await json(await lena.post(`/api/projects/${projectId}/codes`, { data: { name: code, definition: `Definition of ${code}` } }))
  }
})

const INTERESTING: Record<string, RegExp> = {
  non_nfc: /\p{M}/u,
  emoji: /[\u{10000}-\u{10FFFF}]/u,
  markdown: /[*_`$#~]/,
  // oxlint-disable-next-line no-control-regex -- this control character is exactly what is being tested
  control_character: /[\x08]/,
}

for (const [kind, pattern] of Object.entries(INTERESTING)) {
  test(`${kind}: a selection around the hard character saves exactly`, async ({ page, baseURL, request }) => {
    failOnThirdPartyRequests(page, baseURL!)
    await open(page, 'carl', ARTICLES[kind])
    await request.post('/api/auth/login', { data: { username: name('carl'), password: PASSWORD } })
    const article = await json(await request.get(`/api/articles/${encodeURIComponent(ARTICLES[kind])}`))
    const points = Array.from(article.full_text as string)
    const hard = points.findIndex((point) => pattern.test(point))
    expect(hard).toBeGreaterThanOrEqual(0)
    const start = Math.max(0, hard - 12)
    const end = Math.min(points.length, hard + 12)

    await selectByPosition(page, start, end)
    await expect(panel(page)).toBeVisible()
    await saveWithCode(page, 'Autonomy')

    const [segment] = await json(await request.get(annotationsPath(ARTICLES[kind], 'mine')))
    expect(segment.quote).toBe(points.slice(segment.start_pos, segment.end_pos).join(''))
    expect(points.slice(start, end).join('')).toContain(segment.quote)
    expect(segment.quote.length).toBeGreaterThan(5)
    await expect(page.locator(`[data-segments~="${segment.id}"]`).first()).toBeVisible()
    expect(await highlightText(page, segment.id)).toBe(segment.quote)
    expect(await page.getByTestId('article-text').evaluate((element) => element.textContent)).toBe(article.full_text)

    await page.reload()
    await expect(page.locator(`[data-segments~="${segment.id}"]`).first()).toBeVisible()
    expect(await highlightText(page, segment.id)).toBe(segment.quote)
  })
}

test('a real mouse drag selects exactly the words dragged over, trimmed', async ({ page, request }) => {
  await open(page, 'dora', ARTICLES.german)
  await request.post('/api/auth/login', { data: { username: name('dora'), password: PASSWORD } })
  const article = await json(await request.get(`/api/articles/${encodeURIComponent(ARTICLES.german)}`))
  const words = (article.full_text as string).split('\n')[0].split(' ').filter((word) => /^\p{L}+$/u.test(word))
  const target = words.slice(1, 4).join(' ')
  const found = (article.full_text as string).includes(target) ? target : words[1]
  await dragOver(page, found)
  await expect(page.getByTestId('pending-quote')).toHaveText(found)
  await saveWithCode(page, 'Rights', 'Dragged with the mouse')
  const segments = await json(await request.get(annotationsPath(ARTICLES.german, 'mine')))
  expect(segments.map((segment: { quote: string }) => segment.quote)).toEqual([found])
  expect(Array.from(article.full_text as string).slice(segments[0].start_pos, segments[0].end_pos).join('')).toBe(found)
})

test('a real mouse drag works after an emoji, in the same line', async ({ page, request }) => {
  await open(page, 'dora', ARTICLES.emoji)
  await request.post('/api/auth/login', { data: { username: name('dora'), password: PASSWORD } })
  const article = await json(await request.get(`/api/articles/${encodeURIComponent(ARTICLES.emoji)}`))
  const text = article.full_text as string
  const after = text.slice(text.search(/[\u{10000}-\u{10FFFF}]/u)).split(/\s+/).slice(1).filter((word) => /^\p{L}{3,}$/u.test(word))
  test.skip(after.length === 0, 'No plain word follows the emoji')
  await dragOver(page, after[0])
  await expect(page.getByTestId('pending-quote')).toHaveText(after[0])
})

test('a selection across existing highlights saves the right positions', async ({ page, request }) => {
  await open(page, 'carl', ARTICLES.italian)
  await request.post('/api/auth/login', { data: { username: name('carl'), password: PASSWORD } })
  await selectByPosition(page, 20, 40)
  await saveWithCode(page, 'Autonomy')
  await selectByPosition(page, 60, 80)
  await saveWithCode(page, 'Rights')
  await selectByPosition(page, 10, 100)
  await saveWithCode(page, 'To merge')
  const article = await json(await request.get(`/api/articles/${encodeURIComponent(ARTICLES.italian)}`))
  const segments = await json(await request.get(annotationsPath(ARTICLES.italian, 'mine')))
  expect(segments).toHaveLength(3)
  const points = Array.from(article.full_text as string)
  for (const segment of segments) {
    expect(points.slice(segment.start_pos, segment.end_pos).join('')).toBe(segment.quote)
    expect(await highlightText(page, segment.id)).toBe(segment.quote)
  }
})

test('selections that begin outside the reader or are empty are ignored', async ({ page }) => {
  await open(page, 'carl', ARTICLES.ladin)
  // Scripted: begins in the title, ends in the article.
  await page.evaluate(() => {
    const root = document.querySelector('[data-testid="article-text"]')!
    const title = document.querySelector('.reader-header h2')!
    const range = document.createRange()
    range.setStart(title.firstChild!, 0)
    range.setEnd(root.firstChild!.firstChild!, 10)
    const selection = window.getSelection()!
    selection.removeAllRanges()
    selection.addRange(range)
    root.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }))
  })
  await expect(panel(page)).toHaveCount(0)

  // A real drag from the title into the article.
  await page.evaluate(() => window.getSelection()!.removeAllRanges())
  const title = (await page.locator('.reader-header h2').boundingBox())!
  const reader = (await page.getByTestId('article-text').boundingBox())!
  await page.mouse.move(title.x + 5, title.y + title.height / 2)
  await page.mouse.down()
  await page.mouse.move(reader.x + 60, reader.y + 12, { steps: 6 })
  await page.mouse.up()
  await expect(panel(page)).toHaveCount(0)

  // A plain click selects nothing.
  await page.evaluate(() => window.getSelection()!.removeAllRanges())
  await page.mouse.click(reader.x + 30, reader.y + 12)
  await expect(panel(page)).toHaveCount(0)
})

test('CRLF text sends the right positions', async ({ page }) => {
  const text = 'Line one\r\nLine two\r\n\r\nTARGET words end'
  await logIn(page, name('carl'))
  await page.route(`**/api/projects/${projectId}/articles/crlf`, (route) => route.fulfill({
    json: {
      id: 'crlf', source: 'salto', source_label: 'Salto.bz', language: 'de', language_label: 'German (de)', url: 'https://example.org/',
      title: 'Crlf', publish_date: '2025-01-01T00:00:00', author: 'A', category: null, word_count: 6, full_text: text, metrics: {}, metadata: {},
    },
  }))
  await page.route(`**/api/projects/${projectId}/articles/crlf/progress`, (route) => route.fulfill({ json: { status: 'not_started' } }))
  await page.route(`**/api/projects/${projectId}/articles/crlf/presence`, (route) => route.fulfill({ json: { others: [] } }))
  let posted: { start: number; end: number } | null = null
  await page.route(`**/api/projects/${projectId}/articles/crlf/annotations*`, (route) => {
    if (route.request().method() === 'POST') {
      posted = route.request().postDataJSON()
      return route.fulfill({ status: 201, json: { created: true } })
    }
    return route.fulfill({ json: [] })
  })
  await page.goto(`/projects/${projectId}/articles/crlf`)
  await expect(page.getByTestId('article-text')).toBeVisible()
  expect(await page.getByTestId('article-text').evaluate((element) => element.textContent)).toBe(text)
  const start = text.indexOf('TARGET')
  await selectByPosition(page, start, start + 6)
  await saveWithCode(page, 'Autonomy')
  expect(posted).toMatchObject({ start, end: start + 6 })
})

test('saving keeps the scroll position on a long article', async ({ page }) => {
  await open(page, 'carl', ARTICLES.long)
  await page.evaluate(() => window.scrollTo(0, 2500))
  const before = await page.evaluate(() => window.scrollY)
  expect(before).toBeGreaterThan(1000)
  const position = await page.getByTestId('article-text').evaluate((root) => {
    const rootTop = root.getBoundingClientRect().top + window.scrollY
    const node = root.firstChild!.firstChild as Text
    const range = document.createRange()
    let offset = 0
    for (; offset < node.length - 30; offset += 50) {
      range.setStart(node, offset)
      range.setEnd(node, offset + 1)
      if (range.getBoundingClientRect().top + window.scrollY > rootTop + 2500 + 200) break
    }
    return Array.from(node.data.slice(0, offset)).length
  })
  await selectByPosition(page, position, position + 25)
  await saveWithCode(page, 'Autonomy')
  await expect(page.locator('.hl-mine').first()).toBeVisible()
  expect(Math.abs((await page.evaluate(() => window.scrollY)) - before)).toBeLessThan(5)
})

test('a new code can be made while coding, and a repeat shows a clear message', async ({ page }) => {
  await open(page, 'dora', ARTICLES.ladin)
  await selectByPosition(page, 5, 25)
  await panel(page).getByLabel('New code').fill(`Made ${suffix}`)
  await panel(page).getByRole('button', { name: 'Add' }).click()
  await expect(panel(page).getByRole('radio', { name: `Made ${suffix}` })).toBeChecked()
  await panel(page).getByRole('button', { name: 'Save segment' }).click()
  await expect(panel(page)).toHaveCount(0)

  await selectByPosition(page, 5, 25)
  await saveWithCode(page, `Made ${suffix}`)
  await expect(page.getByRole('status').filter({ hasText: 'already coded' })).toBeVisible()
})

test('progress: coding starts it, and it can be marked done and reopened', async ({ page }) => {
  await open(page, 'dora', ARTICLES.ladin)
  await expect(page.getByText('Your status: In progress')).toBeVisible()
  await page.getByRole('button', { name: 'Mark done' }).click()
  await expect(page.getByText('Your status: Done')).toBeVisible()
  await page.goto(`/projects/${projectId}/articles`)
  await page.getByLabel('My status').selectOption({ value: 'done' })
  await expect(page.locator('.library-list li')).toHaveCount(1)
  await page.locator('.library-list h2 a').click()
  await page.getByRole('button', { name: 'Reopen' }).click()
  await expect(page.getByText('Your status: In progress')).toBeVisible()
})

test('two coders save on the same article at once, and see each other', async ({ browser, baseURL }) => {
  const contexts = await Promise.all([browser.newContext({ baseURL }), browser.newContext({ baseURL })])
  const [carl, dora] = await Promise.all(contexts.map((context) => context.newPage()))
  await open(carl, 'carl', ARTICLES.markdown)
  await open(dora, 'dora', ARTICLES.markdown)
  await expect(dora.getByRole('status').filter({ hasText: `carl ${suffix} is also working` })).toBeVisible()
  // Each page checks in every 30 seconds, so a reload shows the newcomer without waiting.
  await carl.reload()
  await expect(carl.getByRole('status').filter({ hasText: `dora ${suffix} is also working` })).toBeVisible()

  await selectByPosition(carl, 60, 90)
  await selectByPosition(dora, 60, 90)
  await carl.getByRole('form', { name: 'Code this passage' }).getByRole('radio', { name: 'Rights' }).check()
  await dora.getByRole('form', { name: 'Code this passage' }).getByRole('radio', { name: 'Rights' }).check()
  await Promise.all([
    carl.getByRole('button', { name: 'Save segment' }).click(),
    dora.getByRole('button', { name: 'Save segment' }).click(),
  ])
  await expect(panel(carl)).toHaveCount(0)
  await expect(panel(dora)).toHaveCount(0)

  // Mine by default, both under All coders.
  await expect(dora.locator('.hl-other')).toHaveCount(0)
  await dora.getByRole('button', { name: 'All coders' }).click()
  await expect(dora.locator('.segment-by', { hasText: `carl ${suffix}` }).first()).toBeVisible()
  await expect(dora.locator('.segment-by', { hasText: `dora ${suffix}` }).first()).toBeVisible()

  // Leaving clears the banner for the other person.
  await carl.close()
  await dora.waitForTimeout(300)
  await dora.reload()
  await expect(dora.getByRole('status').filter({ hasText: 'also working' })).toHaveCount(0)
  await Promise.all(contexts.map((context) => context.close()))
})

test('a merge while another coder has that code selected saves under the merged code', async ({ page, playwright, baseURL }) => {
  await open(page, 'carl', ARTICLES.non_nfc)
  await selectByPosition(page, 40, 60)
  await panel(page).getByRole('radio', { name: 'To merge' }).check()

  const lena = await playwright.request.newContext({ baseURL })
  await json(await lena.post('/api/auth/login', { data: { username: name('lena'), password: PASSWORD } }))
  const current = await json(await lena.get(`/api/projects/${projectId}/codes`))
  const source = current.find((code: { name: string }) => code.name === 'To merge')
  const target = current.find((code: { name: string }) => code.name === 'Rights')
  await json(await lena.post(`/api/projects/${projectId}/codes/${source.id}/merge`, { data: { target_id: target.id, source_revision: source.revision, target_revision: target.revision } }))

  await panel(page).getByRole('button', { name: 'Save segment' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'was merged while you were working' })).toContainText('Rights')
  await expect(page.locator('.segment-group h3', { hasText: 'Rights' })).toBeVisible()
})

test('editing: your own segment can change, others cannot, and tabs conflict safely', async ({ browser, baseURL }) => {
  const context = await browser.newContext({ baseURL })
  const first = await context.newPage()
  await open(first, 'dora', ARTICLES.markdown)
  const second = await context.newPage()
  await second.goto(articleUrl(ARTICLES.markdown))

  const openOwn = async (page: Page) => {
    await page.locator('.segment-item').first().click()
    await expect(page.getByLabel('Selected segments').getByLabel('Memo')).toBeVisible()
  }
  await openOwn(first)
  await openOwn(second)

  await first.getByLabel('Selected segments').getByLabel('Memo').fill('From the first tab')
  await first.getByLabel('Selected segments').getByRole('button', { name: 'Save changes' }).click()
  await expect(first.getByRole('status').filter({ hasText: 'Saved' })).toBeVisible()

  await second.getByLabel('Selected segments').getByLabel('Memo').fill('From the second tab')
  await second.getByLabel('Selected segments').getByRole('button', { name: 'Save changes' }).click()
  await expect(second.getByRole('alert')).toContainText('someone else')
  await expect(second.getByLabel('Selected segments').getByLabel('Memo')).toHaveValue('From the first tab')

  // Another coder's segment is read-only, even though they can see it.
  const carlContext = await browser.newContext({ baseURL })
  const carl = await carlContext.newPage()
  await open(carl, 'carl', ARTICLES.markdown)
  await carl.getByRole('button', { name: 'All coders' }).click()
  await carl.locator('.segment-item', { hasText: `dora ${suffix}` }).first().click()
  const details = carl.getByLabel('Selected segments')
  await expect(details.getByText('From the first tab')).toBeVisible()
  await expect(details.getByRole('button', { name: /Save|Delete/ })).toHaveCount(0)
  await carlContext.close()

  // Change the code, then delete with confirmation.
  await first.reload()
  await openOwn(first)
  await first.getByLabel('Selected segments').getByRole('combobox').selectOption({ label: 'Autonomy' })
  await first.getByLabel('Selected segments').getByRole('button', { name: 'Save changes' }).click()
  await expect(first.locator('.segment-group h3', { hasText: 'Autonomy' })).toBeVisible()
  await first.getByLabel('Selected segments').getByRole('button', { name: 'Delete…' }).click()
  await first.getByRole('dialog').getByRole('button', { name: 'Delete segment' }).click()
  await expect(first.getByLabel('Selected segments')).toHaveCount(0)
  await context.close()
})

test('someone who cannot code here gets no coding panel', async ({ page }) => {
  await logIn(page, ADMIN.username, ADMIN.password)
  await page.goto(articleUrl(ARTICLES.ladin))
  await expect(page.getByTestId('article-text')).toBeVisible()
  await selectByPosition(page, 5, 25)
  await expect(panel(page)).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Mark done' })).toHaveCount(0)
})
