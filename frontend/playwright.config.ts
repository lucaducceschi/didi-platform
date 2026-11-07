import { defineConfig } from '@playwright/test'

// Starts its own API and frontend on separate ports, against a throwaway database.
// Needs Docker's PostgreSQL (`make e2e` starts it) and the real corpus file.
const E2E_DATABASE = 'postgresql+psycopg://didi:didi_dev@localhost:5433/didi_e2e'

export default defineConfig({
  testDir: './e2e',
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:5181' },
  outputDir: './test-results',
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
    // Positions come from each browser's own selection code, so check those in the other engines too.
    { name: 'firefox', use: { browserName: 'firefox' }, testMatch: /select\.spec/ },
    // Opt in with E2E_WEBKIT=1. WebKit's automation intermittently delivers mouse events to <html> on
    // macOS, even though the page reports the right element at that point, so it can't run by default.
    ...(process.env.E2E_WEBKIT ? [{ name: 'webkit', use: { browserName: 'webkit' as const }, testMatch: /select\.spec/, retries: 2 }] : []),
  ],
  webServer: [
    {
      command: `cd .. && .venv/bin/python scripts/e2e_setup.py && DIDI_DATABASE_URL=${E2E_DATABASE} exec .venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8011`,
      url: 'http://127.0.0.1:8011/api/health',
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: 'DIDI_API_URL=http://127.0.0.1:8011 npx vite --port 5181',
      url: 'http://127.0.0.1:5181',
      reuseExistingServer: false,
    },
  ],
})
