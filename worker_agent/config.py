"""Configuration for the worker agent."""

import platform
import socket
import os
from pydantic_settings import BaseSettings
from pydantic import Field


class WorkerConfig(BaseSettings):
    """Configuration for the worker agent.
    
    All settings can be overridden via environment variables.
    """
    
    # API connection
    api_base_url: str = Field(
        default="http://localhost:8001",
        description="Base URL of the QA Manager API",
    )
    api_key: str = Field(
        default="",
        description="API key for authentication (X-API-Key header)",
    )
    workspace_id: str = Field(
        default="",
        description="Workspace ID (X-Workspace-ID header)",
    )
    
    # Worker identity
    worker_name: str = Field(
        default_factory=lambda: socket.gethostname(),
        description="Human-readable worker name (defaults to hostname)",
    )
    worker_type: str = Field(
        default="celery",
        description="Worker type: celery, jenkins, custom",
    )
    
    # Capabilities
    worker_tags: str = Field(
        default="",
        description="Comma-separated list of tags for job targeting",
    )
    max_concurrent_runs: int = Field(
        default=1,
        description="Maximum concurrent test runs",
    )
    
    # Heartbeat settings
    heartbeat_interval: int = Field(
        default=30,
        description="Seconds between heartbeat requests",
    )
    heartbeat_timeout: int = Field(
        default=10,
        description="Timeout for heartbeat HTTP requests",
    )
    
    # Celery settings (for broker connection)
    celery_broker_url: str = Field(
        default="amqp://guest:guest@localhost:5672//",
        description="RabbitMQ broker URL for Celery",
    )
    
    # Test execution settings
    test_runner_command: str = Field(
        default="pytest",
        description="Command to run tests (pytest, unittest, etc.)",
    )
    test_output_dir: str = Field(
        default="./test_results",
        description="Directory for test result files",
    )
    
    # Timeouts
    api_timeout: int = Field(
        default=30,
        description="Timeout for API requests in seconds",
    )
    registration_retry_interval: int = Field(
        default=10,
        description="Seconds to wait before retrying registration",
    )
    max_registration_retries: int = Field(
        default=5,
        description="Maximum number of registration retry attempts",
    )
    
    model_config = {
        "env_prefix": "QA_WORKER_",
        "env_file": ".env",
        "extra": "ignore",
    }
    
    @property
    def hostname(self) -> str:
        """Get the machine hostname."""
        return socket.gethostname()
    
    @property
    def ip_address(self) -> str | None:
        """Get the machine's IP address."""
        try:
            # Connect to a remote address to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return None
    
    @property
    def os_name(self) -> str:
        """Get the operating system name."""
        return platform.system()
    
    @property
    def arch(self) -> str:
        """Get the machine architecture."""
        return platform.machine()
    
    @property
    def tags_list(self) -> list[str]:
        """Parse tags from comma-separated string."""
        if not self.worker_tags:
            return []
        return [tag.strip() for tag in self.worker_tags.split(",") if tag.strip()]
    
    @property
    def python_version(self) -> str:
        """Get Python version."""
        return platform.python_version()


