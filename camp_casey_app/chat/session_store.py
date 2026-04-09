from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import TypedDict


class ChatMessage(TypedDict):
    role: str       # "user" | "assistant"
    content: str
    ts: float       # unix timestamp


_MAX_HISTORY_PER_SESSION = 40   # 최대 메시지 수 (20턴)
_SESSION_TTL_SECONDS = 60 * 60 * 6  # 6시간 비활동 시 만료
_MAX_SESSIONS = 500             # 최대 동시 세션 수


class SessionStore:
    """
    Thread-safe in-memory 대화 세션 저장소.

    세션은 마지막 활동 기준 TTL 이후 자동 만료되며,
    최대 세션 수 초과 시 가장 오래된 것부터 제거(LRU 방식).
    """

    def __init__(
        self,
        max_history: int = _MAX_HISTORY_PER_SESSION,
        ttl_seconds: float = _SESSION_TTL_SECONDS,
        max_sessions: int = _MAX_SESSIONS,
    ) -> None:
        self._lock = threading.Lock()
        self._sessions: OrderedDict[str, list[ChatMessage]] = OrderedDict()
        self._last_active: dict[str, float] = {}
        self.max_history = max_history
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions

    # ── Public API ──────────────────────────────────────────────────────────

    def get_history(self, session_id: str) -> list[ChatMessage]:
        """세션의 대화 히스토리를 반환한다. 세션이 없으면 빈 리스트."""
        with self._lock:
            self._evict_expired()
            return list(self._sessions.get(session_id, []))

    def append(self, session_id: str, role: str, content: str) -> None:
        """메시지를 세션에 추가한다."""
        with self._lock:
            self._evict_expired()
            self._touch(session_id)
            msg: ChatMessage = {"role": role, "content": content, "ts": time.time()}
            self._sessions[session_id].append(msg)
            # 최대 개수 초과 시 오래된 메시지 삭제 (앞에서 2개씩 제거해 턴 단위 유지)
            while len(self._sessions[session_id]) > self.max_history:
                self._sessions[session_id].pop(0)

    def clear(self, session_id: str) -> None:
        """세션 히스토리를 초기화한다."""
        with self._lock:
            self._sessions.pop(session_id, None)
            self._last_active.pop(session_id, None)

    def session_count(self) -> int:
        with self._lock:
            self._evict_expired()
            return len(self._sessions)

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _touch(self, session_id: str) -> None:
        """세션 최종 활동 시간을 갱신하고 OrderedDict 내 순서를 최신으로 이동."""
        now = time.time()
        self._last_active[session_id] = now
        if session_id not in self._sessions:
            # 최대 세션 수 초과 시 가장 오래된 세션 제거
            if len(self._sessions) >= self.max_sessions:
                oldest = next(iter(self._sessions))
                self._sessions.pop(oldest, None)
                self._last_active.pop(oldest, None)
            self._sessions[session_id] = []
        else:
            self._sessions.move_to_end(session_id)

    def _evict_expired(self) -> None:
        """TTL이 지난 세션을 제거한다."""
        now = time.time()
        expired = [
            sid
            for sid, last in self._last_active.items()
            if now - last > self.ttl_seconds
        ]
        for sid in expired:
            self._sessions.pop(sid, None)
            self._last_active.pop(sid, None)
