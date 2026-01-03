"""
Server management script - start, stop, restart the FastAPI application.

Usage:
    python scripts/server.py start   - Start the server
    python scripts/server.py stop    - Stop the server
    python scripts/server.py restart - Restart the server
    python scripts/server.py status  - Check if server is running
"""
import sys
import subprocess
import signal
import os
import time
from pathlib import Path

# Configuration
HOST = "127.0.0.1"
PORT = 8008
RELOAD = True  # Auto-reload on code changes
PID_FILE = Path(__file__).parent.parent / ".server.pid"

def get_pid() -> int | None:
    """Get the stored PID if it exists."""
    if PID_FILE.exists():
        try:
            return int(PID_FILE.read_text().strip())
        except (ValueError, OSError):
            return None
    return None

def save_pid(pid: int):
    """Save the process PID."""
    PID_FILE.write_text(str(pid))

def clear_pid():
    """Remove the PID file."""
    if PID_FILE.exists():
        PID_FILE.unlink()

def is_running() -> bool:
    """Check if the server is running."""
    pid = get_pid()
    if not pid:
        return False
    
    try:
        # Check if process exists (works on Windows and Unix)
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        clear_pid()
        return False

def start_server():
    """Start the FastAPI server."""
    if is_running():
        print(f"❌ Server is already running (PID: {get_pid()})")
        print(f"   Access at: http://{HOST}:{PORT}")
        print(f"   API docs: http://{HOST}:{PORT}/docs")
        return
    
    print("🚀 Starting QA Manager server...")
    
    # Build uvicorn command
    cmd = [
        sys.executable, "-m", "uvicorn",
        "main:app",
        "--host", HOST,
        "--port", str(PORT),
    ]
    
    if RELOAD:
        cmd.append("--reload")
    
    # Start the process
    try:
        # On Windows, use CREATE_NEW_PROCESS_GROUP to allow proper termination
        if sys.platform == "win32":
            process = subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            process = subprocess.Popen(cmd)
        
        save_pid(process.pid)
        
        # Give it a moment to start
        time.sleep(2)
        
        if is_running():
            print(f"✅ Server started successfully (PID: {process.pid})")
            print(f"   Access at: http://{HOST}:{PORT}")
            print(f"   API docs: http://{HOST}:{PORT}/docs")
            print(f"\n💡 Use 'python scripts/server.py stop' to stop the server")
        else:
            print("❌ Server failed to start")
            clear_pid()
            
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        clear_pid()

def stop_server():
    """Stop the FastAPI server."""
    if not is_running():
        print("ℹ️  Server is not running")
        clear_pid()
        return
    
    pid = get_pid()
    print(f"🛑 Stopping server (PID: {pid})...")
    
    try:
        if sys.platform == "win32":
            # On Windows, use taskkill for clean shutdown
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], 
                          capture_output=True)
        else:
            # On Unix, send SIGTERM
            os.kill(pid, signal.SIGTERM)
        
        # Wait for process to stop
        for _ in range(10):
            if not is_running():
                break
            time.sleep(0.5)
        
        clear_pid()
        print("✅ Server stopped successfully")
        
    except Exception as e:
        print(f"❌ Error stopping server: {e}")
        print(f"   You may need to manually kill PID {pid}")

def status_server():
    """Check server status."""
    if is_running():
        print(f"✅ Server is running (PID: {get_pid()})")
        print(f"   Access at: http://{HOST}:{PORT}")
        print(f"   API docs: http://{HOST}:{PORT}/docs")
    else:
        print("❌ Server is not running")
        clear_pid()

def restart_server():
    """Restart the server."""
    print("🔄 Restarting server...")
    stop_server()
    time.sleep(1)
    start_server()

def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    commands = {
        "start": start_server,
        "stop": stop_server,
        "restart": restart_server,
        "status": status_server,
    }
    
    if command not in commands:
        print(f"❌ Unknown command: {command}")
        print(__doc__)
        sys.exit(1)
    
    commands[command]()

if __name__ == "__main__":
    main()


