<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted } from "vue";
import ChatMessage from "../components/ChatMessage.vue";
import EvaluationCard from "../components/EvaluationCard.vue";
import {
  createSession,
  askQuestion,
  submitAnswer,
  checkFollowUp,
  skipFollowUp,
  autoAnswer,
  finishInterview,
  parseFile,
} from "../api/index";

// ── Chat message type ──
type Msg =
  | { type: "system"; content: string }
  | { type: "question"; content: string }
  | { type: "answer"; role: "user" | "candidate"; content: string }
  | { type: "follow_up"; content: string }
  | { type: "drill_answer"; role: "user" | "candidate"; content: string }
  | { type: "evaluation"; data: any }
  | { type: "final_evaluation"; data: any };

// ── State ──
const mode = ref<"manual" | "ai">("manual");
const phase = ref<
  | "idle"
  | "starting"
  | "question"
  | "answering"
  | "checking_followup"
  | "follow_up"
  | "drill_answering"
  | "answered"
  | "finished"
>("idle");

const sessionId = ref("");
const resume = ref("");
const jd = ref("");
const numQuestions = ref(5);
const answerText = ref("");
const drillAnswerText = ref("");
const totalQuestions = ref(0);
const currentRound = ref(0);
const messages = ref<Msg[]>([]);
const loading = ref(false);
const error = ref("");
const chatEl = ref<HTMLElement | null>(null);

// ── Resume file upload ──
const parsingFile = ref(false);

// ── Time tracking ──
const interviewStartTime = ref(0);
const questionStartTime = ref(0);
const totalElapsed = ref("00:00");
const currentElapsed = ref("00:00");
let timerHandle: ReturnType<typeof setInterval> | null = null;

function startTimer() {
  interviewStartTime.value = Date.now();
  questionStartTime.value = Date.now();
  timerHandle = setInterval(() => {
    const now = Date.now();
    const totalSec = Math.floor((now - interviewStartTime.value) / 1000);
    const curSec = Math.floor((now - questionStartTime.value) / 1000);
    totalElapsed.value = formatTime(totalSec);
    currentElapsed.value = formatTime(curSec);
  }, 1000);
}

function resetQuestionTimer() {
  questionStartTime.value = Date.now();
}

function stopTimer() {
  if (timerHandle) {
    clearInterval(timerHandle);
    timerHandle = null;
  }
}

function formatTime(sec: number): string {
  const m = String(Math.floor(sec / 60)).padStart(2, "0");
  const s = String(sec % 60).padStart(2, "0");
  return `${m}:${s}`;
}

// ── File upload handler ──
async function handleResumeFile(e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  parsingFile.value = true;
  try {
    const res = await parseFile(file);
    resume.value = res.text;
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err.message || "文件解析失败";
  } finally {
    parsingFile.value = false;
    input.value = "";
  }
}

const isStarting = computed(() => phase.value === "starting");
const hasSession = computed(() => !!sessionId.value);
const isFinished = computed(() => phase.value === "finished");

// ── Scroll to bottom ──
async function scrollBottom() {
  await nextTick();
  if (chatEl.value) {
    chatEl.value.scrollTop = chatEl.value.scrollHeight;
  }
}

// ── Add message helpers ──
function addSystem(text: string) {
  messages.value.push({ type: "system", content: text });
  scrollBottom();
}

function addQuestion(text: string) {
  messages.value.push({ type: "question", content: text });
  scrollBottom();
}

function addAnswer(role: "user" | "candidate", text: string) {
  messages.value.push({ type: "answer", role, content: text });
  scrollBottom();
}

function addFollowUp(text: string) {
  messages.value.push({ type: "follow_up", content: text });
  scrollBottom();
}

function addDrillAnswer(role: "user" | "candidate", text: string) {
  messages.value.push({ type: "drill_answer", role, content: text });
  scrollBottom();
}

function addFinalEvaluation(data: any) {
  messages.value.push({ type: "final_evaluation", data });
  scrollBottom();
}

// ── Core interview flow ──

