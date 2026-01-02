"""Test executor for running tests and collecting results."""

import subprocess
import os
import json
import logging
import shutil
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of a test execution."""
    __test__ = False  # Prevent pytest collection
    
    success: bool
    exit_code: int
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    
    stdout: str = ""
    stderr: str = ""
    
    # JSON report data if available
    report_data: dict[str, Any] = field(default_factory=dict)
    
    # Error message if execution failed
    error_message: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API submission."""
        return {
            "success": self.success,
            "exit_code": self.exit_code,
            "total_tests": self.total_tests,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
        }


class TestRunner:
    """Execute tests and collect results."""
    __test__ = False  # Prevent pytest collection
    
    def __init__(
        self,
        test_runner: str = "pytest",
        output_dir: str = "./test_results",
        timeout: int = 28800,  # 8 hours default
    ):
        self.test_runner = test_runner
        self.output_dir = Path(output_dir)
        self.timeout = timeout
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def execute(
        self,
        test_run_id: str,
        test_suite_path: str | None = None,
        test_files: list[str] | None = None,
        test_filter: str | None = None,
        environment: dict[str, str] | None = None,
        extra_args: list[str] | None = None,
    ) -> ExecutionResult:
        """
        Execute tests and return results.
        
        Args:
            test_run_id: Unique ID for this test run
            test_suite_path: Path to test suite directory
            test_files: Specific test files to run
            test_filter: Test filter expression (e.g., pytest -k filter)
            environment: Additional environment variables
            extra_args: Additional command-line arguments
            
        Returns:
            ExecutionResult with execution outcome
        """
        start_time = datetime.now(timezone.utc)
        
        # Create result directory for this run
        result_dir = self.output_dir / test_run_id
        result_dir.mkdir(parents=True, exist_ok=True)
        
        # Build command
        cmd = self._build_command(
            test_suite_path=test_suite_path,
            test_files=test_files,
            test_filter=test_filter,
            extra_args=extra_args,
            result_dir=result_dir,
        )
        
        logger.info(f"Executing tests: {' '.join(cmd)}")
        
        # Prepare environment
        env = os.environ.copy()
        if environment:
            env.update(environment)
        
        try:
            # Run tests
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=env,
                cwd=test_suite_path,
            )
            
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            # Parse results
            result = self._parse_results(
                exit_code=process.returncode,
                stdout=process.stdout,
                stderr=process.stderr,
                result_dir=result_dir,
                duration=duration,
            )
            
            # Save stdout/stderr
            self._save_output(result_dir, process.stdout, process.stderr)
            
            return result
            
        except subprocess.TimeoutExpired:
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            logger.error(f"Test execution timed out after {self.timeout}s")
            
            return ExecutionResult(
                success=False,
                exit_code=-1,
                duration_seconds=duration,
                error_message=f"Test execution timed out after {self.timeout} seconds",
            )
            
        except Exception as e:
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            logger.error(f"Test execution failed: {e}")
            
            return ExecutionResult(
                success=False,
                exit_code=-1,
                duration_seconds=duration,
                error_message=str(e),
            )
    
    def _build_command(
        self,
        test_suite_path: str | None,
        test_files: list[str] | None,
        test_filter: str | None,
        extra_args: list[str] | None,
        result_dir: Path,
    ) -> list[str]:
        """Build the test command."""
        cmd = [self.test_runner]
        
        # Add pytest-specific options
        if self.test_runner in ("pytest", "py.test"):
            # JSON report for machine-readable results
            json_report = result_dir / "report.json"
            cmd.extend(["--json-report", f"--json-report-file={json_report}"])
            
            # JUnit XML for Jenkins compatibility
            junit_xml = result_dir / "junit.xml"
            cmd.extend([f"--junitxml={junit_xml}"])
            
            # Verbose output
            cmd.append("-v")
            
            # Filter expression
            if test_filter:
                cmd.extend(["-k", test_filter])
        
        # Add test files
        if test_files:
            cmd.extend(test_files)
        
        # Add extra arguments
        if extra_args:
            cmd.extend(extra_args)
        
        return cmd
    
    def _parse_results(
        self,
        exit_code: int,
        stdout: str,
        stderr: str,
        result_dir: Path,
        duration: float,
    ) -> ExecutionResult:
        """Parse test results from output and report files."""
        result = ExecutionResult(
            success=exit_code == 0,
            exit_code=exit_code,
            duration_seconds=duration,
            stdout=stdout,
            stderr=stderr,
        )
        
        # Try to parse JSON report (pytest-json-report)
        json_report = result_dir / "report.json"
        if json_report.exists():
            try:
                with open(json_report) as f:
                    report = json.load(f)
                
                result.report_data = report
                
                # Extract summary
                summary = report.get("summary", {})
                result.total_tests = summary.get("total", 0)
                result.passed = summary.get("passed", 0)
                result.failed = summary.get("failed", 0)
                result.skipped = summary.get("skipped", 0)
                result.errors = summary.get("error", 0)
                
                # Duration from report
                if "duration" in report:
                    result.duration_seconds = report["duration"]
                    
            except Exception as e:
                logger.warning(f"Failed to parse JSON report: {e}")
        
        # If no JSON report, try to parse from stdout
        if result.total_tests == 0:
            result = self._parse_stdout_summary(result, stdout)
        
        return result
    
    def _parse_stdout_summary(self, result: ExecutionResult, stdout: str) -> ExecutionResult:
        """Parse test summary from stdout (fallback)."""
        # Look for pytest summary line: "10 passed, 2 failed, 1 skipped"
        import re
        
        patterns = [
            (r"(\d+)\s+passed", "passed"),
            (r"(\d+)\s+failed", "failed"),
            (r"(\d+)\s+skipped", "skipped"),
            (r"(\d+)\s+error", "errors"),
        ]
        
        for pattern, attr in patterns:
            match = re.search(pattern, stdout, re.IGNORECASE)
            if match:
                setattr(result, attr, int(match.group(1)))
        
        result.total_tests = result.passed + result.failed + result.skipped + result.errors
        
        return result
    
    def _save_output(self, result_dir: Path, stdout: str, stderr: str):
        """Save stdout and stderr to files."""
        try:
            (result_dir / "stdout.txt").write_text(stdout)
            (result_dir / "stderr.txt").write_text(stderr)
        except Exception as e:
            logger.warning(f"Failed to save output files: {e}")
    
    def cleanup_old_results(self, max_age_days: int = 7):
        """Clean up old test result directories."""
        if not self.output_dir.exists():
            return
        
        cutoff = datetime.now(timezone.utc).timestamp() - (max_age_days * 86400)
        
        for path in self.output_dir.iterdir():
            if path.is_dir():
                try:
                    if path.stat().st_mtime < cutoff:
                        shutil.rmtree(path)
                        logger.info(f"Cleaned up old result directory: {path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up {path}: {e}")
