"""Main worker agent class."""

import asyncio
import signal
import logging
import sys
from uuid import UUID
from datetime import datetime, timezone
from typing import Any

from .config import WorkerConfig
from .api_client import APIClient
from .health import get_health_metrics, check_available_resources
from .executor import TestRunner, ExecutionResult

logger = logging.getLogger(__name__)


class WorkerAgent:
    """
    Worker agent that runs on worker machines.
    
    Responsibilities:
    - Register with QA Manager API on startup
    - Send periodic heartbeats
    - Listen for test execution tasks via Celery
    - Execute tests and report results
    """
    
    def __init__(self, config: WorkerConfig | None = None):
        self.config = config or WorkerConfig()
        self.api_client = APIClient(self.config)
        self.executor = TestRunner(
            test_runner=self.config.test_runner_command,
            output_dir=self.config.test_output_dir,
        )
        
        self._running = False
        self._heartbeat_task: asyncio.Task | None = None
        self._current_status = "starting"
        self._current_active_runs = 0
        
    @property
    def worker_id(self) -> UUID | None:
        """Get the worker ID (set after registration)."""
        return self.api_client.worker_id
    
    @property
    def is_registered(self) -> bool:
        """Check if the worker is registered."""
        return self.worker_id is not None
    
    @property
    def is_running(self) -> bool:
        """Check if the worker is running."""
        return self._running
    
    async def start(self):
        """
        Start the worker agent.
        
        This will:
        1. Register with the API
        2. Start the heartbeat loop
        3. Start listening for Celery tasks
        """
        logger.info(f"Starting worker agent: {self.config.worker_name}")
        self._running = True
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        # Register with API
        await self._register_with_retry()
        
        if not self.is_registered:
            logger.error("Failed to register with API, exiting")
            self._running = False
            return
        
        # Start heartbeat loop
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        # Update status to idle
        self._current_status = "idle"
        
        logger.info(f"Worker agent started successfully (ID: {self.worker_id})")
        
        # Keep running until stopped
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        
        await self.stop()
    
    async def stop(self):
        """Stop the worker agent gracefully."""
        logger.info("Stopping worker agent...")
        self._running = False
        
        # Cancel heartbeat task
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # Send final offline heartbeat
        self._current_status = "offline"
        await self.api_client.send_heartbeat(
            status="offline",
            current_active_runs=0,
        )
        
        logger.info("Worker agent stopped")
    
    async def _register_with_retry(self):
        """Register with the API, retrying on failure."""
        for attempt in range(self.config.max_registration_retries):
            try:
                result = await self.api_client.register()
                logger.info(f"Registration successful: {result.get('message', 'OK')}")
                
                # Update heartbeat interval from server if provided
                server_interval = result.get("heartbeat_interval")
                if server_interval:
                    # We could update config here if needed
                    pass
                
                return
                
            except Exception as e:
                logger.warning(
                    f"Registration attempt {attempt + 1}/{self.config.max_registration_retries} "
                    f"failed: {e}"
                )
                if attempt < self.config.max_registration_retries - 1:
                    await asyncio.sleep(self.config.registration_retry_interval)
        
        logger.error("All registration attempts failed")
    
    async def _heartbeat_loop(self):
        """Background loop to send periodic heartbeats."""
        logger.info(f"Starting heartbeat loop (interval: {self.config.heartbeat_interval}s)")
        
        while self._running:
            try:
                # Collect health metrics
                health_metrics = get_health_metrics()
                
                # Send heartbeat
                result = await self.api_client.send_heartbeat(
                    status=self._current_status,
                    current_active_runs=self._current_active_runs,
                    health_metrics=health_metrics,
                )
                
                if result:
                    logger.debug(f"Heartbeat sent: status={self._current_status}")
                else:
                    logger.warning("Heartbeat failed, will retry")
                
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
            
            # Wait for next heartbeat
            await asyncio.sleep(self.config.heartbeat_interval)
        
        logger.info("Heartbeat loop stopped")
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def handle_signal(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown...")
            self._running = False
        
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
    
    async def execute_test_run(
        self,
        test_run_id: str,
        test_suite_path: str | None = None,
        test_files: list[str] | None = None,
        test_filter: str | None = None,
        environment: dict[str, str] | None = None,
    ) -> ExecutionResult:
        """
        Execute a test run.
        
        Args:
            test_run_id: ID of the test run
            test_suite_path: Path to test suite
            test_files: Specific test files to run
            test_filter: Filter expression
            environment: Environment variables
            
        Returns:
            ExecutionResult with execution outcome
        """
        logger.info(f"Starting test execution: {test_run_id}")
        
        # Update status
        self._current_status = "busy"
        self._current_active_runs += 1
        
        try:
            # Check resources before running
            has_resources, resource_msg = check_available_resources()
            if not has_resources:
                logger.warning(f"Resource check failed: {resource_msg}")
                # Continue anyway, but log warning
            
            # Execute tests
            result = self.executor.execute(
                test_run_id=test_run_id,
                test_suite_path=test_suite_path,
                test_files=test_files,
                test_filter=test_filter,
                environment=environment,
            )
            
            logger.info(
                f"Test execution completed: {result.passed} passed, "
                f"{result.failed} failed, {result.skipped} skipped"
            )
            
            return result
            
        finally:
            # Update status back to idle
            self._current_active_runs -= 1
            if self._current_active_runs <= 0:
                self._current_active_runs = 0
                self._current_status = "idle"
    
    def can_accept_job(self) -> bool:
        """Check if the worker can accept a new job."""
        if not self._running:
            return False
        
        if self._current_active_runs >= self.config.max_concurrent_runs:
            return False
        
        has_resources, _ = check_available_resources()
        return has_resources


async def main():
    """Main entry point for running the worker agent."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Load config from environment
    config = WorkerConfig()
    
    # Create and start agent
    agent = WorkerAgent(config)
    
    try:
        await agent.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())


