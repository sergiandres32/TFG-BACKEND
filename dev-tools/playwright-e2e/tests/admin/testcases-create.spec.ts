// spec: specs/testcases_create_test_plan.md
// input: tests/seed.spec.ts
// tests\admin\testcases-create.spec.ts

import { test } from '../../fixtures/admin-fixtures';
import { seedTopicAndExercise, type SeededTopicExercise } from '../../support/adminApi';

test.describe('Test cases - creación manual y por JSON', () => {
  let seeded: SeededTopicExercise;

  test.beforeEach(async ({ loginPage, dashboardPage, request }, testInfo) => {
    const suffix = `${Date.now()}_${testInfo.retry}_${testInfo.parallelIndex}`;

    seeded = await seedTopicAndExercise(request, {
      topicName: `pw_testcase_topic_${suffix}`,
      topicDescription: 'Topic seedat per API per a jocs de prova',
      exerciseTitle: `pw_testcase_exercise_${suffix}`,
      exerciseDescription: 'Exercici seedat per API per a jocs de prova',
    });

    await loginPage.goto('/');
    await loginPage.waitReady();
    await loginPage.login(
      process.env.STREAMLIT_TEACHER_USER ?? 'profesor_seed',
      process.env.STREAMLIT_TEACHER_PASS ?? 'profesor123'
    );
    await dashboardPage.waitReady();
  });

  test('crear joc de prova con interfaz auxiliar (manual)', async ({ testCasesPage }) => {
    const suffix = Date.now();
    const testCaseName = `pw_testcase_manual_${suffix}`;

    await testCasesPage.waitReady();
    await testCasesPage.selectExercise(seeded.exerciseTitle);
    await testCasesPage.createTestCase(testCaseName, '2 3\n', '5\n');
    await testCasesPage.expectCreationSuccessMessage(testCaseName);
  });

  test('crear joc de prova con importador JSON', async ({ testCasesPage }) => {
    const suffix = Date.now();
    const testCaseName = `pw_testcase_json_${suffix}`;
    const rawJson = JSON.stringify([
      {
        name: testCaseName,
        content: {
          input: '10 30\\n',
          expected: '40\\n',
          mode: 'exact',
          ignore_whitespace: false,
        },
      },
    ]);

    await testCasesPage.waitReady();
    await testCasesPage.selectExercise(seeded.exerciseTitle);
    await testCasesPage.openJsonImportMode();
    await testCasesPage.importTestCasesFromJson(rawJson);
    await testCasesPage.expectTestCaseVisible(testCaseName);
  });
});