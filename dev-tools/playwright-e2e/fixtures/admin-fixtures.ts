import { test as base } from '@playwright/test';

import { DashboardPage } from '../pages/DashboardPage';
import { ExercisesPage } from '../pages/ExercisesPage';
import { LoginPage } from '../pages/LoginPage';
import { QuestionsPage } from '../pages/QuestionsPage';
import { TestCasesPage } from '../pages/TestCasesPage';
import { TopicsPage } from '../pages/TopicsPage';

type AdminFixtures = {
  loginPage: LoginPage;
  dashboardPage: DashboardPage;
  topicsPage: TopicsPage;
  exercisesPage: ExercisesPage;
  questionsPage: QuestionsPage;
  testCasesPage: TestCasesPage;
};

export const test = base.extend<AdminFixtures>({
  loginPage: async ({ page }, use) => {
    await use(new LoginPage(page));
  },
  dashboardPage: async ({ page }, use) => {
    await use(new DashboardPage(page));
  },
  topicsPage: async ({ page }, use) => {
    await use(new TopicsPage(page));
  },
  exercisesPage: async ({ page }, use) => {
    await use(new ExercisesPage(page));
  },
  questionsPage: async ({ page }, use) => {
    await use(new QuestionsPage(page));
  },
  testCasesPage: async ({ page }, use) => {
    await use(new TestCasesPage(page));
  },
});

export { expect } from '@playwright/test';
