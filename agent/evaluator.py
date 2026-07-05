import asyncio

from agents import set_default_openai_api, set_tracing_disabled
from openai.types.responses import ResponseTextDeltaEvent
from agents import Agent, Runner

from schema.system_config import load_system_config
from schema.evaluation import QuestionEvaluation, InterviewEvaluation, DimensionScore

set_default_openai_api("chat_completions")
set_tracing_disabled(True)

config = load_system_config("config/system_config.json")


SINGLE_EVAL_PROMPT = """你是一位资深技术面试官，擅长对候选人的回答进行量化评估和改进指导。

请根据【面试题目】和【候选人回答】，进行评分和改进建议。

⚠️ 核心评分原则：考察"核心思路是否正确 + 是否有场景化意识"，而非按清单机械扣分。
一段简洁但切中要害的回答，应当获得高分。

评分标准（1-5分）：
1分 — 完全偏离方向或基本未作答
2分 — 触及部分要点但核心理解有偏差
3分 — 核心思路基本正确，但缺少场景化意识或关键环节的关联论述
4分 — 核心思路正确，有自己的场景化思考，整体方向对路
5分 — 核心思路清晰正确，展现出场景化意识和实践经验，即便未列出所有技术细节

请输出：
1. score：评分（1-5分整数）
2. highlights：回答亮点（指出哪些核心思路正确、哪些场景化思考到位）
3. missing_points：可以补充的方向（注意语气是"锦上添花"而非"扣分项"）
4. improvement：导师级复盘建议（具体可执行的改进方向）"""


OVERALL_EVAL_PROMPT = """你是一位资深技术面试官，负责对整场面试进行多维度量化评估。

请根据【岗位背景信息】和【面试记录（题目+回答）】，生成完整的面试评价报告。

评估维度（0-100分）：
1. 岗位匹配度 — 候选人的能力和经验与岗位要求的匹配程度
2. 技术深度 — 对核心原理、最佳实践和底层机制的掌握程度
3. 沟通与逻辑 — 表达是否条理清晰、逻辑严密，是否遵循STAR原则
4. 抗压与临场 — 面对追问或未知问题时的应变能力

要求：
1. 对每个题目逐一评分，指出亮点和缺失关键点，给出改进建议
2. 对四个维度分别打分并给出简要评语
3. 给出终期判决（通过 / 待定 / 淘汰）。如果判决为"淘汰"，则 salary_fit 设为"无"；否则给出建议薪资匹配度
4. 提炼2-3个面试前必须查漏补缺的知识盲区作为通关锦囊"""


class Evaluator:
    """面试评价智能体，支持单题评价和整体面试评价"""

    def __init__(self):
        self._single_agent = Agent(
            name="单题评价",
            model=config.default_model,
            instructions=SINGLE_EVAL_PROMPT,
            output_type=QuestionEvaluation,
        )
        self._overall_agent = Agent(
            name="整体面试评价",
            model=config.default_model,
            instructions=OVERALL_EVAL_PROMPT,
            output_type=InterviewEvaluation,
        )
        self._last_question_eval: QuestionEvaluation | None = None
        self._last_interview_eval: InterviewEvaluation | None = None

    # ── 单题评价 ──

    @property
    def last_question_eval(self) -> QuestionEvaluation | None:
        return self._last_question_eval

    async def evaluate_single(self, question: str, answer: str) -> QuestionEvaluation:
        """评价单个题目的回答"""
        input_text = (
            f"面试题目：{question}\n\n"
            f"候选人回答：{answer}"
        )
        result = await Runner.run(self._single_agent, input_text)
        self._last_question_eval = result.final_output
        # 回填题目文本
        self._last_question_eval.question = question
        return self._last_question_eval

    async def evaluate_single_streamed(self, question: str, answer: str):
        """流式评价单个题目的回答，结束后通过 last_question_eval 获取结果"""
        input_text = (
            f"面试题目：{question}\n\n"
            f"候选人回答：{answer}"
        )
        result = Runner.run_streamed(self._single_agent, input_text)
        async for event in result.stream_events():
            if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                yield event.data.delta
        self._last_question_eval = result.final_output
        self._last_question_eval.question = question

    # ── 整体面试评价 ──

    @property
    def last_interview_eval(self) -> InterviewEvaluation | None:
        return self._last_interview_eval

    async def evaluate_all(
        self,
        qa_pairs: list[tuple[str, str]],
        job_context: str = "",
    ) -> InterviewEvaluation:
        """评价整场面试表现

        Args:
            qa_pairs: [(question1, answer1), (question2, answer2), ...]
            job_context: 岗位背景信息
        """
        interview_log = "\n\n".join(
            f"题目{i+1}：{q}\n回答{i+1}：{a}"
            for i, (q, a) in enumerate(qa_pairs)
        )
        input_text = (
            f"岗位背景信息：{job_context}\n\n"
            f"面试记录：\n{interview_log}"
        )
        result = await Runner.run(self._overall_agent, input_text)
        self._last_interview_eval = result.final_output
        return self._last_interview_eval

    async def evaluate_all_streamed(
        self,
        qa_pairs: list[tuple[str, str]],
        job_context: str = "",
    ):
        """流式评价整场面试表现，结束后通过 last_interview_eval 获取结果"""
        interview_log = "\n\n".join(
            f"题目{i+1}：{q}\n回答{i+1}：{a}"
            for i, (q, a) in enumerate(qa_pairs)
        )
        input_text = (
            f"岗位背景信息：{job_context}\n\n"
            f"面试记录：\n{interview_log}"
        )
        result = Runner.run_streamed(self._overall_agent, input_text)
        async for event in result.stream_events():
            if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                yield event.data.delta
        self._last_interview_eval = result.final_output


