"""
FastAPI application entry point.
Simplified for MVP - add middleware and routes as needed.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from api.routes import auth, workspaces, users
from api.routes import projects
from api.routes import test_suites, test_cases, test_runs, test_catalog
from api.routes import webhooks, workers, jobs, schedules, notifications
# Models imported in routes as needed - not globally here

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # Startup
    logger.info("qai starting...")
    yield
    # Shutdown
    logger.info("qai shutting down...")

# Create FastAPI app
app = FastAPI(
    title="qai",
    description="an intelligent qa platform for the ai supercycle",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes - Start with auth and organizations, add more as implemented
app.include_router(auth.router, prefix="/qai/api/v1/auth", tags=["auth"])
app.include_router(workspaces.router, prefix="/qai/api/v1/workspaces", tags=["workspaces"])
app.include_router(users.router, prefix="/qai/api/v1/users", tags=["users"])

# Project routes - uses current user's organization context
app.include_router(
    projects.simple_router,
    prefix="/qai/api/v1/projects",
    tags=["projects"],
)

# Test suite and test case routes
app.include_router(test_suites.router, prefix="/qai/api/v1")
app.include_router(test_cases.router, prefix="/qai/api/v1")
app.include_router(test_runs.router, prefix="/qai/api/v1")
app.include_router(test_catalog.router, prefix="/qai/api/v1")

# Webhook routes (public endpoints with secret/token auth)
app.include_router(webhooks.router, prefix="/qai/api/v1")

# Worker routes
app.include_router(workers.router, prefix="/qai/api/v1")

# Job management routes
app.include_router(jobs.router, prefix="/qai/api/v1")

# Schedule routes
app.include_router(schedules.router, prefix="/qai/api/v1")

# Notification routes
app.include_router(notifications.router, prefix="/qai/api/v1")

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "qai", "version": "1.0.0"}



