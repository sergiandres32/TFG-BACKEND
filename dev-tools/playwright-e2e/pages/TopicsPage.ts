import { expect, Locator, Page } from '@playwright/test';

import { TableActions } from '../components/TableActions';
import { BasePage } from './BasePage';

export class TopicsPage extends BasePage {
  readonly heading: Locator;
  readonly nameField: Locator;
  readonly descriptionField: Locator;
  readonly weightField: Locator;
  readonly createButton: Locator;
  readonly successMessage: Locator;
  readonly importJsonToggleButton: Locator;
  readonly jsonInput: Locator;
  readonly importTopicsButton: Locator;
  readonly actions: TableActions;

  constructor(page: Page) {
    super(page);
    this.heading = this.page.getByRole('heading', { name: 'Crear tema' });
    this.nameField = this.page.getByLabel('Nom', { exact: true });
    this.descriptionField = this.page.getByLabel('Descripció', { exact: true });
    this.weightField = this.page.getByLabel('Pes', { exact: true });
    this.createButton = this.page.getByRole('button', { name: 'Crear tema', exact: true });
    this.successMessage = this.page.getByText('Tema creat', { exact: false });
    this.importJsonToggleButton = this.page.getByRole('button', { name: 'Importar des de JSON' }).first();
    this.jsonInput = this.page.getByLabel('JSON de temes');
    this.importTopicsButton = this.page.getByRole('button', { name: 'Importar temes' });
    this.actions = new TableActions(page);
  }

  async waitReady(): Promise<void> {
    await expect(this.heading).toBeVisible();
  }

  async createTopic(name: string, description: string, weight: string): Promise<void> {
    await this.nameField.fill(name);
    await this.descriptionField.fill(description);
    await this.weightField.fill(weight);
    await this.createButton.click();
  }

  async openJsonImportMode(): Promise<void> {
    await this.importJsonToggleButton.click();
    await expect(this.jsonInput).toBeVisible();
  }

  async importTopicsFromJson(rawJson: string): Promise<void> {
    await this.jsonInput.fill(rawJson);
    await this.importTopicsButton.click();
  }

  async expectTopicVisible(topicName: string): Promise<void> {
    await expect(this.page.getByText(topicName, { exact: false }).first()).toBeVisible();
  }
}
