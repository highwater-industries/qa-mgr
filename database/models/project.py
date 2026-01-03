"""
Project and TestSuite models.

Project represents a repository/codebase being tested.
TestSuite is a logical grouping of tests (file, module, feature).
"""

from typing import Optional
from uuid import UUID
from datetime import datetime

from sqlmodel import Field, SQLModel, Relationship, Column, Index
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, TEXT

from .base import TenantBaseModel


# =============================================================================
# Database Models
# =============================================================================

class Project(TenantBaseModel, table=True):
    """
    Project table - represents a repository/codebase being tested.
    """
    
    __tablename__ = "projects"
    
    # Basic info
    name: str = Field(max_length=255)
    description: str | None = Field(
        default=None,
        sa_column=Column(TEXT, nullable=True),
    )
    
    # Tags for organization
    tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(TEXT), nullable=False, server_default="{}"),
    )
    
    # Repository
    repository_url: str | None = Field(default=None, max_length=500)
    repository_type: str | None = Field(default="git", max_length=50)
    default_branch: str = Field(default="main", max_length=100)
    
    # Configuration (JSONB for flexibility)
    config: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    
    # Relationships
    test_suites: list["TestSuite"] = Relationship(back_populates="project")
    
    __table_args__ = (
        Index("idx_project_organization", "workspace_id"),
        Index("idx_project_organization_name", "workspace_id", "name"),
    )


class TestSuite(TenantBaseModel, table=True):
    """
    TestSuite table - logical grouping of test cases.
    
    Supports hierarchy (parent_id) for nested suites.
    Examples:
    - tests/unit/api (path)
    - tests/integration/database (path)
    """
    __test__ = False  # Prevent pytest from collecting this as a test class
    
    __tablename__ = "test_suites"
    
    # Hierarchy
    project_id: UUID = Field(foreign_key="projects.id", index=True)
    parent_id: UUID | None = Field(
        default=None,
        foreign_key="test_suites.id",
        nullable=True,
    )
    
    # Identity
    name: str = Field(max_length=500)
    description: str | None = Field(
        default=None,
        sa_column=Column(TEXT, nullable=True),
    )
    
    # Path (for file-based suites)
    path: str = Field(max_length=1000)  # e.g., "tests/unit/api"
    
    # Classification
    tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(TEXT), nullable=False, server_default="{}"),
    )
    category: str | None = Field(default=None, max_length=100)  # 'unit', 'integration', 'e2e'
    
    # Metadata
    meta_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    
    # Relationships
    project: Project = Relationship(back_populates="test_suites")
    parent: Optional["TestSuite"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={
            "remote_side": "TestSuite.id",
            "foreign_keys": "[TestSuite.parent_id]",
        },
    )
    children: list["TestSuite"] = Relationship(back_populates="parent")
    test_cases: list["TestCase"] = Relationship(back_populates="suite")  # type: ignore
    
    __table_args__ = (
        Index("idx_suite_organization_project", "workspace_id", "project_id"),
        Index("idx_suite_parent", "parent_id"),
        Index("idx_suite_organization_path", "workspace_id", "path"),
    )


# =============================================================================
# API Schemas - Project
# =============================================================================

class ProjectBase(SQLModel):
    """Base schema for Project."""
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class ProjectCreate(ProjectBase):
    """Request schema for creating a project."""
    repository_url: str | None = None
    repository_type: str = "git"
    default_branch: str = "main"
    config: dict = {}


class ProjectUpdate(SQLModel):
    """Request schema for updating a project."""
    name: str | None = None
    description: str | None = None
    repository_url: str | None = None
    default_branch: str | None = None
    config: dict | None = None


class ProjectPublic(ProjectBase):
    """Public response schema for Project."""
    id: UUID
    workspace_id: UUID
    repository_url: str | None
    repository_type: str | None
    default_branch: str
    created_at: datetime
    
    # Statistics (computed)
    suite_count: int = 0
    test_count: int = 0
    last_run_at: datetime | None = None


class ProjectDetail(ProjectPublic):
    """Detailed response schema for Project."""
    config: dict
    updated_at: datetime


# =============================================================================
# API Schemas - TestSuite
# =============================================================================

class TestSuiteBase(SQLModel):
    """Base schema for TestSuite."""
    name: str = Field(min_length=1, max_length=500)
    description: str | None = None
    path: str = Field(min_length=1, max_length=1000)


class TestSuiteCreate(TestSuiteBase):
    """Request schema for creating a test suite."""
    project_id: UUID
    parent_id: UUID | None = None
    tags: list[str] = []
    category: str | None = None
    meta_data: dict = {}


class TestSuiteUpdate(SQLModel):
    """Request schema for updating a test suite."""
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    category: str | None = None
    meta_data: dict | None = None


class TestSuitePublic(TestSuiteBase):
    """Public response schema for TestSuite."""
    id: UUID
    workspace_id: UUID
    project_id: UUID
    parent_id: UUID | None
    tags: list[str]
    category: str | None
    created_at: datetime
    
    # Statistics (computed)
    test_count: int = 0
    child_count: int = 0


class TestSuiteDetail(TestSuitePublic):
    """Detailed response schema for TestSuite."""
    meta_data: dict
    updated_at: datetime
    
    # Nested project info
    class ProjectInfo(SQLModel):
        id: UUID
        name: str
    
    project: ProjectInfo | None = None


class TestSuiteTree(TestSuitePublic):
    """Tree response schema for TestSuite (includes children)."""
    children: list["TestSuiteTree"] = []


# =============================================================================
# Example Usage
# =============================================================================

"""
# Creating a project
project = Project(
    organization_id=current_workspace_id,
    name="Web Application",
    repository_url="https://github.com/org/web-app.git",
    default_branch="main",
)

# Creating a test suite
suite = TestSuite(
    organization_id=current_workspace_id,
    project_id=project.id,
    name="API Tests",
    path="tests/api",
    category="integration",
    tags=["api", "integration"],
)

# API endpoint
@router.post("/projects", response_model=ProjectPublic)
async def create_project(
    data: ProjectCreate,
    session: Session = Depends(get_session),
    current_workspace_id: UUID = Depends(get_current_workspace),
):
    project = Project(**data.model_dump(), organization_id=current_workspace_id)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project
"""



