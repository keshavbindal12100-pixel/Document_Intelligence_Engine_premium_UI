from backend.app.api.audit import router as audit_router
from backend.app.api.auth import router as auth_router
from backend.app.api.dashboard import router as dashboard_router
from backend.app.api.documents import router as documents_router
from backend.app.api.extraction import router as extraction_router
from backend.app.api.integrations import router as integrations_router
from backend.app.api.templates import router as templates_router
from backend.app.api.workflows import router as workflows_router
from backend.app.api.workspaces import router as workspaces_router
from fastapi import APIRouter

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(workspaces_router)
api_router.include_router(documents_router)
api_router.include_router(extraction_router)
api_router.include_router(templates_router)
api_router.include_router(workflows_router)
api_router.include_router(integrations_router)
api_router.include_router(audit_router)
api_router.include_router(dashboard_router)

__all__ = ["api_router"]
