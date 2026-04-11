// spec: specs/streamlit_admin_smoke_test_plan.md
// input: tests/seed.spec.ts
// tests\admin\login-dashboard-smoke.spec.ts

import { test, expect } from '../../fixtures/admin-fixtures';

test.describe('Smoke Streamlit Admin', () => {
  test('Login profesor y carga de dashboard', async ({ loginPage, dashboardPage }) => {
    await loginPage.goto('/');

    await loginPage.waitReady();
    await loginPage.login(
      process.env.STREAMLIT_TEACHER_USER ?? 'profesor_seed',
      process.env.STREAMLIT_TEACHER_PASS ?? 'profesor123'
    );

    await dashboardPage.waitReady();
    await expect(dashboardPage.topicsHeading).toBeVisible();
  });
});
