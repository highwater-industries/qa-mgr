"""Setup script for QA Manager - Run this first!"""
import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description, check=True):
    """Run a command and print status."""
    print(f"\n{'='*60}")
    print(f"➤ {description}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, shell=True, capture_output=False)
    if check and result.returncode != 0:
        print(f"❌ Failed: {description}")
        sys.exit(1)
    print(f"✅ Success: {description}")

def main():
    print("""
    ╔════════════════════════════════════════════════════════╗
    ║           QA Manager - First Time Setup               ║
    ╚════════════════════════════════════════════════════════╝
    """)
    
    # 0. Create virtual environment with uv
    if not Path(".venv").exists():
        print("\n0️⃣  Creating virtual environment with uv...")
        result = subprocess.run("uv venv --python 3.12.10", shell=True)
        if result.returncode != 0:
            print("❌ Failed to create venv with uv.")
            print("   Make sure uv is installed: pip install uv")
            sys.exit(1)
        print("✅ Virtual environment created")
    else:
        print("\n0️⃣  Virtual environment exists ✓")
    
    # 1. Create database
    print("\n1️⃣  Creating PostgreSQL database...")
    db_commands = [
        'psql -U postgres -c "CREATE DATABASE qa_mgr;"',
        'psql -U postgres -c "CREATE USER qa_mgr_user WITH PASSWORD \'password\';"',
        'psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE qa_mgr TO qa_mgr_user;"',
    ]
    
    for cmd in db_commands:
        try:
            subprocess.run(cmd, shell=True, check=False, capture_output=True)
        except:
            pass
    print("   Database setup attempted (ignore errors if already exists)")
    
    # 2. Install dependencies with uv
    run_command(
        "uv pip install -e .",
        "2️⃣  Installing Python dependencies with uv"
    )
    
    # 3. Initialize Alembic
    if not os.path.exists("alembic"):
        run_command(
            "alembic init alembic",
            "3️⃣  Initializing Alembic"
        )
    else:
        print("\n3️⃣  Alembic already initialized ✓")
    
    # 4. Create migration
    run_command(
        'alembic revision --autogenerate -m "Initial schema"',
        "4️⃣  Creating database migration"
    )
    
    # 5. Run migration
    run_command(
        "alembic upgrade head",
        "5️⃣  Applying database migration"
    )
    
    # 6. Create superuser
    run_command(
        "python scripts/create_admin.py",
        "6️⃣  Creating admin user"
    )
    
    print("""
    
    ╔════════════════════════════════════════════════════════╗
    ║                Setup Complete! 🎉                     ║
    ╚════════════════════════════════════════════════════════╝
    
    Next steps:
    
    1. Start the API server:
       uvicorn main:app --reload --port 8000
    
    2. Open API docs:
       http://localhost:8000/docs
    
    3. Login credentials:
       Username: admin
       Password: admin123
    
    4. Test the tenant endpoint!
    """)

if __name__ == "__main__":
    main()
