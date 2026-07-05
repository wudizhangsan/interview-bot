"""FastAPI 依赖注入"""

from api.session_manager import SessionManager

_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """获取全局 SessionManager 单例"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
