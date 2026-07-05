#!/usr/bin/env python3
"""模拟面试主程序 — 自动回答

从本地简历 PDF 和岗位描述 TXT 读取信息，AI 面试官提问 + AI 候选人自动回答，
全程自动化运行，面试结束后输出逐题评分和综合评价。
"""

import asyncio
import os
import re
import sys

_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from tools.file_parser import parse_file
from engine.interview_engine import InterviewEngine
from agent.candidate_agent import CandidateAgent, CandidateConfig


# ── 文件路径 ──
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CV_PATH = os.path.join(BASE_DIR, "assert", "cv", "大模型.pdf")
JD_PATH = os.path.join(BASE_DIR, "assert", "job", "大模型-应用.txt")


# ── 工具函数 ──

async def load_resume(path: str) -> str:
    if not os.path.exists(path):
        print(f"[错误] 简历文件不存在：{path}")
        sys.exit(1)
    text = await parse_file(path)
    if not text.strip():
        print(f"[错误] 简历文件解析后为空：{path}")
        sys.exit(1)
    return text.strip()


def load_jd(path: str) -> str:
    if not os.path.exists(path):
        print(f"[错误] 岗位描述文件不存在：{path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def extract_experience_years(resume: str) -> int:
    """从简历文本中提取工作年限"""
    patterns = [
        r"工作年限[：:]\s*(\d+)\s*年",
        r"(\d+)\s*年（.*?）",
        r"(\d+)\s*年后端",
        r"工作经验[：:].*?(\d+)\s*年",
    ]
    for p in patterns:
        m = re.search(p, resume)
        if m:
            return int(m.group(1))
    return 3  # 默认


def infer_candidate_config(resume: str, jd: str) -> CandidateConfig:
    """根据简历和岗位描述推断候选人配置"""
    years = extract_experience_years(resume)

    # 从简历中提取技能优势
    skill_keywords = [
        "LangChain", "LangGraph", "LlamaIndex", "RAG", "MCP",
        "vLLM", "FastAPI", "Python", "Agent", "LoRA", "QLoRA",
        "Docker", "Kubernetes", "Redis", "PostgreSQL", "MySQL",
        "Flink", "AIOps", "Prompt Engineering",
    ]
    strengths = [s for s in skill_keywords if s.lower() in resume.lower()]

    # 岗位方向中没有在简历中找到的技能作为短板
    jd_skills = ["Java", "Spring Boot", "Kubernetes", "Docker"]
    weaknesses = [s for s in jd_skills if s.lower() not in resume.lower()]

    # 根据经验年限推断等级
    if years >= 8:
        level = "expert"
    elif years >= 4:
        level = "senior"
    elif years >= 2:
        level = "mid"
    else:
        level = "junior"

    return CandidateConfig(
        level=level,
        years_of_experience=years,
        strengths=strengths,
        weaknesses=weaknesses,
    )


async def main():
    print("=" * 56)
    print("          AI 面试助手 — 全自动模拟面试")
    print("=" * 56)

    # ── 加载简历与 JD ──
    print("\n>>> 正在加载简历...")
    resume = await load_resume(CV_PATH)
    print(f"    读取成功（{len(resume)} 字符）")

    print("\n>>> 正在加载岗位描述...")
    jd = load_jd(JD_PATH)
    print(f"    读取成功（{len(jd)} 字符）")

    # ── 创建候选人 ──
    candidate_config = infer_candidate_config(resume, jd)
    candidate = CandidateAgent(candidate_config)

    level_map = {"junior": "初级", "mid": "中级", "senior": "高级", "expert": "专家"}
    print(f"\n>>> 候选人配置")
    print(f"    等级：{level_map.get(candidate_config.level, candidate_config.level)}")
    print(f"    经验：{candidate_config.years_of_experience}年")
    print(f"    优势：{'、'.join(candidate_config.strengths) if candidate_config.strengths else '无'}")
    print(f"    短板：{'、'.join(candidate_config.weaknesses) if candidate_config.weaknesses else '无'}")

    # ── 初始化引擎 ──
    print("\n>>> 正在生成题库...")
    engine = InterviewEngine()
    await engine.setup(resume, jd, num_questions=5)
    print(f"    已准备 {len(engine.state.question_pool)} 道题目，面试开始！\n")

    # ── 逐题问答 ──
    for round_idx in range(len(engine.state.question_pool)):
        print(f"\n{'━' * 56}")
        print(f"  第 {round_idx + 1} 题（共 {len(engine.state.question_pool)} 题）")
        print(f"{'━' * 56}")

        # ask
        question = await engine.ask()
        print(f"\n面试官：{question}")

        # 候选人自动回答
        print(f"\n候选人：", end="", flush=True)
        answer = await candidate.answer(question)
        print(answer)
        await engine.answer(answer)

        # 追问
        fq = await engine.follow_up()
        if fq:
            print(f"\n面试官（追问）：{fq}")
            print(f"\n候选人：", end="", flush=True)
            f_answer = await candidate.answer(fq)
            print(f_answer)
            await engine.answer(f_answer)

    # ── 统一评价 ──
    print(f"\n\n{'=' * 56}")
    print("  所有题目回答完毕，正在生成评价报告...")
    print(f"{'=' * 56}")

    # 逐题评价
    print(f"\n{'─' * 56}")
    print("  逐题复盘")
    print(f"{'─' * 56}")
    for round_idx in range(len(engine.state.rounds)):
        eval_result = await engine.evaluate_round()
        print(f"\n第 {round_idx + 1} 题：{eval_result.question}")
        print(f"评分：{'⭐' * eval_result.score}{'☆' * (5 - eval_result.score)} ({eval_result.score}/5)")
        if eval_result.highlights:
            print(f"亮点：{eval_result.highlights}")
        if eval_result.missing_points:
            print(f"缺失要点：{eval_result.missing_points}")
        if eval_result.improvement:
            print(f"改进建议：{eval_result.improvement}")

    # 整体评价
    final_eval = await engine.finish()
    print(f"\n{'─' * 56}")
    print("  综合评价")
    print(f"{'─' * 56}")
    print(f"\n总分：{final_eval.overall_score:.1f}/100")
    print(f"终期判决：{final_eval.final_verdict}")
    if final_eval.salary_fit:
        print(f"薪资建议：{final_eval.salary_fit}")
    print("\n各维度评分：")
    for d in final_eval.dimensions:
        print(f"  {d.name}：{d.score:.1f}分 —— {d.summary}")
    if final_eval.improvement_tips:
        print("\n通关锦囊：")
        for tip in final_eval.improvement_tips:
            print(f"  • {tip}")
    print(f"\n{'=' * 56}")
    print("  ✅ 面试结束")
    print(f"{'=' * 56}")


if __name__ == "__main__":
    asyncio.run(main())
