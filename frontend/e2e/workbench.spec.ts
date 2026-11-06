import { readFile } from 'node:fs/promises'
import { type Page, expect, test } from '@playwright/test'
import { ADMIN, PASSWORD, failOnThirdPartyRequests, logIn, sessionFor } from './helpers'

test.describe.configure({ mode: 'serial' })

async function addUser(page: Page, displayName: string, username: string) {
  await page.getByLabel('Display name').fill(displayName)
  await page.getByLabel('Username').fill(username)
  await page.getByLabel('Temporary password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Add user' }).click()
  await expect(page.getByRole('cell', { name: displayName, exact: true })).toBeVisible()
}

async function createProject(page: Page, name: string, lead: string, codebook: string) {
  await page.goto('/projects')
  await page.getByRole('button', { name: 'New project' }).click()
  await page.getByLabel('Name', { exact: true }).fill(name)
  await page.getByLabel('Project lead').selectOption({ label: lead })
  await page.getByRole('radio', { name: codebook }).check()
  await page.getByRole('button', { name: 'Create project' }).click()
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible()
}

async function addCode(page: Page, name: string, inside = 'Top level', definition = '') {
  const form = page.locator('form', { has: page.getByRole('heading', { name: 'Add a code' }) })
  await form.getByLabel('Name').fill(name)
  await form.getByLabel('Inside').selectOption({ label: inside })
  await form.getByLabel('Definition').fill(definition)
  await form.getByRole('button', { name: 'Add code' }).click()
  await expect(page.locator('.code-tree').getByText(name, { exact: true })).toBeVisible()
}

test('an admin sets up users and two separate projects', async ({ page, baseURL }) => {
  failOnThirdPartyRequests(page, baseURL!)
  await logIn(page, ADMIN.username, ADMIN.password)
  await page.getByRole('link', { name: 'Users' }).click()
  await addUser(page, 'Anna Lead', 'anna')
  await addUser(page, 'Ben Lead', 'ben')
  await addUser(page, 'Cara Coder', 'cara')

  await createProject(page, 'Autonomy framing', 'Anna Lead', 'With the starter codes')
  await createProject(page, 'Language rights', 'Ben Lead', 'Empty')
})

