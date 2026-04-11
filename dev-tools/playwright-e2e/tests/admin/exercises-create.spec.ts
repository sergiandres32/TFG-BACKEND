// spec: specs/exercises_create_test_plan.md
// input: tests/seed.spec.ts
// tests\admin\exercises-create.spec.ts

import { test } from '../../fixtures/admin-fixtures';

test.describe('Exercises - creación manual y por JSON', () => {
  test.beforeEach(async ({ loginPage, dashboardPage }) => {
    await loginPage.goto('/');
    await loginPage.waitReady();
    await loginPage.login(
      process.env.STREAMLIT_TEACHER_USER ?? 'profesor_seed',
      process.env.STREAMLIT_TEACHER_PASS ?? 'profesor123'
    );
    await dashboardPage.waitReady();
  });

  test('crear exercise con interfaz auxiliar (manual)', async ({ topicsPage, exercisesPage }) => {
    const suffix = Date.now();
    const topicName = `pw_exercise_topic_manual_${suffix}`;
    const exerciseTitle = `pw_exercise_manual_${suffix}`;

    await topicsPage.waitReady();
    await topicsPage.createTopic(topicName, 'Topic per exercici manual', '1.0');
    await topicsPage.expectTopicVisible(topicName);

    await exercisesPage.waitReady();
    await exercisesPage.createExercise(exerciseTitle, 'Exercici creat manualment', topicName);
    await exercisesPage.expectExerciseVisible(exerciseTitle);
  });

  test('crear exercise con importador JSON', async ({ topicsPage, exercisesPage }) => {
    const suffix = Date.now();
    const topicName = `pw_exercise_topic_json_${suffix}`;
    const exerciseTitle = `pw_exercise_json_${suffix}`;
    const rawJson = JSON.stringify([
      {
        title: exerciseTitle,
        description: 'Exercici creat des de JSON',
        level: 'beginner',
        is_required: false,
        topic_name: topicName,
      },
    ]);

    await topicsPage.waitReady();
    await topicsPage.createTopic(topicName, 'Topic per exercici JSON', '1.0');
    await topicsPage.expectTopicVisible(topicName);

    await exercisesPage.waitReady();
    await exercisesPage.openJsonImportMode();
    await exercisesPage.importExercisesFromJson(rawJson);
    await exercisesPage.expectExerciseVisible(exerciseTitle);
  });
});