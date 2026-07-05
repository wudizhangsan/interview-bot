"""API 路由测试：使用 FastAPI TestClient + mock 避免真实 LLM 调用"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.deps import get_session_manager
from schema.engine import InterviewState, InterviewStatus, InterviewConfig
from schema.evaluation import (
    DimensionScore,
    InterviewEvaluation,
    QuestionEvaluation,
)
from schema.question import QuestionItem

client = TestClient(app)


# ============================================================
#  KB 路由测试
# ============================================================


class TestKBRoutes:
    """知识库管理路由测试"""

    @patch("api.kb_routes.list_topics")
    def test_get_topics(self, mock_list):
        mock_list.return_value = {"python_gil": 3, "django_orm": 3}
        resp = client.get("/api/kb/topics")
        assert resp.status_code == 200
        assert resp.json() == {"python_gil": 3, "django_orm": 3}

    @patch("api.kb_routes.load_kb")
    @patch("api.kb_routes.validate_topic_name", return_value=True)
    def test_get_topic_exists(self, mock_validate, mock_load):
        mock_load.return_value = [
            {"question": "Q1?", "answer": "A1"},
            {"question": "Q2?", "answer": "A2"},
        ]
        resp = client.get("/api/kb/topics/python_gil")
        assert resp.status_code == 200
        data = resp.json()
        assert data["topic"] == "python_gil"
        assert len(data["questions"]) == 2

    @patch("api.kb_routes.load_kb")
    @patch("api.kb_routes.validate_topic_name", return_value=True)
    def test_get_topic_not_found(self, mock_validate, mock_load):
        mock_load.side_effect = FileNotFoundError
        resp = client.get("/api/kb/topics/unknown")
        assert resp.status_code == 404
        assert "不存在" in resp.json()["detail"]

    @patch("api.kb_routes.validate_topic_name", return_value=False)
    def test_get_topic_invalid_name(self, mock_validate):
        # 使用含 . 的名称（不会被路由 normalize，但 validate 会拒绝）
        resp = client.get("/api/kb/topics/test.name")
        assert resp.status_code == 400

    @patch("api.kb_routes.kb_generator.generate", new_callable=AsyncMock)
    @patch("api.kb_routes.save_kb")
    @patch("api.kb_routes.validate_topic_name", return_value=True)
    def test_create_topic_with_text(
        self, mock_validate, mock_save, mock_generate
    ):
        mock_generate.return_value = [
            QuestionItem(question="问题1", answer="答案1"),
            QuestionItem(question="问题2", answer="答案2"),
        ]
        resp = client.post(
            "/api/kb/topics",
            data={"topic_name": "my_topic", "text": "some content"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["topic"] == "my_topic"
        assert data["question_count"] == 2
        assert len(data["questions"]) == 2
        mock_save.assert_called_once()

    @patch("api.kb_routes.validate_topic_name", return_value=True)
    def test_create_topic_no_content(self, mock_validate):
        """既不提供 text 也不提供 file → 400"""
        resp = client.post(
            "/api/kb/topics",
            data={"topic_name": "empty_topic"},
        )
        assert resp.status_code == 400
        assert "请提供文本内容" in resp.json()["detail"]

    @patch("api.kb_routes.validate_topic_name", return_value=False)
    def test_create_topic_invalid_name(self, mock_validate):
        resp = client.post(
            "/api/kb/topics",
            data={"topic_name": "../evil", "text": "content"},
        )
        assert resp.status_code == 400
        assert "只允许" in resp.json()["detail"]

    @patch("api.kb_routes.delete_kb")
    @patch("api.kb_routes.validate_topic_name", return_value=True)
    def test_delete_topic_success(self, mock_validate, mock_delete):
        mock_delete.return_value = True
        resp = client.delete("/api/kb/topics/my_topic")
        assert resp.status_code == 200
        assert "已删除" in resp.json()["message"]

    @patch("api.kb_routes.delete_kb")
    @patch("api.kb_routes.validate_topic_name", return_value=True)
    def test_delete_topic_not_found(self, mock_validate, mock_delete):
        mock_delete.return_value = False
        resp = client.delete("/api/kb/topics/ghost")
        assert resp.status_code == 404
        assert "不存在" in resp.json()["detail"]

    @patch("api.kb_routes.validate_topic_name", return_value=False)
    def test_delete_topic_invalid_name(self, mock_validate):
        resp = client.delete("/api/kb/topics/test.name")
        assert resp.status_code == 400

    @patch("api.kb_routes.kb_generator.generate", new_callable=AsyncMock)
    @patch("api.kb_routes.save_kb")
    @patch("api.kb_routes.validate_topic_name", return_value=True)
    def test_create_topic_with_pdf_upload(
        self, mock_validate, mock_save, mock_generate
    ):
        """通过上传 PDF 创建知识点"""
        mock_generate.return_value = [
            QuestionItem(question="Q1?", answer="A1"),
        ]
        # 为了不依赖真实 PDF 文件，用 patch 让 parse_file 返回模拟文本
        with patch("api.kb_routes.parse_file", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = "模拟 PDF 解析文本"
            resp = client.post(
                "/api/kb/topics",
                data={"topic_name": "pdf_topic"},
                files={"file": ("test.pdf", b"%PDF-dummy-content", "application/pdf")},
            )
        assert resp.status_code == 200
        assert resp.json()["topic"] == "pdf_topic"
        assert resp.json()["question_count"] == 1


# ============================================================
#  面试流程路由测试
# ============================================================


def _make_mock_state(**overrides) -> InterviewState:
    """创建一个默认 InterviewState，可覆盖特定字段"""
    defaults = dict(
        status=InterviewStatus.ready,
        config=InterviewConfig(resume="r", jd="j"),
        question_pool=[
            QuestionItem(question="问题1", answer="答案1"),
            QuestionItem(question="问题2", answer="答案2"),
        ],
        rounds=[],
        current_round_index=-1,
    )
    defaults.update(overrides)
    return InterviewState(**defaults)


def _make_mock_engine():
    """创建一个装配好的 mock InterviewEngine"""
    engine = MagicMock()
    engine.state = _make_mock_state()
    engine.setup = AsyncMock()
    engine.ask = AsyncMock(return_value="问题1")
    engine.answer = AsyncMock()
    engine.follow_up = AsyncMock(return_value=None)
    engine.skip_follow_up = AsyncMock()
    engine.evaluate_round = AsyncMock(
        return_value=QuestionEvaluation(
            question="问题1", score=4,
            highlights="好", missing_points="无", improvement="继续",
        )
    )
    engine.finish = AsyncMock(
        return_value=InterviewEvaluation(
            overall_score=85.0,
            dimensions=[DimensionScore(name="技术深度", score=80.0)],
            qa_evaluations=[],
            final_verdict="通过",
            salary_fit="匹配",
            improvement_tips=["继续学习"],
        )
    )
    return engine


@pytest.fixture
def mock_session_manager():
    """创建一个 mock SessionManager 并注入到 app 依赖"""
    sm = MagicMock()
    engine = _make_mock_engine()
    sm.create.return_value = "test-session-id"
    sm.get.return_value = engine
    sm.delete.return_value = True

    app.dependency_overrides[get_session_manager] = lambda: sm
    yield sm
    app.dependency_overrides.clear()


class TestInterviewRoutes:
    """面试流程路由测试"""

    def test_create_session(self, mock_session_manager):
        mock_session_manager.create.return_value = "sid-123"
        resp = client.post(
            "/api/interview/sessions",
            json={"resume": "熟悉Python", "jd": "招聘后端", "num_questions": 2},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "sid-123"
        assert data["num_questions"] == 2
        assert data["status"] == "ready"

    def test_create_session_failure_cleans_up(self, mock_session_manager):
        """setup 失败时应当删除已创建的会话"""
        engine = mock_session_manager.get.return_value
        engine.setup.side_effect = ValueError("初始化失败")

        resp = client.post(
            "/api/interview/sessions",
            json={"resume": "", "jd": ""},
        )
        assert resp.status_code == 400
        assert "初始化失败" in resp.json()["detail"]
        # 确认 cleanup 被调用
        mock_session_manager.delete.assert_called_once()

    def test_ask_question(self, mock_session_manager):
        engine = mock_session_manager.get.return_value
        engine.state = _make_mock_state(current_round_index=0)
        resp = client.post("/api/interview/sessions/test-id/ask")
        assert resp.status_code == 200
        data = resp.json()
        assert data["question"] == "问题1"
        assert data["round_index"] == 0
        assert data["total"] == 2

    def test_ask_question_all_done(self, mock_session_manager):
        engine = mock_session_manager.get.return_value
        engine.ask.side_effect = RuntimeError("所有题目已问完")

        resp = client.post("/api/interview/sessions/test-id/ask")
        assert resp.status_code == 400
        assert "所有题目已问完" in resp.json()["detail"]

    def test_answer(self, mock_session_manager):
        resp = client.post(
            "/api/interview/sessions/test-id/answer",
            json={"answer": "我的回答"},
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "回答已记录"

    def test_answer_no_question(self, mock_session_manager):
        engine = mock_session_manager.get.return_value
        engine.answer.side_effect = RuntimeError("当前没有进行中的题目")

        resp = client.post(
            "/api/interview/sessions/test-id/answer",
            json={"answer": "回答"},
        )
        assert resp.status_code == 400

    def test_follow_up_returns_question(self, mock_session_manager):
        engine = mock_session_manager.get.return_value
        engine.follow_up = AsyncMock(return_value="追问题目？")

        resp = client.get("/api/interview/sessions/test-id/follow-up")
        assert resp.status_code == 200
        data = resp.json()
        assert data["needs_follow_up"] is True
        assert data["question"] == "追问题目？"

    def test_follow_up_no_question(self, mock_session_manager):
        """不需要追问时返回 False"""
        resp = client.get("/api/interview/sessions/test-id/follow-up")
        assert resp.status_code == 200
        data = resp.json()
        assert data["needs_follow_up"] is False
        assert data["question"] is None

    def test_skip_follow_up(self, mock_session_manager):
        resp = client.post("/api/interview/sessions/test-id/skip-follow-up")
        assert resp.status_code == 200
        assert "已跳过" in resp.json()["message"]

    def test_evaluate_round(self, mock_session_manager):
        resp = client.post("/api/interview/sessions/test-id/evaluate-round")
        assert resp.status_code == 200
        data = resp.json()
        assert data["question"] == "问题1"
        assert data["score"] == 4

    def test_evaluate_round_no_question(self, mock_session_manager):
        engine = mock_session_manager.get.return_value
        engine.evaluate_round.side_effect = RuntimeError("当前没有进行中的题目")

        resp = client.post("/api/interview/sessions/test-id/evaluate-round")
        assert resp.status_code == 400

    def test_finish(self, mock_session_manager):
        resp = client.post("/api/interview/sessions/test-id/finish")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_score"] == 85.0
        assert data["final_verdict"] == "通过"

    def test_get_state(self, mock_session_manager):
        resp = client.get("/api/interview/sessions/test-id/state")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"

    def test_delete_session(self, mock_session_manager):
        resp = client.delete("/api/interview/sessions/test-id")
        assert resp.status_code == 200
        assert "已删除" in resp.json()["message"]

    def test_delete_session_not_found(self, mock_session_manager):
        mock_session_manager.delete.return_value = False
        resp = client.delete("/api/interview/sessions/ghost")
        assert resp.status_code == 404

    def test_nonexistent_session(self, mock_session_manager):
        """会话不存在时所有接口返回 404"""
        mock_session_manager.get.return_value = None

        endpoints = [
            ("POST", "/api/interview/sessions/nonexistent/ask"),
            ("POST", "/api/interview/sessions/nonexistent/answer", {"answer": "x"}),
            ("GET", "/api/interview/sessions/nonexistent/follow-up"),
            ("POST", "/api/interview/sessions/nonexistent/skip-follow-up"),
            ("POST", "/api/interview/sessions/nonexistent/evaluate-round"),
            ("POST", "/api/interview/sessions/nonexistent/finish"),
            ("GET", "/api/interview/sessions/nonexistent/state"),
        ]

        for method, path, *body in endpoints:
            if method == "POST":
                kwargs = {"json": body[0]} if body else {}
                resp = client.post(path, **kwargs)
            else:
                resp = client.get(path)
            assert resp.status_code == 404, f"{method} {path} should be 404"
            assert "不存在" in resp.json()["detail"], f"{method} {path} message mismatch"


# ============================================================
#  根路径测试
# ============================================================


def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "AI Interview Pilot" in data["message"]
