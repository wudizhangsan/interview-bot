import asyncio
import uuid

from agents import set_default_openai_api, set_tracing_disabled
from openai.types.responses import ResponseTextDeltaEvent
from agents import Agent, Runner, SQLiteSession

from schema.system_config import load_system_config
from schema.question import QuestionList

set_default_openai_api("chat_completions")
set_tracing_disabled(True)

config = load_system_config("config/system_config.json")


QUESTION_PROMPT = """你是一位资深技术面试官，擅长根据岗位要求和技术知识点出题。
请根据给定的【背景信息】和【知识点清单】，生成若干道面试题。

要求：
1. 每道题包含「问题」和「参考答案」两部分
2. 题目要有层次：基础题考察概念理解，进阶题考察原理和最佳实践
3. 参考答案应准确、简洁，直击要点
4. 题目数量为3-5道，覆盖给定的知识点
5. 用中文出题和回答，口语化表达，搭配专业名词
6. 题目和参考答案都不要出现代码，用文字描述即可
7. 参考回答要像面试中口头叙述一样自然，而非书面文档"""


class QuestionGenerator:
    def __init__(self):
        self.agent = Agent(
            name="面试提问生成器",
            model=config.default_model,
            instructions=QUESTION_PROMPT,
            output_type=QuestionList,
        )
        self._last_result: QuestionList | None = None

    @property
    def last_result(self) -> QuestionList | None:
        return self._last_result

    async def run(self, background: str, knowledge_points: list[str]) -> QuestionList:
        input_text = (
            f"背景信息：{background}\n\n"
            f"知识点清单：{'、'.join(knowledge_points)}"
        )
        result = await Runner.run(self.agent, input_text)
        return result.final_output

    async def run_streamed(self, background: str, knowledge_points: list[str]):
        input_text = (
            f"背景信息：{background}\n\n"
            f"知识点清单：{'、'.join(knowledge_points)}"
        )
        result = Runner.run_streamed(self.agent, input_text)
        async for event in result.stream_events():
            if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                yield event.data.delta
        self._last_result = result.final_output


async def main():
    generator = QuestionGenerator()

    # run() — 一次性获取完整结果
    result = await generator.run(
        background="招聘一名中级Python后端开发工程师",
        knowledge_points=["Python GIL", "异步编程(asyncio)", "Django ORM与查询优化"],
    )
    print("=== run() 输出 ===")
    for i, q in enumerate(result.questions, 1):
        print(f"问题{i}：{q.question}")
        print(f"答案：{q.answer}")
        print()

    # run_streamed() — 流式输出，结束后通过 last_result 拿到 QuestionList
    print("=== run_streamed() 输出 ===")
    async for chunk in generator.run_streamed(
        background="招聘一名中级Python后端开发工程师",
        knowledge_points=["Python GIL", "异步编程(asyncio)", "Django ORM与查询优化"],
    ):
        print(chunk, end="", flush=True)
    print()

    # 流结束后获取结构化结果
    for i, q in enumerate(generator.last_result.questions, 1):
        print(f"问题{i}：{q.question}")
        print(f"答案：{q.answer}")
        print()



if __name__ == "__main__":
    asyncio.run(main())
