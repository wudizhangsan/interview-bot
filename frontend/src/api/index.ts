import axios from "axios";

const http = axios.create({
  baseURL: "/api",
  timeout: 120000,
});

// ── 面试 API ──

export async function createSession(
  resume: string,
  jd: string,
  numQuestions: number = 5,
  style: string = "technical",
  difficulty: string = "medium"
): Promise<{ session_id: string; num_questions: number; status: string }> {
  const { data } = await http.post("/interview/sessions", {
    resume,
    jd,
    num_questions: numQuestions,
    style,
    difficulty,
  });
  return data;
}

export async function askQuestion(
  sessionId: string
): Promise<{
  session_id: string;
  question: string;
  round_index: number;
  total: number;
}> {
  const { data } = await http.post(`/interview/sessions/${sessionId}/ask`);
  return data;
}

export async function submitAnswer(
  sessionId: string,
  answer: string
): Promise<{ message: string }> {
  const { data } = await http.post(`/interview/sessions/${sessionId}/answer`, {
    answer,
  });
  return data;
}

export async function checkFollowUp(
  sessionId: string
): Promise<{ needs_follow_up: boolean; question: string | null }> {
  const { data } = await http.get(`/interview/sessions/${sessionId}/follow-up`);
  return data;
}

export async function skipFollowUp(
  sessionId: string
): Promise<{ message: string }> {
  const { data } = await http.post(
    `/interview/sessions/${sessionId}/skip-follow-up`
  );
  return data;
}

export async function autoAnswer(
  sessionId: string,
  level: string = "mid"
): Promise<{ answer: string }> {
  const { data } = await http.post(
    `/interview/sessions/${sessionId}/auto-answer`,
    { level }
  );
  return data;
}

export async function evaluateRound(
  sessionId: string
): Promise<Record<string, unknown>> {
  const { data } = await http.post(
    `/interview/sessions/${sessionId}/evaluate-round`
  );
  return data;
}

export async function finishInterview(
  sessionId: string
): Promise<Record<string, unknown>> {
  const { data } = await http.post(
    `/interview/sessions/${sessionId}/finish`
  );
  return data;
}

export async function getState(
  sessionId: string
): Promise<Record<string, unknown>> {
  const { data } = await http.get(`/interview/sessions/${sessionId}/state`);
  return data;
}

export async function deleteSession(
  sessionId: string
): Promise<{ message: string }> {
  const { data } = await http.delete(
    `/interview/sessions/${sessionId}`
  );
  return data;
}

// ── 知识库 API ──

export async function listTopics(): Promise<Record<string, number>> {
  const { data } = await http.get("/kb/topics");
  return data;
}

export async function getTopic(
  topicName: string
): Promise<{ topic: string; questions: Array<{ question: string; answer: string }> }> {
  const { data } = await http.get(`/kb/topics/${encodeURIComponent(topicName)}`);
  return data;
}

export async function createTopic(
  topicName: string,
  text: string,
  file?: File
): Promise<{
  topic: string;
  question_count: number;
  questions: Array<{ question: string; answer: string }>;
}> {
  const form = new FormData();
  form.append("topic_name", topicName);
  if (file) {
    form.append("file", file);
  }
  if (text) {
    form.append("text", text);
  }
  const { data } = await http.post("/kb/topics", form);
  return data;
}

export async function deleteTopic(
  topicName: string
): Promise<{ message: string }> {
  const { data } = await http.delete(`/kb/topics/${encodeURIComponent(topicName)}`);
  return data;
}

// ── 文件解析 API ──

export async function parseFile(file: File): Promise<{ text: string }> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await http.post("/parse-file", form);
  return data;
}
