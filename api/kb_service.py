"""知识库服务：Q&A 生成 Agent + 文件读写"""

import json
import os
import re
from pathlib import Path

from agents import set_default_openai_api, set_tracing_disabled
from agents import Agent, Runner

from schema.system_config import load_system_config
from schema.question import QuestionItem, QuestionList

set_default_openai_api("chat_completions")
set_tracing_disabled(True)

config = load_system_config("config/system_config.json")

KB_DIR = Path(__file__).resolve().parent.parent / "assert" / "kb"

# 知识点名称只允许：中文、字母、数字、下划线、中划线
TOPIC_NAME_PATTERN = re.compile(r"^[\u4e00-\u9fa5a-zA-Z0-9_-]+$")

KB_GEN_PROMPT = """你是一个面试题库生成专家。请根据用户提供的知识点内容和知识点名称，生成若干道面试题。

要求：
1. 每道题包含「问题」和「参考答案」两部分
2. 题目要有层次：基础题考察概念理解，进阶题考察原理和最佳实践
3. 参考答案应准确、简洁，直击要点
4. 生成3-5道题
5. 用中文出题和回答，口语化表达，搭配专业名词
6. 题目和参考答案都不要出现代码，用文字描述即可
7. 参考回答要像面试中口头叙述一样自然，而非书面文档"""


class KBGenerator:
    """使用 LLM 从知识点文本生成 Q&A 题目"""

    def __init__(self):
        self.agent = Agent(
            name="题库生成器",
            model=config.default_model,
            instructions=KB_GEN_PROMPT,
            output_type=QuestionList,
        )

    async def generate(self, topic: str, text: str) -> list[QuestionItem]:
        """根据知识点文本生成题目列表"""
        input_text = f"知识点名称：{topic}\n\n知识点内容：{text}"
        result = await Runner.run(self.agent, input_text)
        return result.final_output.questions


# ── 工具函数 ──


def validate_topic_name(name: str) -> bool:
    """验证知识点名称合法性（防止路径穿越）"""
    return bool(TOPIC_NAME_PATTERN.match(name))


def _topic_path(topic_name: str) -> Path:
    return KB_DIR / f"{topic_name}.json"


def save_kb(topic_name: str, questions: list[QuestionItem]):
    """保存题目到 assert/kb/{topic_name}.json"""
    ensure_kb_dir()
    path = _topic_path(topic_name)
    data = [{"question": q.question, "answer": q.answer} for q in questions]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_kb(topic_name: str) -> list[dict]:
    """从 assert/kb/{topic_name}.json 加载题目"""
    path = _topic_path(topic_name)
    if not path.exists():
        raise FileNotFoundError(f"知识点 '{topic_name}' 不存在")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_topics() -> dict[str, int]:
    """列出所有知识点及其题目数量"""
    ensure_kb_dir()
    result: dict[str, int] = {}
    for fpath in sorted(KB_DIR.glob("*.json")):
        topic = fpath.stem
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        result[topic] = len(data)
    return result


def delete_kb(topic_name: str) -> bool:
    """删除知识点文件，返回是否成功"""
    path = _topic_path(topic_name)
    if not path.exists():
        return False
    os.remove(path)
    return True


def ensure_kb_dir():
    """确保知识库目录存在"""
    KB_DIR.mkdir(parents=True, exist_ok=True)
