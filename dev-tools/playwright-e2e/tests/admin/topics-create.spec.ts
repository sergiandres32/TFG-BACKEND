// spec: specs/topics_create_test_plan.md
// input: tests/seed.spec.ts
// tests\admin\topics-create.spec.ts

import { test } from '../../fixtures/admin-fixtures';

test.describe('Topics - creación manual y por JSON', () => {
  test.beforeEach(async ({ loginPage, dashboardPage }) => {
    await loginPage.goto('/');
    await loginPage.waitReady();
    await loginPage.login(
      process.env.STREAMLIT_TEACHER_USER ?? 'profesor_seed',
      process.env.STREAMLIT_TEACHER_PASS ?? 'profesor123'
    );
    await dashboardPage.waitReady();
  });

  test('crear topic con interfaz auxiliar (manual)', async ({ topicsPage }) => {
    const topicName = `pw_manual_topic_${Date.now()}`;

    await topicsPage.waitReady();
    await topicsPage.createTopic(topicName, 'Creat des de Playwright manual', '1.0');
    await topicsPage.expectTopicVisible(topicName);
  });

  test('crear topic con importador JSON', async ({ topicsPage }) => {
    const topicName = `pw_json_topic_${Date.now()}`;
    const rawJson = JSON.stringify([
      {
        name: topicName,
        description: 'Creat des de Playwright JSON',
        weight: 1.2,
        required_beginner: 0,
        required_mid: 0,
        required_expert: 0,
      },
    ]);

    await topicsPage.waitReady();
    await topicsPage.openJsonImportMode();
    await topicsPage.importTopicsFromJson(rawJson);
    await topicsPage.expectTopicVisible(topicName);
  });
});
