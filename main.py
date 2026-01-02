"""
FastAPI application entry point.
Simplified for MVP - add middleware and routes as needed.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from api.routes import auth, organizations, users
from api.routes import projects
from api.routes import test_suites, test_cases
# Models imported in routes as needed - not globally here

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # Startup
    logger.info("QA Manager API starting...")
    yield
    # Shutdown
    logger.info("QA Manager API shutting down...")

# Create FastAPI app
app = FastAPI(
    title="QA Manager API",
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
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(organizations.router, prefix="/api/v1/organizations", tags=["organizations"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])

# Project routes - both simplified and organization-scoped
app.include_router(
    projects.simple_router,
    prefix="/api/v1/projects",
    tags=["projects"],
)
app.include_router(
    projects.router,
    prefix="/api/v1/organizations/{organization_id}/projects",
    tags=["projects-admin"],
)

# Test suite and test case routes
app.include_router(test_suites.router, prefix="/api/v1")
app.include_router(test_cases.router, prefix="/api/v1")

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "QA Manager API", "version": "1.0.0"}

