"""Health metrics collection for worker agent."""

import platform
import os
import logging
from typing import Any

logger = logging.getLogger(__name__)


def get_health_metrics() -> dict[str, Any]:
    """
    Collect health metrics for the worker.
    
    Returns:
        dict with CPU, memory, disk metrics
    """
    metrics: dict[str, Any] = {
        "timestamp": None,
        "cpu": {},
        "memory": {},
        "disk": {},
    }
    
    from datetime import datetime, timezone
    metrics["timestamp"] = datetime.now(timezone.utc).isoformat()
    
    try:
        import psutil
        
        # CPU metrics
        metrics["cpu"] = {
            "percent": psutil.cpu_percent(interval=0.1),
            "count": psutil.cpu_count(),
            "count_logical": psutil.cpu_count(logical=True),
        }
        
        # Memory metrics
        mem = psutil.virtual_memory()
        metrics["memory"] = {
            "total_gb": round(mem.total / (1024**3), 2),
            "available_gb": round(mem.available / (1024**3), 2),
            "percent_used": mem.percent,
        }
        
        # Disk metrics
        disk = psutil.disk_usage("/")
        metrics["disk"] = {
            "total_gb": round(disk.total / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "percent_used": disk.percent,
        }
        
    except ImportError:
        logger.debug("psutil not available, health metrics will be limited")
        metrics["cpu"] = {"count": os.cpu_count()}
        
    except Exception as e:
        logger.warning(f"Error collecting health metrics: {e}")
    
    # Add platform info
    metrics["platform"] = {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
    }
    
    return metrics


def get_system_load() -> float:
    """
    Get current system load as a percentage.
    
    Returns:
        System load percentage (0-100), or -1 if unavailable
    """
    try:
        import psutil
        return psutil.cpu_percent(interval=0.1)
    except ImportError:
        return -1
    except Exception:
        return -1


def check_available_resources(
    min_memory_gb: float = 1.0,
    min_disk_gb: float = 5.0,
    max_cpu_percent: float = 90.0,
) -> tuple[bool, str]:
    """
    Check if the worker has sufficient resources to accept a new job.
    
    Args:
        min_memory_gb: Minimum available memory in GB
        min_disk_gb: Minimum free disk space in GB
        max_cpu_percent: Maximum CPU usage percentage
        
    Returns:
        Tuple of (has_resources: bool, message: str)
    """
    try:
        import psutil
        
        # Check memory
        mem = psutil.virtual_memory()
        available_mem_gb = mem.available / (1024**3)
        if available_mem_gb < min_memory_gb:
            return False, f"Insufficient memory: {available_mem_gb:.1f}GB < {min_memory_gb}GB"
        
        # Check disk
        disk = psutil.disk_usage("/")
        free_disk_gb = disk.free / (1024**3)
        if free_disk_gb < min_disk_gb:
            return False, f"Insufficient disk space: {free_disk_gb:.1f}GB < {min_disk_gb}GB"
        
        # Check CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)
        if cpu_percent > max_cpu_percent:
            return False, f"CPU overloaded: {cpu_percent}% > {max_cpu_percent}%"
        
        return True, "Resources OK"
        
    except ImportError:
        # psutil not available, assume resources are OK
        return True, "psutil not available, assuming resources OK"
    except Exception as e:
        return False, f"Error checking resources: {e}"


