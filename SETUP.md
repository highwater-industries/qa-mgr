# QA Manager - Setup Instructions

## Quick Setup

Run the automated setup script:

```powershell
cd c:\vscode\qa-mgr
python scripts/setup.py
```

This will:
1. Create PostgreSQL database
2. Install Python dependencies
3. Initialize Alembic
4. Create database schema
5. Create admin user

## Manual Setup (if automated fails)

### 1. Create Database

```powershell
psql -U postgres
```

```sql
CREATE DATABASE qa_mgr;
CREATE USER qa_mgr_user WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE qa_mgr TO qa_mgr_user;
\q
```

### 2. Install Dependencies

```powershell
pip install -e .
```

### 3. Initialize Database

```powershell
# Initialize Alembic (first time only)
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Initial schema"

# Apply migration
alembic upgrade head
```

### 4. Create Admin User

```powershell
python scripts/create_admin.py
```

## Start the Server

### Option 1: Use the server script (recommended)

```powershell
# Start the server
python scripts/server.py start

# Stop the server
python scripts/server.py stop

# Restart the server
python scripts/server.py restart

# Check server status
python scripts/server.py status
```

### Option 2: Quick batch files (Windows)

```powershell
# Start
.\start.bat

# Stop
.\stop.bat
```

### Option 3: Manual uvicorn

```powershell
uvicorn main:app --reload --port 8000
```

## Test the API

1. Open http://localhost:8000/docs
2. Login at POST /api/v1/auth/login with admin/admin123
3. Click "Authorize" and paste your token
4. Try the tenant endpoints!

## Login Credentials

- **Username**: admin
- **Password**: admin123
- **Email**: admin@qa-mgr.local
