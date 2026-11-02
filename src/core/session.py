"""
Conversational Session Memory Manager for Company Brain on FalkorDB.

Maintains sliding-window multi-turn conversation history for each session_id,
formatting history as google.genai.types.Content objects to inject into
Gemini's chats.create(history=...) call.
"""

import time
import threading
from typing import Dict, List, Optional
from google.genai import types


class SessionManager:
    """
    Thread-safe conversational session store with idle TTL eviction
    and configurable sliding-window turn pruning.
    """
    def __init__(self, ttl_seconds: int = 7200, max_turns: int = 6):
        """
        Args:
            ttl_seconds: Idle time (in seconds) after which a session expires (default: 2 hours).
            max_turns: Maximum conversation turns (user + model messages) to preserve in context (default: 6 turns / 3 exchanges).
        """
        self.ttl_seconds = ttl_seconds
        self.max_turns = max_turns
        self._sessions: Dict[str, List[types.Content]] = {}
        self._last_accessed: Dict[str, float] = {}
        self._lock = threading.Lock()

    def get_history(self, session_id: Optional[str]) -> List[types.Content]:
        """
        Retrieves the sliding-window history for the given session_id.
        Returns an empty list if session_id is None or not found.
        """
        if not session_id:
            return []

        with self._lock:
            self._cleanup_expired()
            if session_id not in self._sessions:
                return []
            self._last_accessed[session_id] = time.time()
            # Return last N turns
            return list(self._sessions[session_id][-self.max_turns:])

    def add_turn(self, session_id: Optional[str], user_text: str, model_text: str):
        """
        Records a completed conversational exchange (user prompt + synthesized answer).
        """
        if not session_id or not user_text or not model_text:
            return

        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = []

            # Append user turn
            self._sessions[session_id].append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=user_text)]
                )
            )
            # Append model turn
            self._sessions[session_id].append(
                types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=model_text)]
                )
            )

            # Prune to max_turns * 2 to keep store compact
            if len(self._sessions[session_id]) > self.max_turns * 2:
                self._sessions[session_id] = self._sessions[session_id][-self.max_turns:]

            self._last_accessed[session_id] = time.time()

    def clear_session(self, session_id: Optional[str]) -> bool:
        """
        Clears conversation history for the given session_id.
        """
        if not session_id:
            return False

        with self._lock:
            removed = self._sessions.pop(session_id, None) is not None
            self._last_accessed.pop(session_id, None)
            return removed

    def get_active_sessions_count(self) -> int:
        """Returns the number of active unexpired sessions."""
        with self._lock:
            self._cleanup_expired()
            return len(self._sessions)

    def get_stats(self) -> dict:
        """Returns session manager diagnostics."""
        with self._lock:
            self._cleanup_expired()
            return {
                "active_sessions": len(self._sessions),
                "ttl_seconds": self.ttl_seconds,
                "max_turns": self.max_turns
            }

    def _cleanup_expired(self):
        """Evicts sessions that have exceeded the idle TTL."""
        now = time.time()
        expired = [
            sid for sid, ts in self._last_accessed.items()
            if (now - ts) > self.ttl_seconds
        ]
        for sid in expired:
            self._sessions.pop(sid, None)
            self._last_accessed.pop(sid, None)


# Global singleton instance
session_manager = SessionManager()