async def main():
    evaluator = Evaluator()

    # ── 单题评价示例 ──
    print("=== 单题评价 ===")
    result = await evaluator.evaluate_single(
        question="请解释Python的GIL是什么，它对多线程有什么影响？",
        answer="GIL是全局解释器锁，它让Python在同一时刻只能执行一个线程。"
               "对于CPU密集型任务，多线程反而会因为上下文切换变慢。"
               "可以用多进程或异步编程来绕过GIL的限制。"
    )
    print(f"题目：{result.question}")
    print(f"评分：{result.score}/5")
    print(f"亮点：{result.highlights}")
    print(f"缺失：{result.missing_points}")
    print(f"改进：{result.improvement}")
    print()

    # ── 整体面试评价示例 ──
    print("=== 整体面试评价 ===")
    interview = await evaluator.evaluate_all(
        qa_pairs=[
            ("请解释Python的GIL是什么？",
             "GIL是全局解释器锁，同一时刻只能执行一个线程。"
             "CPU密集型用多进程，IO密集型用多线程或异步。"),
            ("讲讲Django ORM查询优化经验？",
             "用select_related和prefetch_related减少查询次数，"
             "用索引优化慢查询，用connection.queries调试SQL。"),
        ],
        job_context="招聘中级Python后端开发，要求熟悉Python并发编程和Django框架",
    )
    print(f"总分：{interview.overall_score}")
    for d in interview.dimensions:
        print(f"  {d.name}：{d.score}分 — {d.summary}")
    print(f"终期判决：{interview.final_verdict}")
    print(f"薪资匹配：{interview.salary_fit}")
    print("通关锦囊：")
    for tip in interview.improvement_tips:
        print(f"  - {tip}")
    print()

    # 逐题评价
    print("--- 逐题复盘 ---")
    for qe in interview.qa_evaluations:
        print(f"Q: {qe.question}")
        print(f"评分: {qe.score}/5")
        print(f"改进: {qe.improvement}")
        print()

    # ── 流式单题评价示例 ──
    print("=== 流式单题评价 ===")
    async for chunk in evaluator.evaluate_single_streamed(
        question="什么是SQL注入？如何预防？",
        answer="SQL注入是把恶意SQL代码拼接到查询参数中。"
               "预防方法：使用参数化查询、ORM框架、输入验证。",
    ):
        print(chunk, end="", flush=True)
    print("\n")

    # 流结束后获取结构化结果
    qe = evaluator.last_question_eval
    print(f"流式单题评分：{qe.score}/5")


if __name__ == "__main__":
    asyncio.run(main())
