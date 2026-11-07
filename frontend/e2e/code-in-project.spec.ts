import { type Page, expect, test } from '@playwright/test'
import { ADMIN, failOnThirdPartyRequests, logIn, PASSWORD, sessionFor } from './helpers'

test.describe.configure({ mode: 'serial' })

let articleId = ''
let articlePath = ''

const readOnlyNote = (page: Page) => page.getByText('Coding happens inside a project.')

test('set up a lead, a coder and someone with no project', async ({ playwright, baseURL }) => {
  const admin = await playwright.request.newContext({ baseURL })
  expect((await admin.post('/api/auth/login', { data: ADMIN })).ok()).toBe(true)
  const ids: Record<string, string> = {}
  for (const username of ['bridge_lead', 'bridge_coder', 'bridge_nobody']) {
    const response = await admin.post('/api/users', { data: { username, display_name: username, password: PASSWORD } })
    expect(response.ok()).toBe(true)
    ids[username] = (await response.json()).id
  }
  const project = await (await admin.post('/api/projects', { data: { name: 'Bridge study', lead_user_id: ids.bridge_lead, codebook: { mode: 'empty' } } })).json()
  expect((await admin.post(`/api/projects/${project.id}/members`, { data: { user_id: ids.bridge_coder, role: 'coder' } })).ok()).toBe(true)
  articleId = (await (await admin.get('/api/articles/search?q=&page_size=1')).json()).results[0].id
  articlePath = `/articles/${encodeURIComponent(articleId)}`
})

test('without a project, or as a coder before the article is added, the page says why it is read-only', async ({ browser, baseURL }) => {
  const nobody = await sessionFor(browser, baseURL, 'bridge_nobody')
  await nobody.goto(articlePath)
  await expect(readOnlyNote(nobody)).toBeVisible()
  await expect(nobody.getByText('ask a project lead to add you')).toBeVisible()
  await nobody.context().close()

  const coder = await sessionFor(browser, baseURL, 'bridge_coder')
  await coder.goto(articlePath)
  await expect(coder.getByText('ask a project lead to add it')).toBeVisible()
  await expect(coder.getByRole('button', { name: /Add to/ })).toHaveCount(0)
  await coder.context().close()
})

test('a lead adds the article from the corpus page and lands in the reader', async ({ page, baseURL }) => {
  failOnThirdPartyRequests(page, baseURL!)
  await logIn(page, 'bridge_lead')
  await page.goto(articlePath)
  await page.getByRole('button', { name: 'Add to Bridge study and code' }).click()
  await expect(page).toHaveURL(new RegExp(`/projects/[^/]+/articles/${encodeURIComponent(articleId)}$`))
  await expect(page.getByRole('button', { name: 'Mark done' })).toBeVisible()
})

test('once it is in the project, the corpus page links to the reader for its members', async ({ browser, baseURL }) => {
  for (const username of ['bridge_lead', 'bridge_coder']) {
    const page = await sessionFor(browser, baseURL, username)
    await page.goto(articlePath)
    await expect(page.getByRole('button', { name: /Add to/ })).toHaveCount(0)
    await page.getByRole('link', { name: 'Open in Bridge study to code' }).click()
    await expect(page.getByRole('button', { name: 'Mark done' })).toBeVisible()
    await page.context().close()
  }
})
