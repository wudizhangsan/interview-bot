<script setup lang="ts">
defineProps<{
  role: "system" | "interviewer" | "user" | "candidate";
  content: string;
}>();
</script>

<template>
  <div
    class="chat-message"
    :class="{
      'msg-system': role === 'system',
      'msg-interviewer': role === 'interviewer',
      'msg-user': role === 'user',
      'msg-candidate': role === 'candidate',
    }"
  >
    <div class="msg-label">{{ { system: "系统", interviewer: "面试官", user: "我", candidate: "候选人" }[role] }}</div>
    <div class="msg-bubble">
      <div class="msg-content" v-text="content" />
    </div>
  </div>
</template>

<style scoped>
.chat-message {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 80%;
}

.msg-system {
  align-self: center;
  max-width: 100%;
}

.msg-system .msg-bubble {
  background: #f1f5f9;
  color: var(--color-text-secondary);
  font-size: 13px;
  text-align: center;
  padding: 6px 16px;
  border-radius: 16px;
}

.msg-system .msg-label {
  display: none;
}

.msg-interviewer {
  align-self: flex-start;
}

.msg-interviewer .msg-bubble {
  background: var(--color-primary-light);
  color: var(--color-text);
  border: 1px solid var(--color-primary);
  border-radius: 4px 16px 16px 16px;
}

.msg-user {
  align-self: flex-end;
}

.msg-user .msg-bubble {
  background: var(--color-primary);
  color: #fff;
  border-radius: 16px 4px 16px 16px;
}

.msg-candidate {
  align-self: flex-end;
}

.msg-candidate .msg-bubble {
  background: #fef3c7;
  color: var(--color-text);
  border: 1px solid #fcd34d;
  border-radius: 16px 4px 16px 16px;
}

.msg-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-secondary);
  padding: 0 4px;
}

.msg-bubble {
  padding: 10px 14px;
  line-height: 1.5;
  font-size: 14px;
}

.msg-content {
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
