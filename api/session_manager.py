"""In-memory InterviewEngine 会话管理"""

import uuid
from typing import Optional

from engine.interview_engine import InterviewEngine


class SessionManager:
    """管理 InterviewEngine 实例的生命周期"""

    def __init__(self):
        self._sessions: dict[str, InterviewEngine] = {}

    def create(self) -> str:
        """创建一个新的面试会话，返回 session_id"""
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = InterviewEngine()
        return session_id

    def get(self, session_id: str) -> Optional[InterviewEngine]:
        """获取指定会话的 InterviewEngine 实例"""
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        """删除指定会话，返回是否成功"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def list_sessions(self) -> list[str]:
        """列出所有会话 ID"""
        return list(self._sessions.keys())
