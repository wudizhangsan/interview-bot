from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from .question import QuestionItem
from .evaluation import QuestionEvaluation, InterviewEvaluation


class InterviewStatus(str, Enum):
    idle = "idle"
    ready = "ready"
    in_progress = "in_progress"
    finished = "finished"


class InterviewConfig(BaseModel):
    """面试配置"""
    resume: str = ""
    jd: str = ""
    style: str = "technical"  # 面试风格：technical / behavioral / mixed
    difficulty: str = "medium"  # 难度：easy / medium / hard
    num_questions: int = 5
    focus_areas: list[str] = Field(default_factory=list)  # 侧重点


class DrillDownRound(BaseModel):
    """追问子轮次"""
    question: str
    answer: str = ""


class InterviewRound(BaseModel):
    """单轮问答记录"""
    question: QuestionItem
    answer: str = ""
    drill_down: Optional[DrillDownRound] = None
    evaluation: Optional[QuestionEvaluation] = None


class InterviewState(BaseModel):
    """完整面试状态"""
    status: InterviewStatus = InterviewStatus.idle
    config: InterviewConfig = Field(default_factory=InterviewConfig)
    question_pool: list[QuestionItem] = Field(default_factory=list)
    rounds: list[InterviewRound] = Field(default_factory=list)
    current_round_index: int = -1
    final_evaluation: Optional[InterviewEvaluation] = None
