"""Minimal test to isolate the login schema issue."""
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class LoginCredentials(BaseModel):
    """Login with username."""
    username: str
    password: str

@app.post("/test-login")
async def test_login(credentials: LoginCredentials):
    """Test login endpoint."""
    return {"username": credentials.username, "received": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8009)
