import asyncio
from typing import Optional

from pydantic import BaseModel
from agents import set_default_openai_api, set_tracing_disabled
from agents import Agent, Runner

from schema.system_config import load_system_config
from schema.engine import (
    InterviewConfig,
    InterviewRound,
    InterviewState,
    InterviewStatus,
    DrillDownRound,
)
from schema.question import QuestionItem
from schema.evaluation import QuestionEvaluation, InterviewEvaluation
from agent.kb_agent import KnowledgeBase, KBAgent
from agent.question_generator import QuestionGenerator
from agent.evaluator import Evaluator

set_default_openai_api("chat_completions")
set_tracing_disabled(True)

config = load_system_config("config/system_config.json")


TOPIC_EXTRACT_PROMPT = """你是一位技术招聘专家，擅长从简历和岗位描述中提取面试需要考察的知识点。

请根据【简历】和【岗位描述】，列出待考察的技术知识点清单。
要求：
1. 每个知识点必须严格来自【岗位描述】中明确列出的技术要求和职责方向
2. 优先提取岗位的核心技术领域（如大模型应用、RAG、Agent开发等），而非通用基础设施
3. 如果岗位描述中提及了具体技术组件（如MySQL、Redis），只提取与岗位核心技术方向相关的部分
4. 输出3-6个知识点即可，确保每个都是该岗位真正需要深入考察的方向
5. 用中文输出，每行一个知识点"""


FOLLOW_UP_PROMPT = """你是一位资深技术面试官，正在对候选人进行追问。
请根据【面试题目】和【候选人回答】，判断是否需要追问。

追问原则：
- 如果候选人回答"不知道"、"不会"、空白或表示完全不理解 → 不需要追问，直接跳过
- 如果回答完整深入，涵盖了核心原理和最佳实践 → 不需要追问
- 如果回答触及了核心技术但不够深入，或存在可以深挖的点 → 生成1道追问
- 追问应该层层递进，考察候选人的深度理解
- 最多只能追问1次

请输出是否需要追问以及追问的问题。"""


class FollowUpDecision(BaseModel):
    needs_follow_up: bool
    question: str = ""


