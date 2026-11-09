import { expect, test } from '@playwright/test'
import { ADMIN, failOnThirdPartyRequests } from './helpers'

const VARIETIES = [
  ['German', 'de'],
  ['Italian', 'it'],
] as const

test.beforeEach(async ({ page, baseURL }) => {
  failOnThirdPartyRequests(page, baseURL!)
  await page.request.post('/api/auth/login', { data: ADMIN })
})

for (const [label, variety] of VARIETIES) {
  test(`search and open a ${label} article with exact text`, async ({ page, request }) => {
    await page.goto('/search')
    const checkbox = page.getByRole('checkbox', { name: new RegExp(label) })
    const searchResponse = page.waitForResponse(
      (r) => r.url().includes('/api/articles') && r.url().includes(`language=${variety}`) && r.status() === 200,
    )
    await checkbox.click()
    await searchResponse
    await expect(checkbox).toBeChecked()
    await expect(page).toHaveURL(new RegExp(`language=${variety}`))
    const first = page.locator('.result-list h2 a').first()
    await expect(first).toBeVisible()
    await first.click()

    const id = decodeURIComponent(new URL(page.url()).pathname.split('/').pop()!)
    await request.post('/api/auth/login', { data: ADMIN })
    const article = await (await request.get(`/api/articles/${encodeURIComponent(id)}`)).json()
    expect(article.language).toBe(variety)
    const text = page.getByTestId('article-text')
    await expect(text).toBeVisible()
    expect(await text.evaluate((element) => element.textContent)).toBe(article.full_text)
  })
}

test('a query filters results and survives going back', async ({ page }) => {
  await page.goto('/search')
  await page.getByLabel('Search the corpus').fill('autonomia')
  await page.getByRole('button', { name: 'Search', exact: true }).click()
  await expect(page).toHaveURL(/q=autonomia/)
  await expect(page.locator('.result-list mark').first()).toBeVisible()
  await page.locator('.result-list h2 a').first().click()
  await page.getByRole('button', { name: 'Back to results' }).click()
  await expect(page.getByLabel('Search the corpus')).toHaveValue('autonomia')
})

test('an article opened directly can go back to search', async ({ page }) => {
  await page.goto('/search?language=de')
  const href = await page.locator('.result-list h2 a').first().getAttribute('href')
  await page.goto(href!)
  await page.getByRole('button', { name: 'Back to results' }).click()
  await expect(page.getByLabel('Search the corpus')).toBeVisible()
})

test('a broken search shows a clear message', async ({ page }) => {
  await page.goto('/search?q=%22unbalanced')
  await expect(page.getByRole('alert')).toContainText('could not be understood')
})

test('a missing article shows a clear message', async ({ page }) => {
  await page.goto('/articles/does-not-exist')
  await expect(page.getByRole('alert')).toContainText('not in the corpus')
})

test('the theme can be switched', async ({ page }) => {
  await page.goto('/search')
  const before = await page.locator('html').getAttribute('data-theme')
  await page.getByRole('button', { name: /theme/ }).click()
  await expect(page.locator('html')).not.toHaveAttribute('data-theme', before!)
})
