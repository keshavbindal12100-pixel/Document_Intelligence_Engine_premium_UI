import uuid

from backend.app.core.exceptions import (
    AuthenticationException,
    EntityAlreadyExistsException,
)
from backend.app.core.permissions import WorkspaceRole
from backend.app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.repositories.user_repo import UserRepository
from backend.app.repositories.workspace_repo import WorkspaceRepository
from backend.app.schemas.token import Token
from backend.app.schemas.user import UserCreate
from slugify import slugify
from sqlalchemy.ext.asyncio import AsyncSession


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
        self.workspace_repo = WorkspaceRepository(db)

    async def register(self, user_in: UserCreate) -> User:
        """Register a new user, create default personal workspace, and assign ADMIN role."""
        existing = await self.user_repo.get_by_email(user_in.email)
        if existing:
            raise EntityAlreadyExistsException("User", user_in.email)

        # Create user
        hashed_pwd = get_password_hash(user_in.password)
        new_user = User(
            email=user_in.email.lower().strip(),
            hashed_password=hashed_pwd,
            full_name=user_in.full_name,
            is_active=True,
            is_superuser=False,
        )
        user = await self.user_repo.create(new_user)

        # Create default workspace for the user
        ws_name = f"{user.full_name or user.email.split('@')[0]}'s Workspace"
        base_slug = slugify(ws_name)
        unique_slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

        default_workspace = Workspace(
            name=ws_name,
            slug=unique_slug,
            description="Default personal workspace",
            created_by_id=user.id,
        )
        workspace = await self.workspace_repo.create(default_workspace)

        # Associate user with workspace as ADMIN
        await self.workspace_repo.add_member(
            workspace_id=workspace.id,
            user_id=user.id,
            role=WorkspaceRole.ADMIN,
        )

        return user

    async def authenticate(self, email: str, password: str) -> User:
        """Authenticate user credentials."""
        user = await self.user_repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise AuthenticationException("Incorrect email or password.")
        if not user.is_active:
            raise AuthenticationException("User account is disabled.")
        return user

    def generate_token_pair(self, user: User) -> Token:
        """Generate JWT access and refresh token pair for authenticated user."""
        access_token = create_access_token(
            subject=str(user.id),
            extra_claims={"email": user.email, "is_superuser": user.is_superuser},
        )
        refresh_token = create_refresh_token(subject=str(user.id))
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )

    async def refresh_tokens(self, refresh_token_str: str) -> Token:
        """Validate refresh token and issue new token pair."""
        payload = decode_token(refresh_token_str)
        if not payload or payload.get("type") != "refresh":
            raise AuthenticationException("Invalid or expired refresh token.")

        user_id_str = payload.get("sub")
        if not user_id_str:
            raise AuthenticationException("Invalid token subject.")

        try:
            user_id = uuid.UUID(user_id_str)
        except ValueError:
            raise AuthenticationException("Invalid user ID format in token.") from None

        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise AuthenticationException("User not found or inactive.")

        return self.generate_token_pair(user)
