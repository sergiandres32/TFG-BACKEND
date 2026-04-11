import { expect, Locator, Page } from '@playwright/test';

import { BasePage } from './BasePage';

export class LoginPage extends BasePage {
  readonly title: Locator;
  readonly usernameField: Locator;
  readonly passwordField: Locator;
  readonly signInButton: Locator;

  constructor(page: Page) {
    super(page);
    this.title = this.page.getByText('Jutge Admin', { exact: true });
    this.usernameField = this.page.getByLabel('Usuari');
    this.passwordField = this.page.getByLabel('Contrasenya');
    this.signInButton = this.page.getByRole('button', { name: 'Inicia sessió' });
  }

  async waitReady(): Promise<void> {
    await expect(this.title).toBeVisible();
    await expect(this.usernameField).toBeVisible();
    await expect(this.passwordField).toBeVisible();
  }

  async login(username: string, password: string): Promise<void> {
    await this.usernameField.fill(username);
    await this.passwordField.fill(password);
    await this.signInButton.click();
  }
}
