#!/usr/bin/env python3
"""模拟面试主程序 — 手动回答

从本地简历 PDF 和岗位描述 TXT 读取信息，启动 AI 面试官进行交互式面试。
用户手动输入回答，面试结束后统一输出逐题评分和综合评价。
"""

import asyncio
import os
import sys

# 确保项目根目录在 sys.path 中
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from tools.file_parser import parse_file
from engine.interview_engine import InterviewEngine


# ── 文件路径（可根据实际情况修改）──
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CV_PATH = os.path.join(BASE_DIR, "assert", "cv", "大模型.pdf")
JD_PATH = os.path.join(BASE_DIR, "assert", "job", "大模型-应用.txt")


async def load_resume(path: str) -> str:
    """从 PDF 或 DOCX 中提取简历文本"""
    if not os.path.exists(path):
        print(f"[错误] 简历文件不存在：{path}")
        sys.exit(1)
    text = await parse_file(path)
    if not text.strip():
        print(f"[错误] 简历文件解析后为空：{path}")
        sys.exit(1)
    return text.strip()


def load_jd(path: str) -> str:
    """读取岗位描述文本"""
    if not os.path.exists(path):
        print(f"[错误] 岗位描述文件不存在：{path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


async def main():
    print("=" * 56)
    print("          AI 面试助手 — 模拟面试"
          "")
    print("=" * 56)

    # ── 加载简历与 JD ──
    print("\n>>> 正在加载简历...")
    resume = await load_resume(CV_PATH)
    print(f"    读取成功（{len(resume)} 字符）")

    print("\n>>> 正在加载岗位描述...")
    jd = load_jd(JD_PATH)
    print(f"    读取成功（{len(jd)} 字符）")
    print(f"    岗位：{jd.split(chr(10))[0] if chr(10) in jd else jd[:40]}")

    # ── 初始化引擎 ──
    print("\n>>> 正在生成题库...")
    engine = InterviewEngine()
    await engine.setup(resume, jd, num_questions=5)
    print(f"    已准备 {len(engine.state.question_pool)} 道题目，面试开始！\n")

    # ── 逐题问答（只问答，不评分）──
    for round_idx in range(len(engine.state.question_pool)):
        print(f"\n{'━' * 56}")
        print(f"  第 {round_idx + 1} 题（共 {len(engine.state.question_pool)} 题）")
        print(f"{'━' * 56}")

        # ask
        question = await engine.ask()
        print(f"\n面试官：{question}")

        # 用户回答
        print()  # 空行美化
        user_answer = input("你的回答：")
        await engine.answer(user_answer)

        # 追问
        fq = await engine.follow_up()
        if fq:
            print(f"\n面试官（追问）：{fq}")
            print()
            f_answer = input("你的回答：")
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
