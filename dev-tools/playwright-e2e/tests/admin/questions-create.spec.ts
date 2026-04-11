// spec: specs/questions_create_test_plan.md
// input: tests/seed.spec.ts
// tests\admin\questions-create.spec.ts

import { test } from '../../fixtures/admin-fixtures';

test.describe('Questions - creación manual y por JSON', () => {
  test.beforeEach(async ({ loginPage, dashboardPage }) => {
    await loginPage.goto('/');
    await loginPage.waitReady();
    await loginPage.login(
      process.env.STREAMLIT_TEACHER_USER ?? 'profesor_seed',
      process.env.STREAMLIT_TEACHER_PASS ?? 'profesor123'
    );
    await dashboardPage.waitReady();
  });

  test('crear question con interfaz auxiliar (manual)', async ({ topicsPage, questionsPage }) => {
    const suffix = Date.now();
    const topicName = `pw_question_topic_manual_${suffix}`;
    const statement = `pw_question_manual_${suffix}`;

    await topicsPage.waitReady();
    await topicsPage.createTopic(topicName, 'Topic per pregunta manual', '1.0');
    await topicsPage.expectTopicVisible(topicName);

    await questionsPage.waitReady();
    await questionsPage.selectTopic(topicName);
    await questionsPage.createQuestion(statement, ['Opció A', 'Opció B', 'Opció C', 'Opció D']);
    await questionsPage.expectCreationSuccessMessage();
  });

  test('crear question con importador JSON', async ({ topicsPage, questionsPage }) => {
    const suffix = Date.now();
    const topicName = `pw_question_topic_json_${suffix}`;
    const statement = `pw_question_json_${suffix}`;
    const rawJson = JSON.stringify([
      {
        level: 'beginner',
        statement,
        options: ['JSON A', 'JSON B', 'JSON C', 'JSON D'],
        correct_option_index: 0,
        is_required: false,
      },
    ]);

    await topicsPage.waitReady();
    await topicsPage.createTopic(topicName, 'Topic per pregunta JSON', '1.0');
    await topicsPage.expectTopicVisible(topicName);

    await questionsPage.waitReady();
    await questionsPage.selectTopic(topicName);
    await questionsPage.openJsonImportMode();
    await questionsPage.importQuestionsFromJson(rawJson);
    await questionsPage.expectQuestionVisible(statement);
  });
});