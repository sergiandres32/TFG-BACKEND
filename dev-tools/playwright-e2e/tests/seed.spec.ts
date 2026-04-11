import { test, expect } from '@playwright/test';

test.describe('Seed streamlit', () => {
  test('seed', async ({ page, baseURL }) => {
    await page.goto(baseURL ?? 'http://localhost:8501');
    await expect(page.getByText('Jutge Admin', { exact: true })).toBeVisible();
  });
});
