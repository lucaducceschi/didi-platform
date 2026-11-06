import { defineConfig } from '@playwright/test'

// Starts its own API and frontend on separate ports, against a throwaway database.
// Needs Docker's PostgreSQL (`make e2e` starts it) and the real corpus file.
const E2E_DATABASE = 'postgresql+psycopg://didi:didi_dev@localhost:5433/didi_e2e'

export default defineConfig({
  testDir: './e2e',
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:5181' },
  outputDir: './test-results',
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
