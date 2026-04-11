import { expect, Locator, Page } from '@playwright/test';

import { TableActions } from '../components/TableActions';
import { BasePage } from './BasePage';

export class ExercisesPage extends BasePage {
  readonly heading: Locator;
  readonly titleField: Locator;
  readonly descriptionField: Locator;
  readonly levelSelect: Locator;
  readonly requiredCheckbox: Locator;
  readonly topicSelect: Locator;
  readonly createButton: Locator;
  readonly importJsonToggleButton: Locator;
  readonly jsonInput: Locator;
  readonly importExercisesButton: Locator;
  readonly actions: TableActions;

  constructor(page: Page) {
    super(page);
    this.heading = this.page.getByRole('heading', { name: 'Crear exercici' });
    this.titleField = this.page.getByLabel('Títol', { exact: true });
    this.descriptionField = this.page.getByLabel("Descripció de l'exercici", { exact: true });
    this.levelSelect = this.page.getByLabel('Nivell', { exact: true });
    this.requiredCheckbox = this.page.getByLabel('Exercici obligatori', { exact: true });
    this.topicSelect = this.page.getByLabel('Tema', { exact: true });
    this.createButton = this.page.getByRole('button', { name: 'Crear exercici', exact: true });
    this.importJsonToggleButton = this.page.getByRole('button', { name: 'Importar des de JSON' }).nth(2);
    this.jsonInput = this.page.getByLabel("JSON d'exercicis", { exact: true });
    this.importExercisesButton = this.page.getByRole('button', { name: 'Importar exercicis', exact: true });
    this.actions = new TableActions(page);
  }

  async waitReady(): Promise<void> {
    await expect(this.heading).toBeVisible();
  }

  async createExercise(title: string, description: string, topicName: string, level = 'beginner'): Promise<void> {
    await this.titleField.fill(title);
    await this.descriptionField.fill(description);
    await this.selectOptionByLabel('Nivell', level);
    await this.selectOptionByLabel('Tema', topicName);
    await this.createButton.click();
  }

  async openJsonImportMode(): Promise<void> {
    await this.importJsonToggleButton.click();
    await expect(this.jsonInput).toBeVisible();
  }

  async importExercisesFromJson(rawJson: string): Promise<void> {
    await this.jsonInput.fill(rawJson);
    await this.importExercisesButton.click();
  }

  async expectExerciseVisible(title: string): Promise<void> {
    await expect(this.page.getByText(title, { exact: false }).first()).toBeVisible();
  }
}
