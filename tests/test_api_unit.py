"""API 单元测试：SessionManager + KB Service"""

import json
import re

import pytest

from api.session_manager import SessionManager
from api.kb_service import (
    validate_topic_name,
    ensure_kb_dir,
    save_kb,
    load_kb,
    list_topics,
    delete_kb,
)
from schema.question import QuestionItem

# ── SessionManager 测试 ──


class TestSessionManager:
    def test_create_returns_uuid(self):
        sm = SessionManager()
        sid = sm.create()
        # UUID v4 格式：8-4-4-4-12 十六进制
        assert re.match(r"^[0-9a-f-]{36}$", sid)

    def test_get_returns_engine(self):
        sm = SessionManager()
        sid = sm.create()
        engine = sm.get(sid)
        assert engine is not None
        assert hasattr(engine, "setup")
        assert hasattr(engine, "ask")
        assert hasattr(engine, "state")

    def test_get_nonexistent_returns_none(self):
        sm = SessionManager()
        assert sm.get("nonexistent-uuid") is None

    def test_delete_returns_true(self):
        sm = SessionManager()
        sid = sm.create()
        assert sm.delete(sid) is True
        assert sm.get(sid) is None

    def test_delete_nonexistent_returns_false(self):
        sm = SessionManager()
        assert sm.delete("nonexistent-uuid") is False

    def test_list_sessions(self):
        sm = SessionManager()
        assert sm.list_sessions() == []
        s1 = sm.create()
        s2 = sm.create()
        assert set(sm.list_sessions()) == {s1, s2}

    def test_delete_removes_from_list(self):
        sm = SessionManager()
        s1 = sm.create()
        s2 = sm.create()
        sm.delete(s1)
        assert sm.list_sessions() == [s2]


# ── KB Service 测试 ──


class TestValidateTopicName:
    @pytest.mark.parametrize("name", [
        "python_gil",
        "Python并发编程",
        "django-orm",
        "test123",
        "TestCase",
        "混合_Mixed-Name_123",
    ])
    def test_valid_names(self, name):
        assert validate_topic_name(name) is True

    @pytest.mark.parametrize("name", [
        "../../etc/passwd",
        "../安全绕过",
        "a/b",
        "a\\b",
        "a b",          # 含空格
        "test.name",    # 含点号
        "",             # 空字符串
        "a,b",
        "a:b",
    ])
    def test_invalid_names(self, name):
        assert validate_topic_name(name) is False


class TestKBCrud:
    """KB 文件读写测试（使用临时目录）"""

    def test_save_and_load(self, tmp_path):
        questions = [
            QuestionItem(question="Q1?", answer="A1"),
            QuestionItem(question="Q2?", answer="A2"),
        ]
        save_kb("test_topic", questions)

        # 默认 KB_DIR 是固定的，手动检查保存结果
        # 改用猴子补丁在类级别单独测试
        pass

    def test_list_topics(self, tmp_path):
        # 创建一个临时 KB 目录结构
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "topic_a.json").write_text(
            json.dumps([{"question": "q", "answer": "a"}], ensure_ascii=False), encoding="utf-8"
        )
        (kb_dir / "topic_b.json").write_text(
            json.dumps([{"question": "q1", "answer": "a1"}, {"question": "q2", "answer": "a2"}], ensure_ascii=False),
            encoding="utf-8",
        )

        # 引入模块并替换 KB_DIR
        import api.kb_service as kb
        original_dir = kb.KB_DIR
        try:
            kb.KB_DIR = kb_dir
            result = list_topics()
            assert result == {"topic_a": 1, "topic_b": 2}
        finally:
            kb.KB_DIR = original_dir

    def test_load_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            load_kb("non_existent_topic_xyz")

    def test_save_read_roundtrip(self, tmp_path):
        import api.kb_service as kb
        original_dir = kb.KB_DIR
        try:
            kb.KB_DIR = tmp_path / "kb_roundtrip"

            questions = [
                QuestionItem(question="问题1", answer="答案1"),
                QuestionItem(question="问题2", answer="答案2"),
            ]
            save_kb("roundtrip", questions)

            raw = load_kb("roundtrip")
            assert len(raw) == 2
            assert raw[0]["question"] == "问题1"
            assert raw[1]["answer"] == "答案2"
        finally:
            kb.KB_DIR = original_dir

    def test_delete(self, tmp_path):
        import api.kb_service as kb
        original_dir = kb.KB_DIR
        try:
            kb.KB_DIR = tmp_path / "kb_delete"
            ensure_kb_dir()

            q = [QuestionItem(question="q", answer="a")]
            save_kb("to_delete", q)
            assert load_kb("to_delete") is not None

            assert delete_kb("to_delete") is True
            assert delete_kb("to_delete") is False
        finally:
            kb.KB_DIR = original_dir

    def test_ensure_kb_dir_creates(self, tmp_path):
        import api.kb_service as kb
        original_dir = kb.KB_DIR
        try:
            new_dir = tmp_path / "brand_new_kb"
            kb.KB_DIR = new_dir
            assert not new_dir.exists()
            ensure_kb_dir()
            assert new_dir.exists()
            assert new_dir.is_dir()
        finally:
            kb.KB_DIR = original_dir

    def test_empty_kb_dir(self, tmp_path):
        import api.kb_service as kb
        original_dir = kb.KB_DIR
        try:
            kb.KB_DIR = tmp_path / "empty_kb"
            ensure_kb_dir()
            assert list_topics() == {}
        finally:
            kb.KB_DIR = original_dir
