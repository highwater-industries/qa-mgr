#!/usr/bin/env python
"""
CLI entry point for running the QA Manager worker agent.

Usage:
    # Run the worker agent (registers with API, sends heartbeats)
    python -m worker_agent
    
    # Run with custom settings
    QA_WORKER_API_BASE_URL=http://qa-manager:8001 python -m worker_agent
    
    # Run Celery worker (listens for tasks)
    celery -A worker_agent.celery_tasks worker --loglevel=info

Environment Variables:
    QA_WORKER_API_BASE_URL      Base URL of QA Manager API (default: http://localhost:8001)
    QA_WORKER_API_KEY           API key for authentication
    QA_WORKER_ORGANIZATION_ID   Organization ID
    QA_WORKER_WORKER_NAME       Worker name (default: hostname)
    QA_WORKER_WORKER_TYPE       Worker type: celery, jenkins, custom (default: celery)
    QA_WORKER_WORKER_TAGS       Comma-separated tags for job targeting
    QA_WORKER_MAX_CONCURRENT_RUNS  Max concurrent runs (default: 1)
    QA_WORKER_HEARTBEAT_INTERVAL   Heartbeat interval in seconds (default: 30)
    QA_WORKER_CELERY_BROKER_URL    RabbitMQ broker URL
    QA_WORKER_TEST_RUNNER_COMMAND  Test runner command (default: pytest)
    QA_WORKER_TEST_OUTPUT_DIR      Directory for test results (default: ./test_results)
"""

import asyncio
import logging
import sys
import argparse

from .agent import WorkerAgent
from .config import WorkerConfig


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )
    
    # Reduce noise from httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="QA Manager Worker Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (debug) logging",
    )
    
    parser.add_argument(
        "--api-url",
        help="QA Manager API base URL",
    )
    
    parser.add_argument(
        "--api-key",
        help="API key for authentication",
    )
    
    parser.add_argument(
        "--organization-id",
        help="Organization ID",
    )
    
    parser.add_argument(
        "--name",
        help="Worker name (defaults to hostname)",
    )
    
    parser.add_argument(
        "--tags",
        help="Comma-separated worker tags",
    )
    
    parser.add_argument(
        "--max-concurrent",
        type=int,
        help="Maximum concurrent test runs",
    )
    
    parser.add_argument(
        "--test-runner",
        help="Test runner command (default: pytest)",
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    setup_logging(verbose=args.verbose)
    logger = logging.getLogger(__name__)
    
    # Build config from environment (pydantic-settings handles this)
    config = WorkerConfig()
    
    # Override with CLI arguments if provided
    if args.api_url:
        config.api_base_url = args.api_url
    if args.api_key:
        config.api_key = args.api_key
    if args.organization_id:
        config.organization_id = args.organization_id
    if args.name:
        config.worker_name = args.name
    if args.tags:
        config.worker_tags = args.tags
    if args.max_concurrent:
        config.max_concurrent_runs = args.max_concurrent
    if args.test_runner:
        config.test_runner_command = args.test_runner
    
    logger.info(f"Starting QA Manager Worker Agent")
    logger.info(f"  Name: {config.worker_name}")
    logger.info(f"  API URL: {config.api_base_url}")
    logger.info(f"  Worker Type: {config.worker_type}")
    logger.info(f"  Tags: {config.tags_list}")
    logger.info(f"  Max Concurrent Runs: {config.max_concurrent_runs}")
    
    # Check required settings
    if not config.organization_id:
        logger.error("Organization ID is required. Set QA_WORKER_ORGANIZATION_ID environment variable.")
        sys.exit(1)
    
    # Create and run agent
    agent = WorkerAgent(config)
    
    try:
        asyncio.run(agent.start())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Worker agent failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
