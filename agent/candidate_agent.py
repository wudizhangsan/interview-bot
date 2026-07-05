import asyncio
from typing import Optional

from pydantic import BaseModel, Field
from agents import set_default_openai_api, set_tracing_disabled
from openai.types.responses import ResponseTextDeltaEvent
from agents import Agent, Runner

from schema.system_config import load_system_config

set_default_openai_api("chat_completions")
set_tracing_disabled(True)

config = load_system_config("config/system_config.json")


CANDIDATE_PROMPT = """你正在模拟一场技术面试，你的角色是【候选人】。

## 你的能力设定
- 能力等级：{ability_level}
- 工作经验：{years_of_experience}年
- 技能优势：{strengths}
- 技能短板：{weaknesses}

## 回答要求
1. 严格匹配你被设定的能力等级来回答问题
2. 不要答超出能力范围的内容
3. 可以使用第一人称（"我"），语气自然真实
4. 回答要体现对应水平的真实表现：
   - 初级：回答较简短，能说对基本概念但深度有限，偶尔会遗漏关键点
   - 中级：回答完整，能说清原理和实践，逻辑清晰
   - 高级：回答深入，涵盖原理、最佳实践和踩坑经验，有架构思维
   - 专家：回答极其深入，能横向对比不同方案，有全局视野
5. 回答长度适中，无需过于冗长

请直接以候选人口吻回答面试官的提问。"""


class CandidateConfig(BaseModel):
    """候选人能力配置"""
    level: str = "mid"  # junior / mid / senior / expert
    years_of_experience: int = 3
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)


LEVEL_DESCRIPTION = {
    "junior": "初级",
    "mid": "中级",
    "senior": "高级",
    "expert": "专家",
}


class CandidateAgent:
    """模拟面试候选人，根据能力设定生成匹配的回答"""

    def __init__(self, ability: str | CandidateConfig = "mid"):
        if isinstance(ability, str):
            self.config = CandidateConfig(level=ability)
        else:
            self.config = ability

        level_label = LEVEL_DESCRIPTION.get(self.config.level, self.config.level)
        strengths_str = "、".join(self.config.strengths) if self.config.strengths else "无特别标注"
        weaknesses_str = "、".join(self.config.weaknesses) if self.config.weaknesses else "无特别标注"

        instructions = CANDIDATE_PROMPT.format(
            ability_level=level_label,
            years_of_experience=self.config.years_of_experience,
            strengths=strengths_str,
            weaknesses=weaknesses_str,
        )

        self._agent = Agent(
            name=f"候选人（{level_label}）",
            model=config.default_model,
            instructions=instructions,
        )

    async def answer(self, question: str) -> str:
        """根据题目生成回答

        Args:
            question: 面试题目文本（可包含追问上下文）

        Returns:
            候选人回答文本
        """
        result = await Runner.run(self._agent, question)
        return result.final_output

    async def answer_streamed(self, question: str):
        """流式生成回答"""
        result = Runner.run_streamed(self._agent, question)
        async for event in result.stream_events():
            if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                yield event.data.delta


async def main():
    """演示不同能力等级的候选人回答效果"""
    test_question = "请解释Python的GIL是什么，它对多线程有什么影响？如何绕过？"

    for level in ["junior", "mid", "senior", "expert"]:
        print(f"\n{'=' * 50}")
        print(f"能力等级：{LEVEL_DESCRIPTION[level]}")
        print(f"{'=' * 50}")

        config = CandidateConfig(
            level=level,
            years_of_experience={"junior": 1, "mid": 3, "senior": 5, "expert": 10}[level],
            strengths=["Python"],
            weaknesses=[],
        )
        agent = CandidateAgent(config)
        answer = await agent.answer(test_question)
        print(f"\n面试官：{test_question}")
        print(f"\n候选人：{answer}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
