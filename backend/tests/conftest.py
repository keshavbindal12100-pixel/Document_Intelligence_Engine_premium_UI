import os
import shutil
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from backend.app.core.config import settings
from backend.app.core.permissions import WorkspaceRole
from backend.app.core.security import create_access_token, get_password_hash
from backend.app.db.base import Base
from backend.app.db.database import get_db
from backend.app.main import app
from backend.app.models.user import User, UserWorkspace
from backend.app.models.workspace import Workspace
from backend.app.services.storage_service import storage_service
from backend.app.workers.celery_app import celery_app
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Disable eager auto-execution so upload endpoints return instantly in unit tests
celery_app.conf.task_always_eager = False
celery_app.conf.task_eager_propagates = False

# Use in-memory SQLite with StaticPool so all connections share the same memory DB
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Fixture providing clean database session with freshly initialized schema."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
def mock_celery_task_delay():
    """Autouse fixture preventing real Redis connections for background task delay() in tests."""
    import importlib
    from unittest.mock import MagicMock, patch

    celery_app_module = importlib.import_module("backend.app.workers.celery_app")
    from backend.app.workers.tasks import process_document_task

    with (
        patch.object(process_document_task, "delay") as mock_delay,
        patch.object(process_document_task, "apply_async") as mock_apply,
        patch.object(celery_app_module, "has_active_worker", return_value=True),
    ):
        mock_delay.return_value = MagicMock(id="mock-celery-task-id")
        mock_apply.return_value = MagicMock(id="mock-celery-task-id")
        yield mock_delay


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Fixture providing AsyncClient with DB dependency overridden."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def test_user(db_session: AsyncSession) -> User:
    """Fixture that creates and returns a standard active user."""
    user = User(
        id=uuid.uuid4(),
        email="testuser@example.com",
        hashed_password=get_password_hash("TestPassword123!"),
        full_name="Test User",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def test_workspace(db_session: AsyncSession, test_user: User) -> Workspace:
    """Fixture that creates and returns a workspace with test_user as ADMIN."""
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Test Innovation Workspace",
        slug=f"test-workspace-{uuid.uuid4().hex[:6]}",
        description="Workspace created for automated testing",
        created_by_id=test_user.id,
    )
    db_session.add(workspace)
    await db_session.flush()

    membership = UserWorkspace(
        user_id=test_user.id,
        workspace_id=workspace.id,
        role=WorkspaceRole.ADMIN,
    )
    db_session.add(membership)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


@pytest.fixture
def auth_headers(test_user: User, test_workspace: Workspace) -> dict[str, str]:
    """Headers with Bearer JWT token and active Workspace ID."""
    token = create_access_token(subject=str(test_user.id))
    return {
        "Authorization": f"Bearer {token}",
        "X-Workspace-Id": str(test_workspace.id),
    }


@pytest.fixture(autouse=True)
def clean_test_storage(tmp_path):
    """Isolate both storage settings and the imported singleton for each test."""
    test_storage = str(tmp_path / "storage_data")
    original_setting = settings.STORAGE_LOCAL_DIR
    original_service_dir = storage_service.base_dir
    settings.STORAGE_LOCAL_DIR = test_storage
    storage_service.base_dir = test_storage
    os.makedirs(test_storage, exist_ok=True)
    try:
        yield
    finally:
        shutil.rmtree(test_storage, ignore_errors=True)
        settings.STORAGE_LOCAL_DIR = original_setting
        storage_service.base_dir = original_service_dir
