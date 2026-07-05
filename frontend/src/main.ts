import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import App from "./App.vue";
import KnowledgeBase from "./views/KnowledgeBase.vue";
import Interview from "./views/Interview.vue";
import "./style.css";

const routes = [
  { path: "/", redirect: "/knowledge" },
  { path: "/knowledge", name: "KnowledgeBase", component: KnowledgeBase },
  { path: "/interview", name: "Interview", component: Interview },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

createApp(App).use(router).mount("#app");
