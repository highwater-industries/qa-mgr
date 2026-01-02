"""Celery application configuration for asynchronous test execution."""

from celery import Celery
from pydantic_settings import BaseSettings, SettingsConfigDict


class CelerySettings(BaseSettings):
    """Settings for Celery configuration."""
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    # RabbitMQ broker URL
    celery_broker_url: str = "amqp://guest:guest@localhost:5672//"
    
    # Result backend (we'll use database, but RabbitMQ RPC can also work)
    celery_result_backend: str = "rpc://"
    
    # Task settings
    celery_task_track_started: bool = True
    celery_task_time_limit: int = 28800  # Default 8 hours max per task (configurable via env)
    celery_task_soft_time_limit: int | None = None  # If None, calculated as 95% of time_limit
    
    # Worker settings
    celery_worker_prefetch_multiplier: int = 1  # Only fetch one task at a time
    celery_worker_max_tasks_per_child: int = 1000
    
    # Result settings
    celery_result_expires: int = 86400  # Keep results for 24 hours


settings = CelerySettings()

# Calculate soft time limit if not explicitly set (95% of hard limit)
soft_time_limit = settings.celery_task_soft_time_limit
if soft_time_limit is None:
    soft_time_limit = int(settings.celery_task_time_limit * 0.95)

# Create Celery app
celery_app = Celery(
    "qa_mgr",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Configure Celery
celery_app.conf.update(
    task_track_started=settings.celery_task_track_started,
    task_time_limit=settings.celery_task_time_limit,
    task_soft_time_limit=soft_time_limit,
    worker_prefetch_multiplier=settings.celery_worker_prefetch_multiplier,
    worker_max_tasks_per_child=settings.celery_worker_max_tasks_per_child,
    result_expires=settings.celery_result_expires,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Task discovery
    imports=["tasks"],
)
