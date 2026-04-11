import { expect, Locator, Page } from '@playwright/test';

import { BasePage } from './BasePage';

export class DashboardPage extends BasePage {
  readonly title: Locator;
  readonly topicsHeading: Locator;
  readonly exercisesHeading: Locator;
  readonly quizHeading: Locator;

  constructor(page: Page) {
    super(page);
    this.title = this.page.getByText("Tauler d'administració", { exact: true });
    this.topicsHeading = this.page.getByRole('heading', { name: 'Temes' });
    this.exercisesHeading = this.page.getByRole('heading', { name: 'Exercicis' });
    this.quizHeading = this.page.getByRole('heading', { name: 'Preguntes tipus test' });
  }

  async waitReady(): Promise<void> {
    await expect(this.title).toBeVisible();
    await expect(this.topicsHeading).toBeVisible();
    await expect(this.exercisesHeading).toBeVisible();
    await expect(this.quizHeading).toBeVisible();
  }
}
