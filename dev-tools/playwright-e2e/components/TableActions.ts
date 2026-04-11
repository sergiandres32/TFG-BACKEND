import { Locator, Page } from '@playwright/test';

export class TableActions {
  readonly saveButton: Locator;
  readonly importJsonButton: Locator;
  readonly deleteSelectedButton: Locator;

  constructor(private readonly page: Page) {
    this.saveButton = this.page.getByRole('button', { name: 'Guardar' });
    this.importJsonButton = this.page.getByRole('button', { name: 'Importar des de JSON' });
    this.deleteSelectedButton = this.page.getByRole('button', { name: 'Eliminar seleccionats' });
  }

  async save(): Promise<void> {
    await this.saveButton.click();
  }

  async importFromJson(): Promise<void> {
    await this.importJsonButton.click();
  }

  async deleteSelected(): Promise<void> {
    await this.deleteSelectedButton.click();
  }
}
