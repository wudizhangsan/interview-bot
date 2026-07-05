<script setup lang="ts">
import { ref, onMounted } from "vue";
import { listTopics, getTopic, createTopic, deleteTopic } from "../api/index";

// ── State ──
const topics = ref<Record<string, number>>({});
const loading = ref(false);
const error = ref("");

// create form
const topicName = ref("");
const topicText = ref("");
const topicFile = ref<File | null>(null);
const creating = ref(false);

// detail view
const selectedTopic = ref("");
const topicQuestions = ref<Array<{ question: string; answer: string }>>([]);
const detailLoading = ref(false);

// ── Methods ──

async function loadTopics() {
  loading.value = true;
  error.value = "";
  try {
    topics.value = await listTopics();
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e.message || "加载知识库列表失败";
  } finally {
    loading.value = false;
  }
}

async function handleCreate() {
  if (!topicName.value.trim()) return;
  creating.value = true;
  error.value = "";
  try {
    await createTopic(topicName.value.trim(), topicText.value, topicFile.value || undefined);
    topicName.value = "";
    topicText.value = "";
    topicFile.value = null;
    await loadTopics();
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e.message || "创建知识库失败";
  } finally {
    creating.value = false;
  }
}

async function handleDelete(name: string) {
  if (!confirm(`确定删除知识库「${name}」吗？`)) return;
  try {
    await deleteTopic(name);
    if (selectedTopic.value === name) {
      selectedTopic.value = "";
      topicQuestions.value = [];
    }
    await loadTopics();
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e.message || "删除失败";
  }
}

async function handleSelect(name: string) {
  if (selectedTopic.value === name) {
    selectedTopic.value = "";
    topicQuestions.value = [];
    return;
  }
  selectedTopic.value = name;
  detailLoading.value = true;
  try {
    const res = await getTopic(name);
    topicQuestions.value = res.questions;
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e.message || "加载详情失败";
  } finally {
    detailLoading.value = false;
  }
}

function handleFileChange(e: Event) {
  const input = e.target as HTMLInputElement;
  topicFile.value = input.files?.[0] || null;
}

onMounted(loadTopics);
</script>

<template>
  <div class="knowledge-page">
    <div class="card">
      <div class="card-title">创建知识库</div>
      <div class="form-group">
        <label class="form-label">主题名称</label>
        <input
          v-model="topicName"
          class="form-input"
          placeholder="例如：Python并发编程"
        />
      </div>
      <div class="form-group">
        <label class="form-label">文本内容（可选）</label>
        <textarea
          v-model="topicText"
          class="form-textarea"
          placeholder="直接输入相关知识点文本…"
          rows="4"
        />
      </div>
      <div class="form-group">
        <label class="form-label">上传文件（可选，PDF/DOCX）</label>
        <input type="file" accept=".pdf,.docx" @change="handleFileChange" />
      </div>
      <button
        class="btn btn-primary"
        :disabled="creating || !topicName.trim()"
        @click="handleCreate"
      >
        {{ creating ? "生成中…" : "生成题库" }}
      </button>
    </div>

    <!-- Error -->
    <div v-if="error" class="card" style="border-left: 4px solid var(--color-danger);">
      <p style="color: var(--color-danger); font-size: 14px;">{{ error }}</p>
    </div>

    <!-- Topic List -->
    <div class="card">
      <div class="card-title">知识库列表</div>

      <div v-if="loading" class="loading">
        <div class="spinner" />
        <p style="margin-top: 8px;">加载中…</p>
      </div>

      <div v-else-if="Object.keys(topics).length === 0" class="text-center text-secondary" style="padding: 24px;">
        暂无知识库，请创建
      </div>

      <ul v-else class="topic-list">
        <li
          v-for="(count, name) in topics"
          :key="name"
          class="topic-item"
          :class="{ selected: selectedTopic === name }"
        >
          <div class="topic-info" @click="handleSelect(name)" style="cursor: pointer; flex: 1;">
            <span class="topic-name">{{ name }}</span>
            <span class="topic-count">{{ count }} 题</span>
          </div>
          <div class="topic-actions">
            <button class="btn btn-sm btn-outline" @click="handleSelect(name)">
              {{ selectedTopic === name ? "收起" : "查看" }}
            </button>
            <button class="btn btn-sm btn-danger" @click="handleDelete(name)">删除</button>
          </div>
        </li>
      </ul>
    </div>

    <!-- Topic Detail -->
    <div v-if="selectedTopic && detailLoading" class="card">
      <div class="loading">
        <div class="spinner" />
      </div>
    </div>

    <div v-if="selectedTopic && topicQuestions.length > 0 && !detailLoading" class="card">
      <div class="card-title">{{ selectedTopic }} — 题目列表</div>
      <div
        v-for="(q, idx) in topicQuestions"
        :key="idx"
        style="padding: 10px 0; border-bottom: 1px solid var(--color-border);"
      >
        <p style="font-weight: 500; margin-bottom: 4px;">
          <strong>Q{{ idx + 1 }}:</strong> {{ q.question }}
        </p>
        <p class="text-secondary" style="white-space: pre-wrap;">
          <strong>A:</strong> {{ q.answer }}
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.topic-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.topic-item.selected {
  background: var(--color-primary-light);
  border-radius: var(--radius);
}
</style>
