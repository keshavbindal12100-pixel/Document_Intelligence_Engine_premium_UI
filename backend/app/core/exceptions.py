from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Any | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


class EntityNotFoundException(AppException):
    def __init__(self, entity_name: str, entity_id: Any):
        super().__init__(
            message=f"{entity_name} with identifier '{entity_id}' was not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class EntityAlreadyExistsException(AppException):
    def __init__(self, entity_name: str, identifier: str):
        super().__init__(
            message=f"{entity_name} with '{identifier}' already exists.",
            status_code=status.HTTP_409_CONFLICT,
        )


class AuthenticationException(AppException):
    def __init__(self, message: str = "Invalid authentication credentials."):
        super().__init__(message=message, status_code=status.HTTP_401_UNAUTHORIZED)


class AuthorizationException(AppException):
    def __init__(self, message: str = "You do not have permission to perform this action."):
        super().__init__(message=message, status_code=status.HTTP_403_FORBIDDEN)


class WorkspaceAccessDeniedException(AuthorizationException):
    def __init__(self, workspace_id: Any):
        super().__init__(message=f"Access to workspace '{workspace_id}' is denied.")


class ValidationException(AppException):
    def __init__(self, message: str, details: Any | None = None):
        super().__init__(
            message=message,
            status_code=getattr(
                status, "HTTP_422_UNPROCESSABLE_CONTENT", status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            details=details,
        )


class FileStorageException(AppException):
    def __init__(self, message: str):
        super().__init__(message=message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers with the FastAPI application."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "type": exc.__class__.__name__,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )
