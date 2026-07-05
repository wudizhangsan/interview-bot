"""面试流程路由"""

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_session_manager
from api.session_manager import SessionManager
from agent.candidate_agent import CandidateAgent
from schema.evaluation import InterviewEvaluation, QuestionEvaluation

router = APIRouter(prefix="/api/interview", tags=["面试流程"])


# ── 请求体模型 ──


class CreateSessionRequest(BaseModel):
    resume: str
    jd: str
    num_questions: int = 5
    style: str = "technical"
    difficulty: str = "medium"


class AnswerRequest(BaseModel):
    answer: str


class AutoAnswerRequest(BaseModel):
    level: str = "mid"


# ── 辅助函数 ──


def _get_engine(session_id: str, sm: SessionManager):
    engine = sm.get(session_id)
    if engine is None:
        raise HTTPException(status_code=404, detail=f"会话 '{session_id}' 不存在")
    return engine


# ── 路由 ──


@router.post("/sessions", summary="创建面试会话")
async def create_session(
    body: CreateSessionRequest,
    sm: SessionManager = Depends(get_session_manager),
):
    session_id = sm.create()
    engine = sm.get(session_id)
    try:
        await engine.setup(
            resume=body.resume,
            jd=body.jd,
            num_questions=body.num_questions,
            style=body.style,
            difficulty=body.difficulty,
        )
    except Exception as e:
        sm.delete(session_id)
        raise HTTPException(status_code=400, detail=f"初始化面试失败: {e}")

    return {
        "session_id": session_id,
        "num_questions": len(engine.state.question_pool),
        "status": engine.state.status.value,
    }


@router.post("/sessions/{session_id}/ask", summary="获取下一道题")
async def ask_question(
    session_id: str,
    sm: SessionManager = Depends(get_session_manager),
):
    engine = _get_engine(session_id, sm)
    try:
        question = await engine.ask()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "session_id": session_id,
        "question": question,
        "round_index": engine.state.current_round_index,
        "total": len(engine.state.question_pool),
    }


@router.post("/sessions/{session_id}/answer", summary="提交回答")
async def submit_answer(
    session_id: str,
    body: AnswerRequest,
    sm: SessionManager = Depends(get_session_manager),
):
    engine = _get_engine(session_id, sm)
    try:
        await engine.answer(body.answer)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"message": "回答已记录"}


@router.post("/sessions/{session_id}/auto-answer", summary="AI 自动回答当前题目")
async def auto_answer(
    session_id: str,
    body: AutoAnswerRequest = AutoAnswerRequest(),
    sm: SessionManager = Depends(get_session_manager),
):
    """用 CandidateAgent 自动回答当前轮次的题目（含追问）"""
    engine = _get_engine(session_id, sm)
    current = engine.current_round
    if current is None:
        raise HTTPException(status_code=400, detail="当前没有进行中的题目")

    # 确定题目文本（追问阶段用追问问题）
    if engine._awaiting_drill_down and current.drill_down:
        question_text = current.drill_down.question
    else:
        question_text = current.question.question

    # 创建候选人并生成回答
    candidate = CandidateAgent(ability=body.level)
    answer_text = await candidate.answer(question_text)

    # 存入引擎
    await engine.answer(answer_text)

    return {"answer": answer_text}


@router.get("/sessions/{session_id}/follow-up", summary="检查是否需要追问")
async def check_follow_up(
    session_id: str,
    sm: SessionManager = Depends(get_session_manager),
):
    engine = _get_engine(session_id, sm)
    try:
        follow_up_question = await engine.follow_up()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if follow_up_question:
        return {
            "needs_follow_up": True,
            "question": follow_up_question,
        }
    return {"needs_follow_up": False, "question": None}


@router.post("/sessions/{session_id}/skip-follow-up", summary="跳过追问")
async def skip_follow_up(
    session_id: str,
    sm: SessionManager = Depends(get_session_manager),
):
    engine = _get_engine(session_id, sm)
    await engine.skip_follow_up()
    return {"message": "已跳过追问"}


@router.post("/sessions/{session_id}/evaluate-round", summary="评价当前轮次")
async def evaluate_round(
    session_id: str,
    sm: SessionManager = Depends(get_session_manager),
):
    engine = _get_engine(session_id, sm)
    try:
        evaluation: QuestionEvaluation = await engine.evaluate_round()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return evaluation.model_dump()


@router.post("/sessions/{session_id}/finish", summary="整体评价，结束面试")
async def finish_interview(
    session_id: str,
    sm: SessionManager = Depends(get_session_manager),
):
    engine = _get_engine(session_id, sm)
    try:
        evaluation: InterviewEvaluation = await engine.finish()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"评价生成失败: {e}")

    return evaluation.model_dump()


@router.get("/sessions/{session_id}/state", summary="查询当前面试状态")
async def get_state(
    session_id: str,
    sm: SessionManager = Depends(get_session_manager),
):
    engine = _get_engine(session_id, sm)
    state = engine.state
    return state.model_dump()


@router.delete("/sessions/{session_id}", summary="删除会话")
async def delete_session(
    session_id: str,
    sm: SessionManager = Depends(get_session_manager),
):
    if not sm.delete(session_id):
        raise HTTPException(status_code=404, detail=f"会话 '{session_id}' 不存在")
    return {"message": f"会话 '{session_id}' 已删除"}
