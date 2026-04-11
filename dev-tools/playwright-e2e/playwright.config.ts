import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: process.env.STREAMLIT_URL ?? 'http://localhost:8501',
    headless: !process.env.PW_HEADED,
    viewport: { width: 1366, height: 768 },
  },
  reporter: [['list']],
});
