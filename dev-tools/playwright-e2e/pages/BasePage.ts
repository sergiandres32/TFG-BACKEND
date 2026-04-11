import { Locator, Page } from '@playwright/test';

export class BasePage {
  readonly apiUrlField: Locator;
  readonly logoutButton: Locator;

  constructor(protected readonly page: Page) {
    this.apiUrlField = this.page.getByLabel('URL API');
    this.logoutButton = this.page.getByRole('button', { name: 'Tanca sessió' });
  }

  async goto(path = '/'): Promise<void> {
    await this.page.goto(path);
  }

  protected async selectOptionByLabel(label: string, optionText: string): Promise<void> {
    const control = this.page.getByRole('combobox', {
      name: new RegExp(this.escapeForRegex(label), 'i'),
    }).first();
    await control.click();
    await control.fill(optionText);

    const option = this.page
      .getByRole('option', { name: new RegExp(this.escapeForRegex(optionText), 'i') })
      .first();

    if ((await option.count()) > 0) {
      await option.click();
      return;
    }

    await control.press('Enter');
  }

  private escapeForRegex(value: string): string {
    return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }
}
