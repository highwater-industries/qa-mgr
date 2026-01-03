"""Tests for the worker agent."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone

from worker_agent.config import WorkerConfig
from worker_agent.api_client import APIClient
from worker_agent.agent import WorkerAgent
from worker_agent.health import get_health_metrics, check_available_resources
from worker_agent.executor import TestRunner, ExecutionResult


# =============================================================================
# Config Tests
# =============================================================================

class TestWorkerConfig:
    """Tests for WorkerConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = WorkerConfig()
        
        assert config.api_base_url == "http://localhost:8001"
        assert config.worker_type == "celery"
        assert config.heartbeat_interval == 30
        assert config.max_concurrent_runs == 1
    
    def test_hostname_property(self):
        """Test hostname is populated."""
        config = WorkerConfig()
        assert config.hostname  # Should not be empty
    
    def test_os_property(self):
        """Test OS name is populated."""
        config = WorkerConfig()
        assert config.os_name in ("Windows", "Linux", "Darwin")
    
    def test_arch_property(self):
        """Test architecture is populated."""
        config = WorkerConfig()
        assert config.arch  # Should not be empty
    
    def test_tags_list_empty(self):
        """Test empty tags."""
        config = WorkerConfig(worker_tags="")
        assert config.tags_list == []
    
    def test_tags_list_parsing(self):
        """Test parsing comma-separated tags."""
        config = WorkerConfig(worker_tags="web, api, integration")
        assert config.tags_list == ["web", "api", "integration"]
    
    def test_python_version(self):
        """Test Python version is populated."""
        config = WorkerConfig()
        assert config.python_version.startswith("3.")


# =============================================================================
# API Client Tests
# =============================================================================

class TestAPIClient:
    """Tests for APIClient."""
    
    def test_client_init(self):
        """Test client initialization."""
        config = WorkerConfig()
        client = APIClient(config)
        
        assert client.base_url == "http://localhost:8001"
        assert client.worker_id is None
    
    def test_headers_without_auth(self):
        """Test headers without API key."""
        config = WorkerConfig(api_key="", workspace_id="")
        client = APIClient(config)
        
        headers = client._get_headers()
        assert "Content-Type" in headers
        assert "X-API-Key" not in headers
    
    def test_headers_with_auth(self):
        """Test headers with API key and org ID."""
        config = WorkerConfig(
            api_key="test-key",
            workspace_id="test-org",
        )
        client = APIClient(config)
        
        headers = client._get_headers()
        assert headers["X-API-Key"] == "test-key"
        assert headers["X-Workspace-ID"] == "test-org"
    
    @pytest.mark.asyncio
    async def test_register_success(self):
        """Test successful registration."""
        config = WorkerConfig(
            api_base_url="http://test-api",
            workspace_id="test-org",
        )
        client = APIClient(config)
        
        worker_id = str(uuid4())
        mock_response = {
            "worker_id": worker_id,
            "message": "Worker registered successfully",
            "heartbeat_interval": 30,
        }
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response_obj)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            
            result = await client.register()
            
            assert result["worker_id"] == worker_id
            assert client.worker_id is not None
            assert str(client.worker_id) == worker_id
    
    @pytest.mark.asyncio
    async def test_heartbeat_without_registration(self):
        """Test heartbeat fails without registration."""
        config = WorkerConfig()
        client = APIClient(config)
        
        result = await client.send_heartbeat(status="idle")
        assert result is None


# =============================================================================
# Health Metrics Tests
# =============================================================================

class TestHealthMetrics:
    """Tests for health metrics collection."""
    
    def test_get_health_metrics(self):
        """Test health metrics collection."""
        metrics = get_health_metrics()
        
        assert "timestamp" in metrics
        assert "cpu" in metrics
        assert "memory" in metrics
        assert "disk" in metrics
        assert "platform" in metrics
    
    def test_platform_info(self):
        """Test platform info in metrics."""
        metrics = get_health_metrics()
        
        assert "system" in metrics["platform"]
        assert "python_version" in metrics["platform"]
    
    def test_check_available_resources(self):
        """Test resource availability check."""
        has_resources, message = check_available_resources()
        
        # Should return a boolean and a message
        assert isinstance(has_resources, bool)
        assert isinstance(message, str)


# =============================================================================
# Test Executor Tests
# =============================================================================

