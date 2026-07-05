<script setup lang="ts">
defineProps<{
  evaluation: {
    question: string;
    score: number;
    highlights: string;
    missing_points: string;
    improvement: string;
  };
}>();
</script>

<template>
  <div class="evaluation-card card">
    <div class="card-title">评价结果</div>
    <div class="eval-section">
      <span class="eval-label">题目</span>
      <p class="eval-text">{{ evaluation.question }}</p>
    </div>
    <div class="eval-section">
      <span class="eval-label">评分</span>
      <div class="eval-score">
        <span class="score-value">{{ evaluation.score }}</span>
        <span class="score-max">/ 5</span>
      </div>
    </div>
    <div v-if="evaluation.highlights" class="eval-section">
      <span class="eval-label">亮点</span>
      <p class="eval-text positive">{{ evaluation.highlights }}</p>
    </div>
    <div v-if="evaluation.missing_points" class="eval-section">
      <span class="eval-label">缺失要点</span>
      <p class="eval-text negative">{{ evaluation.missing_points }}</p>
    </div>
    <div v-if="evaluation.improvement" class="eval-section">
      <span class="eval-label">改进建议</span>
      <p class="eval-text">{{ evaluation.improvement }}</p>
    </div>
  </div>
</template>

<style scoped>
.evaluation-card {
  align-self: center;
  max-width: 100%;
  width: 100%;
  background: #f8fafc;
  border: 1px solid var(--color-border);
}

.eval-section {
  margin-bottom: 10px;
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

.eval-text.positive {
  color: #16a34a;
}

.eval-text.negative {
  color: #dc2626;
}

.eval-score {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.score-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--color-primary);
}

.score-max {
  font-size: 16px;
  color: var(--color-text-secondary);
}
</style>
