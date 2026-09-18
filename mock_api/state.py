"""
In-memory state management for the Mock External API.
"""

import time
from typing import Dict, Any


class MockAPIState:
    """Manages runtime statistics and request counters for the Mock API."""

    def __init__(self) -> None:
        self.total_requests: int = 0
        self.start_time: float = time.time()

    def increment_requests(self) -> int:
        """Increments the request count and returns the updated count."""
        self.total_requests += 1
        return self.total_requests

    def get_stats(self) -> Dict[str, Any]:
        """Returns the current runtime statistics."""
        uptime = round(time.time() - self.start_time, 2)
        return {
            "total_requests": self.total_requests,
            "uptime_seconds": uptime,
        }

    def reset(self) -> Dict[str, Any]:
        """Resets the in-memory request counter."""
        self.total_requests = 0
        return {
            "status": "reset",
            "total_requests": 0,
        }


# Global singleton state instance
state = MockAPIState()
