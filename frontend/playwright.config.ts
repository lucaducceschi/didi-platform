import { defineConfig } from '@playwright/test'

// Needs `make dev` running. These tests use the real local corpus.
export default defineConfig({
  testDir: './e2e',
  use: { baseURL: 'http://127.0.0.1:5180' },
  outputDir: './test-results',
})