test('a project lead builds a nested codebook, renames and merges codes', async ({ browser, baseURL }) => {
  const page = await sessionFor(browser, baseURL, 'anna')
  await expect(page.getByRole('heading', { name: 'Language rights' })).toHaveCount(0)
  await page.getByRole('link', { name: 'Autonomy framing' }).click()

  const tree = page.locator('.code-tree')
  await expect(tree.getByText('Competences', { exact: true })).toBeVisible()
  await addCode(page, 'Reform', 'Autonomy', 'Passages about changing the statute')
  await addCode(page, 'Old reform', 'Autonomy')
  await expect(tree.getByText('Passages about changing the statute')).toBeVisible()

  // Rename.
  await tree.getByRole('button', { name: 'Competences', exact: true }).click()
  await page.getByLabel('Name').first().fill('Powers')
  await page.getByRole('button', { name: 'Save changes' }).click()
  await expect(tree.getByRole('button', { name: 'Powers', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Close' }).click()

  // Merge, with the confirmation showing what will happen.
  await tree.getByRole('button', { name: 'Old reform', exact: true }).click()
  await page.getByLabel('Merge into another code').selectOption({ label: 'Autonomy > Reform' })
  await page.getByRole('button', { name: 'Merge…' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('0 segments from 0 coders')
  await dialog.getByRole('button', { name: 'Merge codes' }).click()
  await expect(dialog).toHaveCount(0)
  await expect(tree.getByText('Old reform', { exact: true })).toHaveCount(0)

  // Exports.
  for (const [link, header] of [['Download segments', 'annotation_id'], ['Download codes', 'code_path']]) {
    const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('link', { name: link }).click()])
    expect(await readFile(await download.path(), 'utf-8')).toContain(header)
  }
  const [codes] = await Promise.all([page.waitForEvent('download'), page.getByRole('link', { name: 'Download codes' }).click()])
  const content = await readFile(await codes.path(), 'utf-8')
  expect(content).toContain('Autonomy > Powers')
  expect(content).toContain('Old reform')

  // Add a coder.
  await page.getByRole('link', { name: 'Members' }).click()
  await page.getByLabel('Person').selectOption({ label: 'Cara Coder (cara)' })
  await page.getByRole('button', { name: 'Add member' }).click()
  await expect(page.getByRole('cell', { name: 'Cara Coder' })).toBeVisible()

  await page.getByRole('link', { name: 'Activity' }).click()
  await expect(page.getByText(/Anna Lead merged Old reform into Reform/)).toBeVisible()
  await page.context().close()
})

test('a coder can add codes but not change them, and cannot see other projects', async ({ browser, baseURL }) => {
  const page = await sessionFor(browser, baseURL, 'cara')
  await expect(page.getByRole('link', { name: 'Users' })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Language rights' })).toHaveCount(0)
  await page.getByRole('link', { name: 'Autonomy framing' }).click()
  const projectUrl = page.url()

  // Codes aren't editable, but a new one can be added.
  await expect(page.locator('.code-tree').getByRole('button', { name: 'Reform', exact: true })).toHaveCount(0)
  await expect(page.locator('.code-tree').getByText('Reform', { exact: true })).toBeVisible()
  await addCode(page, 'Suggested by Cara')
  await expect(page.getByRole('link', { name: 'Settings' })).toHaveCount(0)

  // Member controls aren't offered.
  await page.getByRole('link', { name: 'Members' }).click()
  await expect(page.getByRole('button', { name: 'Add member' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: /Remove/ })).toHaveCount(0)

  // Pages for admins and other projects are closed, even by direct address.
  await page.goto('/users')
  await expect(page).toHaveURL(/\/projects$/)
  const other = await page.request.get('/api/projects')
  expect(JSON.stringify(await other.json())).not.toContain('Language rights')

  // The API refuses a lead-only action too.
  const projectId = new URL(projectUrl).pathname.split('/')[2]
  const codes = await (await page.request.get(`/api/projects/${projectId}/codes`)).json()
  const response = await page.request.patch(`/api/projects/${projectId}/codes/${codes[0].id}`, { data: { revision: codes[0].revision, name: 'Hacked' } })
  expect(response.status()).toBe(403)
  await page.context().close()
})

test('the other project has its own codebook', async ({ browser, baseURL }) => {
  const page = await sessionFor(browser, baseURL, 'ben')
  await expect(page.getByRole('link', { name: 'Autonomy framing' })).toHaveCount(0)
  await page.getByRole('link', { name: 'Language rights' }).click()
  await expect(page.getByText('This codebook is empty')).toBeVisible()
  await addCode(page, 'Ladin in school')
  await expect(page.locator('.code-tree').getByText('Reform', { exact: true })).toHaveCount(0)
  await page.context().close()
})

test('a stale screen gets a conflict message and cannot overwrite newer work', async ({ browser, baseURL }) => {
  const anna = await sessionFor(browser, baseURL, 'anna')
  await anna.getByRole('link', { name: 'Autonomy framing' }).click()
  const url = anna.url()
  const projectId = new URL(url).pathname.split('/')[2]
  const codes = await (await anna.request.get(`/api/projects/${projectId}/codes`)).json()
  const target = codes.find((code: { name: string }) => code.name === 'Reform')

  await anna.locator('.code-tree').getByRole('button', { name: 'Reform', exact: true }).click()
  // Someone else changes the same code while this form is open.
  await anna.request.patch(`/api/projects/${projectId}/codes/${target.id}`, { data: { revision: target.revision, definition: 'Newer definition' } })
  await anna.getByLabel('Definition').first().fill('Older definition')
  await anna.getByRole('button', { name: 'Save changes' }).click()
  await expect(anna.getByRole('alert')).toContainText('someone else')
  await expect(anna.locator('.code-tree').getByText('Newer definition')).toBeVisible()
  await expect(anna.getByLabel('Definition').first()).toHaveValue('Newer definition')
  await expect(anna.locator('.code-tree').getByText('Older definition')).toHaveCount(0)
  await anna.context().close()
})

test('wrong passwords, logging out and expired access', async ({ browser, baseURL }) => {
  const context = await browser.newContext({ baseURL })
  const page = await context.newPage()
  await page.goto('/')
  await page.getByLabel('Username').fill('cara')
  await page.getByLabel('Password').fill('wrong-password-here')
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page.getByRole('alert')).toContainText('incorrect')

  await logIn(page, 'cara')
  await page.getByRole('button', { name: 'Log out' }).click()
  await expect(page.getByLabel('Password')).toBeVisible()
  await page.goto('/search')
  await expect(page.getByLabel('Password')).toBeVisible()
  await context.close()
})

test('a deactivated user is locked out and an admin can change passwords', async ({ browser, baseURL }) => {
  const cara = await sessionFor(browser, baseURL, 'cara')
  const admin = await sessionFor(browser, baseURL, ADMIN.username, ADMIN.password)
  await admin.goto('/users')
  const row = admin.getByRole('row', { name: /Cara Coder/ })
  await row.getByRole('button', { name: 'Deactivate' }).click()
  await expect(row).toContainText('Deactivated')
  await cara.goto('/projects')
  await expect(cara.getByLabel('Password')).toBeVisible()
  await cara.context().close()
  await admin.context().close()
})

test('a user can change their own password', async ({ browser, baseURL }) => {
  const page = await sessionFor(browser, baseURL, 'ben')
  await page.getByRole('link', { name: 'Ben Lead' }).click()
  await page.getByLabel('Current password').fill(PASSWORD)
  await page.getByLabel('New password').fill('another-long-password')
  await page.getByRole('button', { name: 'Change password' }).click()
  await expect(page.getByRole('status')).toContainText('changed')
  await page.getByRole('button', { name: 'Log out' }).click()
  await logIn(page, 'ben', 'another-long-password')
  await page.context().close()
})
