from pydantic import BaseModel


class QuestionEvaluation(BaseModel):
    """单个题目的评价结果"""
    question: str = ""
    score: int = 0  # 1-5分
    highlights: str = ""  # 回答亮点
    missing_points: str = ""  # 缺失关键点
    improvement: str = ""  # 改进建议


class DimensionScore(BaseModel):
    """能力维度评分"""
    name: str  # 维度名称，如"技术深度"
    score: float  # 0-100分
    summary: str = ""  # 该维度简要评语


class InterviewEvaluation(BaseModel):
    """整体面试评价报告"""
    overall_score: float = 0  # 总分（百分制）
    dimensions: list[DimensionScore]  # 各维度评分
    qa_evaluations: list[QuestionEvaluation]  # 逐题评价
    final_verdict: str = ""  # 终期判决：通过 / 待定 / 淘汰
    salary_fit: str = ""  # 建议薪资匹配度
    improvement_tips: list[str]  # 通关锦囊（查漏补缺的知识盲区）
