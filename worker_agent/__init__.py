"""Worker Agent for QA Manager.

This package provides a worker agent that runs on worker machines to:
- Register with the QA Manager API
- Send periodic heartbeats
- Receive and execute test runs via Celery
- Report results back to the API
"""

from .agent import WorkerAgent
from .config import WorkerConfig

__all__ = ["WorkerAgent", "WorkerConfig"]


