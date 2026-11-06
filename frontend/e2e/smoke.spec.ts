import { expect, test } from '@playwright/test'

const VARIETIES = [
  ['German', 'de'],
  ['Italian', 'it'],
  ['Ladin Gherdëina', 'lld_gherd'],
  ['Ladin Val Badia', 'lld_badia'],
] as const

// Everything the page loads must come from the app itself.
test.beforeEach(async ({ page, baseURL }) => {
  page.on('request', (request) => {
    const url = request.url()
    if (url.startsWith('data:') || url.startsWith('blob:')) return
    expect(new URL(url).origin, `third-party request to ${url}`).toBe(new URL(baseURL!).origin)
  })
})

for (const [label, variety] of VARIETIES) {
  test(`search and open a ${label} article with exact text`, async ({ page, request }) => {
    await page.goto('/')
    const checkbox = page.getByRole('checkbox', { name: new RegExp(label) })
    await checkbox.click()
    await expect(checkbox).toBeChecked()
    await expect(page).toHaveURL(new RegExp(`language=${variety}`))
    const first = page.locator('.result-list h2 a').first()
    await expect(first).toBeVisible()
    await first.click()

    const id = decodeURIComponent(new URL(page.url()).pathname.split('/').pop()!)
    const article = await (await request.get(`/api/articles/${encodeURIComponent(id)}`)).json()
    expect(article.language).toBe(variety)
    const text = page.getByTestId('article-text')
    await expect(text).toBeVisible()
    expect(await text.evaluate((element) => element.textContent)).toBe(article.full_text)
  })
}

test('a query filters results and survives going back', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Search the corpus').fill('autonomia')
  await page.getByRole('button', { name: 'Search' }).click()
  await expect(page).toHaveURL(/q=autonomia/)
  await expect(page.locator('.result-list mark').first()).toBeVisible()
  await page.locator('.result-list h2 a').first().click()
  await page.getByRole('button', { name: 'Back to results' }).click()
  await expect(page.getByLabel('Search the corpus')).toHaveValue('autonomia')
})

test('an article opened directly can go back to search', async ({ page }) => {
  await page.goto('/?language=de')
  const href = await page.locator('.result-list h2 a').first().getAttribute('href')
  await page.goto(href!)
  await page.getByRole('button', { name: 'Back to results' }).click()
  await expect(page.getByLabel('Search the corpus')).toBeVisible()
})

test('a broken search shows a clear message', async ({ page }) => {
  await page.goto('/?q=%22unbalanced')
  await expect(page.getByRole('alert')).toContainText('could not be understood')
})

test('a missing article shows a clear message', async ({ page }) => {
  await page.goto('/articles/does-not-exist')
  await expect(page.getByRole('alert')).toContainText('not in the corpus')
})

test('the theme can be switched', async ({ page }) => {
  await page.goto('/')
  const before = await page.locator('html').getAttribute('data-theme')
  await page.getByRole('button', { name: /theme/ }).click()
  await expect(page.locator('html')).not.toHaveAttribute('data-theme', before!)
})