class InterviewEngine:
    """面试流程编排引擎

    组合 KBAgent、QuestionGenerator、Evaluator，模拟完整面试环节。
    状态流转：idle → ready → in_progress → finished
    """

    def __init__(self):
        self._kb = KnowledgeBase()
        self._kb_agent = KBAgent()
        self._question_generator = QuestionGenerator()
        self._evaluator = Evaluator()

        self._follow_up_agent = Agent(
            name="追问判断",
            model=config.default_model,
            instructions=FOLLOW_UP_PROMPT,
            output_type=FollowUpDecision,
        )
        self._topic_agent = Agent(
            name="知识点提取",
            model=config.default_model,
            instructions=TOPIC_EXTRACT_PROMPT,
        )
        self._state = InterviewState()
        self._awaiting_drill_down = False

    # ── 状态查询 ──

    @property
    def state(self) -> InterviewState:
        """获取完整面试状态"""
        return self._state

    @property
    def current_round(self) -> Optional[InterviewRound]:
        """获取当前正在进行的轮次"""
        idx = self._state.current_round_index
        if 0 <= idx < len(self._state.rounds):
            return self._state.rounds[idx]
        return None

    # ── 面试流程方法 ──

    async def setup(self, resume: str, jd: str, **kwargs):
        """初始化配置，构建 question_pool

        Args:
            resume: 简历文本
            jd: 岗位描述文本
            **kwargs: 其他 InterviewConfig 参数（style, difficulty, num_questions, focus_areas）
        """
        self._state = InterviewState(
            config=InterviewConfig(resume=resume, jd=jd, **kwargs),
            status=InterviewStatus.ready,
        )

        # 1. 从简历和JD中提取知识点关键词
        topics = await self._extract_topics(resume, jd)
        num_needed = self._state.config.num_questions

        # 2. 先用 QuestionGenerator 生成岗位领域相关的题目（作为主源）
        gen_result = await self._question_generator.run(
            background=f"简历：{resume}\n岗位描述：{jd}",
            knowledge_points=topics,
        )
        questions: list[QuestionItem] = list(gen_result.questions)

        # 3. 如果还不够，从知识库检索补充（仅当题目数量不足时）
        if len(questions) < num_needed:
            for topic in topics:
                results = self._kb.search(topic, top_k=3)
                for _, q_item in results:
                    if not any(q.question == q_item.question for q in questions):
                        questions.append(q_item)
                    if len(questions) >= num_needed:
                        break
                if len(questions) >= num_needed:
                    break

        # 4. 取前 num_questions 道题放入 question_pool
        self._state.question_pool = questions[:num_needed]
        self._state.status = InterviewStatus.ready

    async def _extract_topics(self, resume: str, jd: str) -> list[str]:
        """提取技术知识点关键词"""
        input_text = f"简历：{resume}\n\n岗位描述：{jd}"
        result = await Runner.run(self._topic_agent, input_text)
        topics = [
            line.strip().lstrip("0123456789.、- ")
            for line in result.final_output.strip().split("\n")
            if line.strip()
        ]
        return topics

    async def ask(self) -> str:
        """返回下一道题目，推进 round_index

        Returns:
            题目文本

        Raises:
            RuntimeError: 所有题目已问完
        """
        next_idx = self._state.current_round_index + 1
        if next_idx >= len(self._state.question_pool):
            raise RuntimeError("所有题目已问完，请调用 finish() 结束面试")

        question_item = self._state.question_pool[next_idx]
        round_entry = InterviewRound(question=question_item)
        self._state.rounds.append(round_entry)
        self._state.current_round_index = next_idx
        self._state.status = InterviewStatus.in_progress
        self._awaiting_drill_down = False

        return question_item.question

    async def answer(self, text: str):
        """保存用户回答

        当前处于追问阶段时，回答会存入 drill_down 子轮次。

        Args:
            text: 用户回答文本

        Raises:
            RuntimeError: 当前没有进行中的题目
        """
        current = self.current_round
        if current is None:
            raise RuntimeError("当前没有进行中的题目，请先调用 ask()")

        if self._awaiting_drill_down:
            if current.drill_down:
                current.drill_down.answer = text
            self._awaiting_drill_down = False
        else:
            current.answer = text

    async def follow_up(self) -> Optional[str]:
        """根据回答生成追问

        Returns:
            追问文本，无需追问时返回 None

        Raises:
            RuntimeError: 当前没有进行中的题目
        """
        current = self.current_round
        if current is None:
            raise RuntimeError("当前没有进行中的题目")

        # 前置守卫：空回答或明显"不知道"时跳过追问
        answer_text = current.answer.strip()
        if not answer_text:
            return None
        ignorance_keywords = ("不知道", "不会", "不了解", "没学过", "不懂", "不清楚", "没接触过", "没做过")
        if any(kw in answer_text for kw in ignorance_keywords):
            return None

        input_text = (
            f"面试题目：{current.question.question}\n\n"
            f"候选人回答：{answer_text}"
        )
        result = await Runner.run(self._follow_up_agent, input_text)
        decision: FollowUpDecision = result.final_output

        if decision.needs_follow_up and decision.question:
            current.drill_down = DrillDownRound(question=decision.question)
            self._awaiting_drill_down = True
            return decision.question

        return None

    async def skip_follow_up(self):
        """跳过追问，标记当前 round 完成"""
        self._awaiting_drill_down = False

    async def evaluate_round(self) -> QuestionEvaluation:
        """评价当前轮次（含追问）

        Returns:
            单题评价结果

        Raises:
            RuntimeError: 当前没有进行中的题目
        """
        current = self.current_round
        if current is None:
            raise RuntimeError("当前没有进行中的题目")

        # 构建完整回答文本（含追问回答）
        full_answer = current.answer
        if current.drill_down and current.drill_down.answer:
            full_answer += (
                f"\n\n[追问] {current.drill_down.question}\n"
                f"[回答] {current.drill_down.answer}"
            )

        eval_result = await self._evaluator.evaluate_single(
            question=current.question.question,
            answer=full_answer,
        )
        current.evaluation = eval_result
        return eval_result

    async def finish(self) -> InterviewEvaluation:
        """整体评价，结束面试

        Returns:
            整体面试评价报告
        """
        # 构建所有 Q&A 对（含追问）
        qa_pairs = []
        for r in self._state.rounds:
            answer_text = r.answer
            if r.drill_down and r.drill_down.answer:
                answer_text += (
                    f"\n[追问] {r.drill_down.question}\n"
                    f"[回答] {r.drill_down.answer}"
                )
            qa_pairs.append((r.question.question, answer_text))

        job_context = (
            f"岗位描述：{self._state.config.jd}\n"
            f"简历：{self._state.config.resume}"
        )

        eval_result = await self._evaluator.evaluate_all(
            qa_pairs=qa_pairs,
            job_context=job_context,
        )

        self._state.final_evaluation = eval_result
        self._state.status = InterviewStatus.finished

        return eval_result


