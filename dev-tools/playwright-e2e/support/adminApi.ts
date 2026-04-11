import { APIRequestContext, expect } from '@playwright/test';

export type SeededTopicExercise = {
  topicId: number;
  topicName: string;
  exerciseId: number;
  exerciseTitle: string;
};

function getApiBaseUrl(): string {
  return process.env.API_URL ?? process.env.STREAMLIT_API_URL ?? 'http://localhost:8000';
}

function getTeacherCredentials(): { username: string; password: string } {
  return {
    username: process.env.STREAMLIT_TEACHER_USER ?? 'profesor_seed',
    password: process.env.STREAMLIT_TEACHER_PASS ?? 'profesor123',
  };
}

export async function loginTeacher(api: APIRequestContext): Promise<string> {
  const { username, password } = getTeacherCredentials();

  const response = await api.post(`${getApiBaseUrl()}/token`, {
    form: { username, password },
  });

  expect(response.ok()).toBeTruthy();
  const payload = await response.json();
  expect(payload.access_token).toBeTruthy();
  return payload.access_token as string;
}

export async function seedTopicAndExercise(
  api: APIRequestContext,
  data: { topicName: string; topicDescription: string; exerciseTitle: string; exerciseDescription: string }
): Promise<SeededTopicExercise> {
  const token = await loginTeacher(api);
  const headers = {
    Authorization: `Bearer ${token}`,
  };

  const topicResponse = await api.post(`${getApiBaseUrl()}/topics`, {
    headers,
    data: {
      name: data.topicName,
      description: data.topicDescription,
      required_beginner: 0,
      required_mid: 0,
      required_expert: 0,
    },
  });

  expect(topicResponse.ok()).toBeTruthy();
  const topicPayload = await topicResponse.json();

  const exerciseResponse = await api.post(`${getApiBaseUrl()}/exercises`, {
    headers,
    data: {
      topic_id: topicPayload.id,
      title: data.exerciseTitle,
      description: data.exerciseDescription,
      level: 'beginner',
      is_required: false,
    },
  });

  expect(exerciseResponse.ok()).toBeTruthy();
  const exercisePayload = await exerciseResponse.json();

  return {
    topicId: topicPayload.id,
    topicName: data.topicName,
    exerciseId: exercisePayload.id,
    exerciseTitle: data.exerciseTitle,
  };
}