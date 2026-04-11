import { expect, Locator, Page } from '@playwright/test';

import { TableActions } from '../components/TableActions';
import { BasePage } from './BasePage';

export class TestCasesPage extends BasePage {
  readonly heading: Locator;
  readonly exerciseSelector: Locator;
  readonly nameField: Locator;
  readonly comparisonModeSelect: Locator;
  readonly inputField: Locator;
  readonly expectedField: Locator;
  readonly ignoreWhitespaceCheckbox: Locator;
  readonly createButton: Locator;
  readonly importJsonToggleButton: Locator;
  readonly jsonInput: Locator;
  readonly importTestCasesButton: Locator;
  readonly createdSuccessMessage: Locator;
  readonly actions: TableActions;

  constructor(page: Page) {
    super(page);
    this.heading = this.page.getByRole('heading', { name: 'Crear joc de prova' });
    this.exerciseSelector = this.page.getByLabel('Exercici per gestionar jocs de prova', { exact: true });
    this.nameField = this.page.getByLabel('Nom del joc de prova', { exact: true });
    this.comparisonModeSelect = this.page.getByLabel('Mode de comparació', { exact: true });
    this.inputField = this.page.getByLabel('Input', { exact: true });
    this.expectedField = this.page.getByLabel('Output esperat', { exact: true });
    this.ignoreWhitespaceCheckbox = this.page.getByLabel('Ignorar espais en blanc', { exact: true });
    this.createButton = this.page.getByRole('button', { name: 'Afegir joc de prova', exact: true });
    this.importJsonToggleButton = this.page.getByRole('button', { name: 'Importar des de JSON' }).nth(3);
    this.jsonInput = this.page.getByLabel('JSON de jocs de prova', { exact: true });
    this.importTestCasesButton = this.page.getByRole('button', { name: 'Importar jocs de prova', exact: true });
    this.createdSuccessMessage = this.page.getByText('Joc de prova creat:', { exact: false });
    this.actions = new TableActions(page);
  }

  async waitReady(): Promise<void> {
    await expect(this.heading).toBeVisible();
  }

  async selectExercise(exerciseTitle: string): Promise<void> {
    await this.selectOptionByLabel('Exercici per gestionar jocs de prova', exerciseTitle);
  }

  async createTestCase(name: string, input: string, expectedOutput: string, mode = 'exact'): Promise<void> {
    await this.nameField.fill(name);
    await this.selectOptionByLabel('Mode de comparació', mode);
    await this.inputField.fill(input);
    await this.expectedField.fill(expectedOutput);
    await this.createButton.click();
  }

  async openJsonImportMode(): Promise<void> {
    await this.importJsonToggleButton.click();
    await expect(this.jsonInput).toBeVisible();
  }

  async importTestCasesFromJson(rawJson: string): Promise<void> {
    await this.jsonInput.fill(rawJson);
    await this.importTestCasesButton.click();
  }

  async expectTestCaseVisible(name: string): Promise<void> {
    await expect(this.page.getByText(name, { exact: false }).first()).toBeVisible();
  }

  async expectCreationSuccessMessage(name: string): Promise<void> {
    await expect(this.page.getByText(`Joc de prova creat: ${name}`, { exact: true })).toBeVisible();
  }
}