async function startInterview() {
  if (!resume.value.trim() || !jd.value.trim()) {
    error.value = "请填写简历和岗位描述";
    return;
  }
  error.value = "";
  phase.value = "starting";
  loading.value = true;
  messages.value = [];
  currentRound.value = 0;
  startTimer();

  try {
    const res = await createSession(
      resume.value,
      jd.value,
      numQuestions.value
    );
    sessionId.value = res.session_id;
    totalQuestions.value = res.num_questions;
    addSystem(
      `面试已创建，共 ${res.num_questions} 道题目，模式：${mode.value === "manual" ? "人工回答" : "AI 自动回答"}`
    );
    await doAsk();
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e.message || "创建面试失败";
    phase.value = "idle";
  } finally {
    loading.value = false;
  }
}

async function doAsk() {
  if (!sessionId.value) return;
  phase.value = "question";
  loading.value = true;
  try {
    const res = await askQuestion(sessionId.value);
    currentRound.value = res.round_index;
    resetQuestionTimer();
    addQuestion(res.question);

    if (mode.value === "ai") {
      await doAutoAnswer();
    } else {
      phase.value = "answering";
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e.message || "获取题目失败";
  } finally {
    loading.value = false;
  }
}

async function doAutoAnswer() {
  if (!sessionId.value) return;
  phase.value = "answering";
  loading.value = true;
  try {
    const res = await autoAnswer(sessionId.value);
    addAnswer("candidate", res.answer);
    await doCheckFollowUp();
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e.message || "自动回答失败";
  } finally {
    loading.value = false;
  }
}

async function submitManualAnswer() {
  if (!sessionId.value || !answerText.value.trim()) return;
  loading.value = true;
  const text = answerText.value.trim();
  answerText.value = "";
  try {
    await submitAnswer(sessionId.value, text);
    addAnswer("user", text);
    await doCheckFollowUp();
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e.message || "提交回答失败";
  } finally {
    loading.value = false;
  }
}

async function doCheckFollowUp() {
  if (!sessionId.value) return;
  phase.value = "checking_followup";
  loading.value = true;
  try {
    const res = await checkFollowUp(sessionId.value);
    if (res.needs_follow_up && res.question) {
      addFollowUp(res.question);
      if (mode.value === "ai") {
        await doAutoDrillAnswer();
      } else {
        phase.value = "follow_up";
        drillAnswerText.value = "";
      }
    } else {
      await goToNextOrFinish();
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e.message || "检查追问失败";
    // Try skipping follow-up and evaluating
    try {
      await skipFollowUp(sessionId.value);
      await goToNextOrFinish();
    } catch {
      phase.value = "question";
    }
  } finally {
    loading.value = false;
  }
}

async function doAutoDrillAnswer() {
  if (!sessionId.value) return;
  phase.value = "drill_answering";
  loading.value = true;
  try {
    const res = await autoAnswer(sessionId.value);
    addDrillAnswer("candidate", res.answer);
    await goToNextOrFinish();
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e.message || "自动回答追问失败";
  } finally {
    loading.value = false;
  }
}

async function submitManualDrillAnswer() {
  if (!sessionId.value || !drillAnswerText.value.trim()) return;
  loading.value = true;
  const text = drillAnswerText.value.trim();
  drillAnswerText.value = "";
  try {
    await submitAnswer(sessionId.value, text);
    addDrillAnswer("user", text);
    await goToNextOrFinish();
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e.message || "提交追问回答失败";
  } finally {
    loading.value = false;
  }
}

async function doSkipFollowUp() {
  if (!sessionId.value) return;
  loading.value = true;
  try {
    await skipFollowUp(sessionId.value);
    await goToNextOrFinish();
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e.message || "跳过追问失败";
  } finally {
    loading.value = false;
  }
}

async function goToNextOrFinish() {
  if (mode.value === "ai") {
    await doNextQuestion();
  } else {
    phase.value = "answered";
  }
}

async function doNextQuestion() {
  if (currentRound.value < totalQuestions.value - 1) {
    await doAsk();
  } else {
    await doFinish();
  }
}

async function doFinish() {
  if (!sessionId.value) return;
  stopTimer();
  loading.value = true;
  try {
    const finalEval = await finishInterview(sessionId.value);
    addSystem("面试结束，以下是综合评价报告：");
    addFinalEvaluation(finalEval);
    phase.value = "finished";
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e.message || "生成评价失败";
  } finally {
    loading.value = false;
  }
}

function resetInterview() {
  stopTimer();
  sessionId.value = "";
  messages.value = [];
  phase.value = "idle";
  currentRound.value = 0;
  totalQuestions.value = 0;
  error.value = "";
  totalElapsed.value = "00:00";
  currentElapsed.value = "00:00";
}

onUnmounted(() => {
  stopTimer();
});
</script>

<template>
  <div class="interview-page">
    <!-- Phase: idle — config form -->
    <div v-if="phase === 'idle'" class="card">
      <div class="card-title">开始模拟面试</div>

      <div class="mode-toggle">
        <button
          class="mode-btn"
          :class="{ active: mode === 'manual' }"
          @click="mode = 'manual'"
        >
          人工回答
        </button>
        <button
          class="mode-btn"
          :class="{ active: mode === 'ai' }"
          @click="mode = 'ai'"
        >
          AI 自动回答
        </button>
      </div>

      <div class="form-group">
        <label class="form-label">简历内容</label>
        <textarea
          v-model="resume"
          class="form-textarea"
          placeholder="粘贴简历文本..."
          rows="6"
        />
        <div class="file-upload-row">
          <input
            type="file"
            accept=".pdf,.docx"
            @change="handleResumeFile"
            id="resume-file-input"
          />
          <label for="resume-file-input" class="btn btn-sm btn-outline">
            上传简历文件
          </label>
          <span v-if="parsingFile" class="text-secondary">解析中…</span>
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">岗位描述 (JD)</label>
        <textarea
          v-model="jd"
          class="form-textarea"
          placeholder="粘贴岗位描述..."
          rows="6"
        />
      </div>
      <div class="form-group">
        <label class="form-label">题目数量</label>
        <input
          v-model="numQuestions"
          class="form-input"
          type="number"
          min="1"
          max="20"
          style="width: 100px;"
        />
      </div>
      <button
        class="btn btn-primary"
        :disabled="isStarting || !resume.trim() || !jd.trim()"
        @click="startInterview"
      >
        {{ isStarting ? "初始化中…" : "开始面试" }}
      </button>
    </div>

    <!-- Error display -->
    <div
      v-if="error && phase !== 'idle'"
      class="card"
      style="border-left: 4px solid var(--color-danger); margin-bottom: 12px;"
    >
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <p style="color: var(--color-danger); font-size: 14px;">{{ error }}</p>
        <button class="btn btn-sm btn-outline" @click="error = ''">关闭</button>
      </div>
    </div>

    <!-- Chat interface -->
    <div
      v-if="hasSession || phase !== 'idle'"
      class="card chat-card"
    >
      <!-- Status bar -->
      <div class="chat-status">
        <span v-if="phase !== 'finished'" class="status-badge">
          {{ currentRound + 1 }} / {{ totalQuestions }}
        </span>
        <span v-else class="status-badge finished">面试结束</span>
        <span class="mode-badge">{{ mode === "manual" ? "人工" : "AI" }}模式</span>
        <span class="time-badge" title="总用时">
          ⏱ 总 {{ totalElapsed }}
        </span>
        <span v-if="phase !== 'finished' && phase !== 'idle'" class="time-badge current" title="当前题用时">
          ⏱ 本题 {{ currentElapsed }}
        </span>
        <button
          v-if="!isFinished"
          class="btn btn-sm btn-danger"
          style="margin-left: auto;"
          @click="resetInterview"
        >
          结束
        </button>
      </div>

      <!-- Messages -->
      <div ref="chatEl" class="chat-messages">
        <template v-for="(msg, i) in messages" :key="i">
          <!-- System message -->
          <ChatMessage
            v-if="msg.type === 'system'"
            role="system"
            :content="msg.content"
          />
          <!-- Question -->
          <ChatMessage
            v-else-if="msg.type === 'question'"
            role="interviewer"
            :content="msg.content"
          />
          <!-- Answer -->
          <ChatMessage
            v-else-if="msg.type === 'answer'"
            :role="msg.role"
            :content="msg.content"
          />
          <!-- Follow-up question -->
          <ChatMessage
            v-else-if="msg.type === 'follow_up'"
            role="interviewer"
            :content="msg.content"
          />
          <!-- Drill answer -->
          <ChatMessage
            v-else-if="msg.type === 'drill_answer'"
            :role="msg.role"
            :content="msg.content"
          />
          <!-- Evaluation card -->
          <EvaluationCard
            v-else-if="msg.type === 'evaluation'"
            :evaluation="msg.data as any"
          />
          <!-- Final evaluation -->
          <div
            v-else-if="msg.type === 'final_evaluation'"
            class="final-eval card"
          >
            <div class="card-title">综合评价报告</div>
            <div class="eval-section">
              <span class="eval-label">总分</span>
              <div class="final-score">{{ (msg.data as any).overall_score?.toFixed?.(1) ?? (msg.data as any).overall_score }}/100</div>
            </div>
            <div v-if="(msg.data as any).final_verdict" class="eval-section">
              <span class="eval-label">终期判决</span>
              <p class="eval-text">{{ (msg.data as any).final_verdict }}</p>
            </div>
            <div v-if="(msg.data as any).salary_fit && (msg.data as any).final_verdict !== '淘汰'" class="eval-section">
              <span class="eval-label">薪资建议</span>
              <p class="eval-text">{{ (msg.data as any).salary_fit }}</p>
            </div>
            <div v-if="(msg.data as any).dimensions?.length" class="eval-section">
              <span class="eval-label">各维度评分</span>
              <div
                v-for="(d, di) in (msg.data as any).dimensions"
                :key="di"
                class="dimension-row"
              >
                <span class="dim-name">{{ d.name }}</span>
                <span class="dim-score">{{ d.score?.toFixed?.(1) ?? d.score }}分</span>
                <span class="dim-summary">{{ d.summary }}</span>
              </div>
            </div>
            <div v-if="(msg.data as any).improvement_tips?.length" class="eval-section">
              <span class="eval-label">通关锦囊</span>
              <ul class="tip-list">
                <li v-for="(tip, ti) in (msg.data as any).improvement_tips" :key="ti">
                  {{ tip }}
                </li>
              </ul>
            </div>

            <!-- Per-question evaluations from final report -->
            <div v-if="(msg.data as any).qa_evaluations?.length" class="eval-section">
              <span class="eval-label">逐题评价</span>
              <div
                v-for="(qa, qi) in (msg.data as any).qa_evaluations"
                :key="qi"
                class="suggestion-item"
              >
                <div class="suggestion-q">第 {{ qi + 1 }} 题：{{ qa.question }}</div>
                <div class="eval-sub-score">评分：{{ qa.score }}/5</div>
                <div class="suggestion-text" v-if="qa.improvement">
                  💡 {{ qa.improvement }}
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- Loading indicator -->
        <div v-if="loading" class="loading" style="padding: 12px;">
          <div class="spinner" />
        </div>
      </div>

      <!-- Input area: manual mode -->
      <div v-if="phase === 'answering' && mode === 'manual'" class="chat-input-area">
        <textarea
          v-model="answerText"
          class="form-textarea"
          placeholder="输入你的回答…"
          rows="2"
          @keydown.ctrl.enter="submitManualAnswer"
        />
        <button
          class="btn btn-primary"
          :disabled="loading || !answerText.trim()"
          @click="submitManualAnswer"
        >
          提交回答
        </button>
      </div>

      <!-- Input area: manual drill answer -->
      <div v-if="phase === 'follow_up' && mode === 'manual'" class="chat-input-area">
        <textarea
          v-model="drillAnswerText"
          class="form-textarea"
          placeholder="输入你对追问的回答…"
          rows="2"
          @keydown.ctrl.enter="submitManualDrillAnswer"
        />
        <div style="display: flex; flex-direction: column; gap: 4px;">
          <button
            class="btn btn-primary btn-sm"
            :disabled="loading || !drillAnswerText.trim()"
            @click="submitManualDrillAnswer"
          >
            提交
          </button>
          <button
            class="btn btn-outline btn-sm"
            :disabled="loading"
            @click="doSkipFollowUp"
          >
            跳过追问
          </button>
        </div>
      </div>

      <!-- Manual mode: next question button (after answering) -->
      <div
        v-if="phase === 'answered' && mode === 'manual' && !loading"
        class="chat-input-area"
        style="justify-content: center;"
      >
        <button
          class="btn btn-primary"
          @click="doNextQuestion"
        >
          {{ currentRound < totalQuestions - 1 ? "下一题" : "完成面试" }}
        </button>
      </div>

      <!-- AI mode: loading / auto-flow indicator -->
      <div
        v-if="mode === 'ai' && loading && phase !== 'finished'"
        class="text-center text-secondary"
        style="padding: 8px;"
      >
        AI 处理中…
      </div>

      <!-- Finished: restart -->
      <div
        v-if="isFinished"
        class="chat-input-area"
        style="justify-content: center;"
      >
        <button class="btn btn-primary" @click="resetInterview">
          重新开始
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.interview-page {
  max-width: 720px;
  margin: 0 auto;
}

.chat-card {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 120px);
  padding: 0;
  overflow: hidden;
}

.chat-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--color-border);
  background: #fafbfc;
}

