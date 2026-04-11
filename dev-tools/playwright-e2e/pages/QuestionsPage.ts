import { expect, Locator, Page } from '@playwright/test';

import { TableActions } from '../components/TableActions';
import { BasePage } from './BasePage';

export class QuestionsPage extends BasePage {
  readonly heading: Locator;
  readonly topicSelector: Locator;
  readonly optionsCountField: Locator;
  readonly statementField: Locator;
  readonly levelSelect: Locator;
  readonly requiredCheckbox: Locator;
  readonly createButton: Locator;
  readonly importJsonToggleButton: Locator;
  readonly jsonInput: Locator;
  readonly importQuestionsButton: Locator;
  readonly createdSuccessMessage: Locator;
  readonly actions: TableActions;

  constructor(page: Page) {
    super(page);
    this.heading = this.page.getByRole('heading', { name: 'Crear pregunta tipus test' });
    this.topicSelector = this.page.getByLabel('Tema de les preguntes', { exact: true });
    this.optionsCountField = this.page.getByLabel("Nombre d'opcions de la nova pregunta", { exact: true });
    this.statementField = this.page.getByLabel('Enunciat', { exact: true });
    this.levelSelect = this.page.getByLabel('Nivell pregunta', { exact: true });
    this.requiredCheckbox = this.page.getByLabel('Pregunta obligatòria', { exact: true });
    this.createButton = this.page.getByRole('button', { name: 'Crear pregunta', exact: true });
    this.importJsonToggleButton = this.page.getByRole('button', { name: 'Importar des de JSON' }).nth(1);
    this.jsonInput = this.page.getByLabel('JSON de preguntes', { exact: true });
    this.importQuestionsButton = this.page.getByRole('button', { name: 'Importar preguntes', exact: true });
    this.createdSuccessMessage = this.page.getByText('Pregunta tipus test creada.', { exact: true });
    this.actions = new TableActions(page);
  }

  async waitReady(): Promise<void> {
    await expect(this.heading).toBeVisible();
  }

  async selectTopic(topicName: string): Promise<void> {
    await this.selectOptionByLabel('Tema de les preguntes', topicName);
  }

  async createQuestion(statement: string, options: string[], level = 'beginner'): Promise<void> {
    await this.optionsCountField.fill(String(options.length));
    await this.statementField.fill(statement);
    await this.selectOptionByLabel('Nivell pregunta', level);

    for (const [index, option] of options.entries()) {
      await this.page.getByLabel(`Opció ${index + 1}`, { exact: true }).fill(option);
    }

    await this.selectOptionByLabel('Opció correcta', 'Opció 1');
    await this.createButton.click();
  }

  async openJsonImportMode(): Promise<void> {
    await this.importJsonToggleButton.click();
    await expect(this.jsonInput).toBeVisible();
  }

  async importQuestionsFromJson(rawJson: string): Promise<void> {
    await this.jsonInput.fill(rawJson);
    await this.importQuestionsButton.click();
  }

  async expectQuestionVisible(statement: string): Promise<void> {
    const questionCells = this.page.getByText(statement, { exact: false });
    expect(await questionCells.count()).toBeGreaterThan(0);
  }

  async expectCreationSuccessMessage(): Promise<void> {
    await expect(this.createdSuccessMessage).toBeVisible();
  }
}
