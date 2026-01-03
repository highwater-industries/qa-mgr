"""HTTP client for QA Manager API communication."""

import logging
from uuid import UUID
from datetime import datetime, timezone
import httpx
from typing import Any

from .config import WorkerConfig

logger = logging.getLogger(__name__)


class APIClient:
    """HTTP client for communicating with QA Manager API."""
    
    def __init__(self, config: WorkerConfig):
        self.config = config
        self.base_url = config.api_base_url.rstrip("/")
        self._worker_id: UUID | None = None
        
    @property
    def worker_id(self) -> UUID | None:
        """Get the registered worker ID."""
        return self._worker_id
    
    @worker_id.setter
    def worker_id(self, value: UUID | None):
        """Set the worker ID after registration."""
        self._worker_id = value
    
    def _get_headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        headers = {
            "Content-Type": "application/json",
        }
        if self.config.api_key:
            headers["X-API-Key"] = self.config.api_key
        if self.config.workspace_id:
            headers["X-Workspace-ID"] = self.config.workspace_id
        return headers
    
    async def register(self) -> dict[str, Any]:
        """
        Register the worker with the API.
        
        Returns:
            dict with worker_id, message, heartbeat_interval
            
        Raises:
            httpx.HTTPStatusError: If registration fails
        """
        url = f"{self.base_url}/quarion/api/v1/workers/register"
        
        payload = {
            "name": self.config.worker_name,
            "worker_type": self.config.worker_type,
            "hostname": self.config.hostname,
            "ip_address": self.config.ip_address,
            "version": "1.0.0",
            "os": self.config.os_name,
            "arch": self.config.arch,
            "capabilities": {
                "python_version": self.config.python_version,
                "test_runner": self.config.test_runner_command,
            },
            "tags": self.config.tags_list,
            "max_concurrent_runs": self.config.max_concurrent_runs,
        }
        
        logger.info(f"Registering worker '{self.config.worker_name}' at {url}")
        
        async with httpx.AsyncClient(timeout=self.config.api_timeout) as client:
            response = await client.post(
                url,
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            
            data = response.json()
            self._worker_id = UUID(data["worker_id"])
            logger.info(f"Worker registered with ID: {self._worker_id}")
            
            return data
    
    async def send_heartbeat(
        self,
        status: str = "idle",
        current_active_runs: int = 0,
        health_metrics: dict | None = None,
    ) -> dict[str, Any] | None:
        """
        Send heartbeat to the API.
        
        Args:
            status: Worker status (idle, busy, offline, error)
            current_active_runs: Number of currently active test runs
            health_metrics: Optional health metrics (CPU, memory, etc.)
            
        Returns:
            Worker data from API, or None if heartbeat fails
        """
        if not self._worker_id:
            logger.warning("Cannot send heartbeat: worker not registered")
            return None
        
        url = f"{self.base_url}/quarion/api/v1/workers/{self._worker_id}/heartbeat"
        
        payload = {
            "status": status,
            "current_active_runs": current_active_runs,
            "health_metrics": health_metrics or {},
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.config.heartbeat_timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.TimeoutException:
            logger.warning(f"Heartbeat timeout for worker {self._worker_id}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"Heartbeat failed: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
            return None
    
    async def update_test_run_status(
        self,
        test_run_id: UUID,
        status: str,
        result_summary: dict | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Update test run status.
        
        This will be implemented when we add the test run update endpoint.
        For now, test run updates happen through the Celery task.
        """
        # Placeholder for future implementation
        logger.debug(f"Would update test run {test_run_id} to status {status}")
        return None
    
    async def upload_test_results(
        self,
        test_run_id: UUID,
        results_file: str,
    ) -> dict[str, Any] | None:
        """
        Upload test results file to the API.
        
        This will be implemented when we add the results upload endpoint.
        """
        # Placeholder for future implementation
        logger.debug(f"Would upload results for test run {test_run_id}")
        return None


