"""Pytest configuration and fixtures."""
import asyncio
import os
from typing import AsyncGenerator, Generator
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from main import app
from database.config import get_db
from database.models import BaseModel, User, Organization, UserOrganizationRole
from database.models.project import Project, TestSuite
from database.models.test_models import TestCase
import bcrypt


# Test database URL - use environment variable or default
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:testpass@localhost:5432/qa_mgr_test"
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.create_all)
    
    yield engine
    
    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    # Start a transaction
    async with test_engine.connect() as connection:
        async with connection.begin() as transaction:
            async_session = async_sessionmaker(
                bind=connection,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            
            async with async_session() as session:
                yield session
                # Rollback transaction after test
                await transaction.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with database session override."""
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture
async def test_organization(db_session: AsyncSession) -> Organization:
    """Create a test organization."""
    org = Organization(
        name="Test Organization",
        slug="test-org",
        description="Test organization for unit tests",
        type="application",
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


@pytest.fixture
async def test_user(db_session: AsyncSession, test_organization: Organization) -> User:
    """Create a test user."""
    hashed_password = bcrypt.hashpw(b"testpass123", bcrypt.gensalt()).decode('utf-8')
    
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=hashed_password,
        full_name="Test User",
        is_active=True,
        is_superuser=False,
        current_organization_id=test_organization.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # Create organization role
    role = UserOrganizationRole(
        user_id=user.id,
        organization_id=test_organization.id,
        role="admin",
    )
    db_session.add(role)
    await db_session.commit()
    
    return user


@pytest.fixture
async def admin_user(db_session: AsyncSession, test_organization: Organization) -> User:
    """Create a superuser admin."""
    hashed_password = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode('utf-8')
    
    user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=hashed_password,
        full_name="Admin User",
        is_active=True,
        is_superuser=True,
        current_organization_id=test_organization.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # Create organization role
    role = UserOrganizationRole(
        user_id=user.id,
        organization_id=test_organization.id,
        role="admin",
    )
    db_session.add(role)
    await db_session.commit()
    
    return user


@pytest.fixture
async def auth_headers(client: AsyncClient, test_user: User) -> dict[str, str]:
    """Get authentication headers for test user."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "testpass123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin_headers(client: AsyncClient, admin_user: User) -> dict[str, str]:
    """Get authentication headers for admin user."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def test_project(db_session: AsyncSession, test_organization: Organization) -> Project:
    """Create a test project."""
    project = Project(
        organization_id=test_organization.id,
        name="Test Project",
        description="Test project for unit tests",
        tags=["test"],
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest.fixture
async def test_suite(db_session: AsyncSession, test_organization: Organization, test_project: Project) -> TestSuite:
    """Create a test suite."""
    suite = TestSuite(
        organization_id=test_organization.id,
        project_id=test_project.id,
        name="Test Suite",
        description="Test suite for unit tests",
        path="tests/unit",
        tags=["unit"],
        category="unit",
    )
    db_session.add(suite)
    await db_session.commit()
    await db_session.refresh(suite)
    return suite


@pytest.fixture
async def test_case(db_session: AsyncSession, test_organization: Organization, test_suite: TestSuite) -> TestCase:
    """Create a test case."""
    test_case = TestCase(
        organization_id=test_organization.id,
        suite_id=test_suite.id,
        name="Test Case 1",
        test_id="tests.unit.test_example::test_one",
        file_path="tests/unit/test_example.py",
        line_number=10,
        description="Sample test case",
        tags=["sample"],
    )
    db_session.add(test_case)
    await db_session.commit()
    await db_session.refresh(test_case)
    return test_case


@pytest.fixture
async def test_user_token(auth_headers: dict[str, str]) -> str:
    """Extract token from auth headers."""
    return auth_headers["Authorization"].replace("Bearer ", "")


@pytest.fixture
def test_org_id(test_organization: Organization):
    """Get test organization ID."""
    return test_organization.id

