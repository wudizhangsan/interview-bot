import asyncio
import json
import os
from pathlib import Path
from typing import Optional

from agents import set_default_openai_api, set_tracing_disabled
from agents import Agent, Runner

from schema.system_config import load_system_config
from schema.question import QuestionItem

set_default_openai_api("chat_completions")
set_tracing_disabled(True)

config = load_system_config("config/system_config.json")

KB_DIR = Path(__file__).resolve().parent.parent / "assert" / "kb"


KB_SELECT_PROMPT = """你是一个面试题库管理员，负责从知识库中为面试官挑选最合适的题目。

知识库中按知识点组织题目，每个知识点包含多道面试题（含参考答案）。

你的任务：
1. 根据面试官提出的主题/知识点，从已有的题库中选择最匹配的一道题
2. 如果题库中有直接相关的知识点，挑一道最有代表性的题目
3. 如果没有直接相关的题目，如实告知"未找到匹配题目"

注意：参考答案仅用于面试官参考，你需要将question和answer都完整输出。"""


class KnowledgeBase:
    """题库加载与检索"""

    def __init__(self, kb_dir: str | Path = KB_DIR):
        self.kb_dir = Path(kb_dir)
        self._topics: dict[str, list[QuestionItem]] = {}
        self._loaded = False

    def load_all(self) -> dict[str, list[QuestionItem]]:
        """加载所有题库JSON文件"""
        if self._loaded:
            return self._topics

        if not self.kb_dir.exists():
            self._loaded = True
            return self._topics

        for fpath in sorted(self.kb_dir.glob("*.json")):
            topic = fpath.stem  # 文件名作为知识点名称
            with open(fpath, "r", encoding="utf-8") as f:
                raw_list = json.load(f)
            self._topics[topic] = [QuestionItem(**item) for item in raw_list]

        self._loaded = True
        return self._topics

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, QuestionItem]]:
        """基于关键词匹配检索相关题目，返回 [(topic, QuestionItem), ...]"""
        self.load_all()
        if not self._topics:
            return []

        query_lower = query.lower()
        query_tokens = set(query_lower.split())

        scored: list[tuple[int, str, QuestionItem]] = []

        for topic, questions in self._topics.items():
            topic_lower = topic.lower()
            for q_item in questions:
                score = 0
                # 知识点文件名匹配
                if query_lower in topic_lower or topic_lower in query_lower:
                    score += 5
                # 文件名分词匹配
                topic_tokens = set(topic_lower.replace("_", " ").split())
                score += len(query_tokens & topic_tokens) * 3
                # 题目内容匹配
                q_lower = q_item.question.lower()
                if query_lower in q_lower:
                    score += 2
                score += sum(2 for t in query_tokens if t in q_lower)
                # 答案内容匹配
                a_lower = q_item.answer.lower()
                score += sum(1 for t in query_tokens if t in a_lower)

                if score > 0:
                    scored.append((score, topic, q_item))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [(topic, q) for _, topic, q in scored[:top_k]]

    @property
    def topic_names(self) -> list[str]:
        """返回所有知识点名称"""
        self.load_all()
        return list(self._topics.keys())

    def get_topic_questions(self, topic: str) -> list[QuestionItem]:
        """获取指定知识点的所有题目"""
        self.load_all()
        return self._topics.get(topic, [])


class KBAgent:
    """题库面试官——从知识库中选取匹配的面试题"""

    def __init__(self):
        self.kb = KnowledgeBase()
        self._agent = Agent(
            name="题库提问智能体",
            model=config.default_model,
            instructions=KB_SELECT_PROMPT,
            output_type=QuestionItem,
        )
        self._last_question: Optional[QuestionItem] = None

    @property
    def last_question(self) -> Optional[QuestionItem]:
        return self._last_question

    async def select_question(self, query: str, top_k: int = 5) -> Optional[QuestionItem]:
        """根据查询主题从题库中选择一道最匹配的题目

        Args:
            query: 搜索主题描述，如"Python GIL"、"Django ORM优化"
            top_k: 候选题目数量

        Returns:
            匹配的 QuestionItem，未找到时返回 None
        """
        candidates = self.kb.search(query, top_k=top_k)
        if not candidates:
            self._last_question = None
            return None

        # 将候选题目格式化为提示词
        kb_text = "以下是从题库中检索到的候选题目：\n\n"
        for i, (topic, q_item) in enumerate(candidates, 1):
            kb_text += (
                f"[候选{i}] 知识点：{topic}\n"
                f"题目：{q_item.question}\n"
                f"参考答案：{q_item.answer}\n\n"
            )
        kb_text += f"请根据面试官的需求「{query}」，从上述候选中选择最匹配的一道题目输出。"

        result = await Runner.run(self._agent, kb_text)
        self._last_question = result.final_output
        return self._last_question

    def load_all(self) -> dict[str, list[QuestionItem]]:
        """直接加载全部题库（不经过LLM）"""
        return self.kb.load_all()


async def main():
    agent = KBAgent()

    # 1. 列出所有知识点
    print("=== 已有知识点 ===")
    for topic in agent.kb.topic_names:
        cnt = len(agent.kb.get_topic_questions(topic))
        print(f"  {topic} ({cnt}题)")
    print()

    # 2. 根据查询选取题目
    queries = [
        "Python GIL多线程",
        "Django ORM查询慢",
        "Redis缓存穿透",
        "完全不存在的知识点",
    ]

    for q in queries:
        print(f"=== 查询：{q} ===")
        result = await agent.select_question(q)
        if result:
            print(f"题目：{result.question}")
            print(f"答案：{result.answer[:60]}...")
        else:
            print("未找到匹配题目")
        print()


if __name__ == "__main__":
    asyncio.run(main())
