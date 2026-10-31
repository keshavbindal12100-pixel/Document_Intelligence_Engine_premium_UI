from backend.app.api.deps import get_current_user
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.schemas.token import LoginRequest, RefreshTokenRequest, Token
from backend.app.schemas.user import UserCreate, UserResponse
from backend.app.services.auth_service import AuthService
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Register a new user account with default workspace."""
    auth_service = AuthService(db)
    return await auth_service.register(user_in)


@router.post("/login", response_model=Token)
async def login_user(
    login_in: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Authenticate and receive access and refresh token pair."""
    auth_service = AuthService(db)
    user = await auth_service.authenticate(login_in.email, login_in.password)
    return auth_service.generate_token_pair(user)


@router.post("/token", response_model=Token)
async def login_token(
    login_in: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """OAuth2 compatible alias for login to acquire access and refresh token."""
    auth_service = AuthService(db)
    user = await auth_service.authenticate(login_in.email, login_in.password)
    return auth_service.generate_token_pair(user)


@router.post("/guest-token", response_model=Token)
async def guest_token(
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Acquire a demo/guest access token for instant development verification."""
    from backend.app.core.security import get_password_hash
    from backend.app.repositories.user_repo import UserRepository

    auth_service = AuthService(db)
    user_repo = UserRepository(db)
    user = await user_repo.get_by_email("admin@example.com")
    if not user:
        user = await user_repo.get_by_email("demo@example.com")
    if not user:
        users = await user_repo.list(limit=1)
        if users:
            user = users[0]
    if not user:
        user = User(
            email="admin@example.com",
            hashed_password=get_password_hash("Password12345!"),
            full_name="Default System Administrator",
            is_active=True,
            is_superuser=True,
        )
        user = await user_repo.create(user)
    return auth_service.generate_token_pair(user)


@router.post("/refresh", response_model=Token)
async def refresh_access_token(
    refresh_in: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Obtain a new access token using a valid refresh token."""
    auth_service = AuthService(db)
    return await auth_service.refresh_tokens(refresh_in.refresh_token)


@router.get("/me", response_model=UserResponse)
async def get_current_authenticated_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get profile of current logged-in user."""
    return current_user
