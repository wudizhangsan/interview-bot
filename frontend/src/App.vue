<script setup lang="ts">
import { useRouter, useRoute } from "vue-router";

const router = useRouter();
const route = useRoute();

function isActive(name: string): boolean {
  return route.name === name;
}
</script>

<template>
  <div class="app-container">
    <header class="app-header">
      <h1 class="app-title">AI 面试助手</h1>
      <nav class="app-nav">
        <router-link
          to="/knowledge"
          class="nav-tab"
          :class="{ active: isActive('KnowledgeBase') }"
        >
          知识库
        </router-link>
        <router-link
          to="/interview"
          class="nav-tab"
          :class="{ active: isActive('Interview') }"
        >
          模拟面试
        </router-link>
      </nav>
    </header>
    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>