class TestTestRunner:
    """Tests for TestRunner."""
    
    def test_executor_init(self):
        """Test executor initialization."""
        executor = TestRunner(
            test_runner="pytest",
            output_dir="./test_output",
        )
        
        assert executor.test_runner == "pytest"
        assert executor.output_dir.name == "test_output"
    
    def test_build_command_basic(self):
        """Test basic command building."""
        executor = TestRunner(test_runner="pytest")
        
        cmd = executor._build_command(
            test_suite_path=None,
            test_files=None,
            test_filter=None,
            extra_args=None,
            result_dir=executor.output_dir / "test-run",
        )
        
        assert cmd[0] == "pytest"
        assert "-v" in cmd
        assert any("--json-report" in arg for arg in cmd)
        assert any("--junitxml" in arg for arg in cmd)
    
    def test_build_command_with_filter(self):
        """Test command building with filter."""
        executor = TestRunner(test_runner="pytest")
        
        cmd = executor._build_command(
            test_suite_path=None,
            test_files=None,
            test_filter="test_login",
            extra_args=None,
            result_dir=executor.output_dir / "test-run",
        )
        
        assert "-k" in cmd
        filter_idx = cmd.index("-k")
        assert cmd[filter_idx + 1] == "test_login"
    
    def test_build_command_with_files(self):
        """Test command building with specific files."""
        executor = TestRunner(test_runner="pytest")
        
        cmd = executor._build_command(
            test_suite_path=None,
            test_files=["tests/test_a.py", "tests/test_b.py"],
            test_filter=None,
            extra_args=None,
            result_dir=executor.output_dir / "test-run",
        )
        
        assert "tests/test_a.py" in cmd
        assert "tests/test_b.py" in cmd
    
    def test_parse_stdout_summary(self):
        """Test parsing pytest summary from stdout."""
        executor = TestRunner()
        result = ExecutionResult(success=True, exit_code=0)
        
        stdout = "===== 10 passed, 2 failed, 1 skipped in 5.32s ====="
        result = executor._parse_stdout_summary(result, stdout)
        
        assert result.passed == 10
        assert result.failed == 2
        assert result.skipped == 1
        assert result.total_tests == 13


# =============================================================================
# Worker Agent Tests
# =============================================================================

class TestWorkerAgent:
    """Tests for WorkerAgent."""
    
    def test_agent_init(self):
        """Test agent initialization."""
        config = WorkerConfig()
        agent = WorkerAgent(config)
        
        assert agent.config == config
        assert agent.worker_id is None
        assert not agent.is_registered
        assert not agent.is_running
    
    def test_can_accept_job_not_running(self):
        """Test can_accept_job when not running."""
        agent = WorkerAgent()
        assert not agent.can_accept_job()
    
    @pytest.mark.asyncio
    async def test_stop_sends_offline_heartbeat(self):
        """Test that stopping sends an offline heartbeat."""
        config = WorkerConfig()
        agent = WorkerAgent(config)
        agent._running = True
        
        # Mock the API client
        agent.api_client.send_heartbeat = AsyncMock(return_value=None)
        
        await agent.stop()
        
        assert not agent._running
        agent.api_client.send_heartbeat.assert_called_once()
        call_kwargs = agent.api_client.send_heartbeat.call_args.kwargs
        assert call_kwargs["status"] == "offline"


# =============================================================================
# Test Result Tests
# =============================================================================

class TestExecutionResult:
    """Tests for ExecutionResult dataclass."""
    
    def test_result_to_dict(self):
        """Test converting result to dictionary."""
        result = ExecutionResult(
            success=True,
            exit_code=0,
            total_tests=10,
            passed=8,
            failed=1,
            skipped=1,
            duration_seconds=5.5,
        )
        
        data = result.to_dict()
        
        assert data["success"] is True
        assert data["total_tests"] == 10
        assert data["passed"] == 8
        assert data["failed"] == 1
        assert data["skipped"] == 1
        assert data["duration_seconds"] == 5.5
    
    def test_result_defaults(self):
        """Test result default values."""
        result = ExecutionResult(success=False, exit_code=1)
        
        assert result.total_tests == 0
        assert result.passed == 0
        assert result.failed == 0
        assert result.skipped == 0
        assert result.stdout == ""
        assert result.stderr == ""
        assert result.error_message is None



