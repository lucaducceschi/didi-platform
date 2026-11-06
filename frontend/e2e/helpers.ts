import { type Browser, type Page, expect } from '@playwright/test'

export const ADMIN = { username: 'e2e_admin', password: 'e2e-test-password' }
export const PASSWORD = 'a-long-test-password'

export async function logIn(page: Page, username: string, password = PASSWORD) {
  await page.goto('/')
  await page.getByLabel('Username').fill(username)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page.getByRole('link', { name: 'Projects' })).toBeVisible()
}

/** Open a separate browser session, as a different person on another computer would. */
export async function sessionFor(browser: Browser, baseURL: string | undefined, username: string, password = PASSWORD) {
  const context = await browser.newContext({ baseURL, acceptDownloads: true })
  const page = await context.newPage()
  failOnThirdPartyRequests(page, baseURL!)
  await logIn(page, username, password)
  return page
}

export function failOnThirdPartyRequests(page: Page, baseURL: string) {
  page.on('request', (request) => {
    const url = request.url()
    if (url.startsWith('data:') || url.startsWith('blob:')) return
    expect(new URL(url).origin, `third-party request to ${url}`).toBe(new URL(baseURL).origin)
  })
}