.status-badge {
  font-size: 12px;
  font-weight: 600;
  background: var(--color-primary-light);
  color: var(--color-primary);
  padding: 2px 10px;
  border-radius: 12px;
}

.status-badge.finished {
  background: #dcfce7;
  color: #16a34a;
}

.mode-badge {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.time-badge {
  font-size: 12px;
  color: var(--color-text-secondary);
  background: #f1f5f9;
  padding: 2px 8px;
  border-radius: 10px;
  white-space: nowrap;
}

.time-badge.current {
  background: #fef3c7;
  color: #92400e;
}

.file-upload-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}

.file-upload-row input[type="file"] {
  display: none;
}

.suggestion-item {
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border);
  font-size: 14px;
}

.suggestion-item:last-child {
  border-bottom: none;
}

.suggestion-q {
  font-weight: 500;
  margin-bottom: 2px;
  color: var(--color-text);
}

.suggestion-text {
  color: var(--color-text-secondary);
  line-height: 1.5;
  white-space: pre-wrap;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chat-input-area {
  border-top: 1px solid var(--color-border);
  padding: 12px 16px;
  display: flex;
  gap: 8px;
}

.chat-input-area .form-textarea {
  flex: 1;
  min-height: 40px;
}

/* Final evaluation styles */
.final-eval {
  align-self: center;
  max-width: 100%;
  width: 100%;
  background: #f8fafc;
  border: 1px solid var(--color-border);
}

.final-score {
  font-size: 40px;
  font-weight: 700;
  color: var(--color-primary);
}

.eval-section {
  margin-bottom: 12px;
}

.eval-label {
  display: inline-block;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
  background: var(--color-bg);
  padding: 2px 8px;
  border-radius: 4px;
  margin-bottom: 4px;
}

.eval-text {
  font-size: 14px;
  line-height: 1.5;
  white-space: pre-wrap;
}

.dimension-row {
  display: flex;
  gap: 8px;
  align-items: baseline;
  padding: 4px 0;
  font-size: 14px;
}

.dim-name {
  font-weight: 600;
  min-width: 80px;
}

.dim-score {
  color: var(--color-primary);
  font-weight: 600;
  min-width: 50px;
}

.dim-summary {
  color: var(--color-text-secondary);
}

.tip-list {
  padding-left: 20px;
  font-size: 14px;
}

.tip-list li {
  margin-bottom: 4px;
}
</style>