async def main():
    """交互式面试流程演示"""
    engine = InterviewEngine()

    resume = """
    熟练掌握 Python、Django、Redis、MySQL
    3年后端开发经验，熟悉RESTful API设计
    熟悉Docker容器化部署
    """

    jd = """
    招聘中级Python后端开发工程师
    要求：熟悉Python并发编程、Django ORM优化、Redis缓存策略
    加分：有微服务架构经验
    """

    print("=" * 50)
    print("AI 面试助手 — 开始模拟面试")
    print("=" * 50)

    # setup
    print("\n>>> 正在生成题库...")
    await engine.setup(resume, jd, num_questions=3)
    print(f"已准备 {len(engine.state.question_pool)} 道题目，面试开始！\n")

    for round_idx in range(len(engine.state.question_pool)):
        print(f"\n{'=' * 50}")
        print(f"第 {round_idx + 1} 题（共 {len(engine.state.question_pool)} 题）")
        print(f"{'=' * 50}")

        # ask
        question = await engine.ask()
        print(f"\n面试官：{question}")

        # user answers (real input)
        user_answer = input("\n你的回答（输入后按回车）：")
        await engine.answer(user_answer)

        # follow-up
        fq = await engine.follow_up()
        if fq:
            print(f"\n面试官（追问）：{fq}")
            f_answer = input("\n你的回答（输入后按回车）：")
            await engine.answer(f_answer)

    # 所有题目完成后统一评价
    print(f"\n{'=' * 50}")
    print("所有题目回答完毕，正在生成评价报告...")
    print(f"{'=' * 50}")

    # 逐题评价
    print("\n--- 逐题复盘 ---")
    for round_idx in range(len(engine.state.rounds)):
        eval_result = await engine.evaluate_round()
        print(f"\n第 {round_idx + 1} 题：{eval_result.question}")
        print(f"评分：{eval_result.score}/5")
        print(f"亮点：{eval_result.highlights}")
        print(f"缺失要点：{eval_result.missing_points}")
        print(f"改进建议：{eval_result.improvement}")

    # 整体评价
    final_eval = await engine.finish()
    print(f"\n--- 综合评价 ---")
    print(f"总分：{final_eval.overall_score}/100")
    print(f"终期判决：{final_eval.final_verdict}")
    print(f"薪资建议：{final_eval.salary_fit}")
    print("\n各维度评分：")
    for d in final_eval.dimensions:
        print(f"  {d.name}：{d.score}分 — {d.summary}")
    print("\n通关锦囊：")
    for tip in final_eval.improvement_tips:
        print(f"  - {tip}")
    print(f"\n状态：{engine.state.status.value}")
    print("✅ 面试结束")


if __name__ == "__main__":
    asyncio.run(main())
