import copy
import uuid
from typing import Any

from backend.app.core.exceptions import EntityNotFoundException, ValidationException
from backend.app.models.integration import Integration
from backend.app.repositories.integration_repo import IntegrationRepository
from backend.app.schemas.integration import (
    IntegrationCreate,
    IntegrationResponse,
    IntegrationUpdate,
)
from backend.app.services.workflow_engine import workflow_engine
from sqlalchemy.ext.asyncio import AsyncSession

SECRET_KEYS = {
    "api_key",
    "token",
    "password",
    "secret",
    "client_secret",
    "auth_token",
    "authorization",
    "private_key",
    "key",
}


def mask_sensitive_config(config: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact secrets in integration config so credentials are NEVER leaked to frontend."""
    if not isinstance(config, dict):
        return config

    masked = copy.deepcopy(config)

    def _mask_dict(d: dict[str, Any]) -> None:
        for k, v in d.items():
            if isinstance(v, dict):
                _mask_dict(v)
            elif any(s in k.lower() for s in SECRET_KEYS) and isinstance(v, str) and v:
                d[k] = "********"

    _mask_dict(masked)
    return masked


class IntegrationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.integration_repo = IntegrationRepository(db)

    def to_safe_response(self, integration: Integration) -> IntegrationResponse:
        """Convert Integration model to sanitized schema with redacted secrets."""
        safe_config = mask_sensitive_config(integration.config or {})
        return IntegrationResponse(
            id=integration.id,
            workspace_id=integration.workspace_id,
            name=integration.name,
            type=integration.type,
            config=safe_config,
            is_active=integration.is_active,
            created_at=integration.created_at,
            updated_at=integration.updated_at,
        )

    async def create_integration(
        self, workspace_id: uuid.UUID, integration_in: IntegrationCreate
    ) -> IntegrationResponse:
        """Create a new external integration."""
        integration = Integration(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            name=integration_in.name,
            type=integration_in.type,
            config=integration_in.config,
            is_active=integration_in.is_active,
        )
        created = await self.integration_repo.create(integration)
        return self.to_safe_response(created)

    async def get_integration(
        self, integration_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> IntegrationResponse:
        """Fetch sanitized integration by ID in workspace."""
        integration = await self.integration_repo.get_by_id_and_workspace(
            integration_id, workspace_id
        )
        if not integration:
            raise EntityNotFoundException("Integration", integration_id)
        return self.to_safe_response(integration)

    async def list_integrations(
        self, workspace_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> list[IntegrationResponse]:
        """List sanitized integrations for a workspace."""
        items = await self.integration_repo.list_by_workspace(workspace_id, skip=skip, limit=limit)
        return [self.to_safe_response(item) for item in items]

    async def update_integration(
        self,
        integration_id: uuid.UUID,
        workspace_id: uuid.UUID,
        update_in: IntegrationUpdate,
    ) -> IntegrationResponse:
        """Update integration configuration while preserving unmasked secrets if sent as masked."""
        integration = await self.integration_repo.get_by_id_and_workspace(
            integration_id, workspace_id
        )
        if not integration:
            raise EntityNotFoundException("Integration", integration_id)

        if update_in.name is not None:
            integration.name = update_in.name
        if update_in.type is not None:
            integration.type = update_in.type
        if update_in.is_active is not None:
            integration.is_active = update_in.is_active

        if update_in.config is not None:
            old_config = integration.config or {}
            new_config = copy.deepcopy(update_in.config)

            # Preserve existing credentials if frontend sends back the masked placeholder '********'
            for k, v in new_config.items():
                if v == "********" and k in old_config:
                    new_config[k] = old_config[k]
                elif isinstance(v, dict) and isinstance(old_config.get(k), dict):
                    for sub_k, sub_v in v.items():
                        if sub_v == "********" and sub_k in old_config[k]:
                            new_config[k][sub_k] = old_config[k][sub_k]

            integration.config = new_config

        updated = await self.integration_repo.update(integration)
        return self.to_safe_response(updated)

    async def delete_integration(self, integration_id: uuid.UUID, workspace_id: uuid.UUID) -> None:
        """Delete integration."""
        integration = await self.integration_repo.get_by_id_and_workspace(
            integration_id, workspace_id
        )
        if not integration:
            raise EntityNotFoundException("Integration", integration_id)
        await self.integration_repo.delete(integration)

    async def test_integration(
        self,
        integration_id: uuid.UUID,
        workspace_id: uuid.UUID,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Test API / webhook integration delivery."""
        integration = await self.integration_repo.get_by_id_and_workspace(
            integration_id, workspace_id
        )
        if not integration:
            raise EntityNotFoundException("Integration", integration_id)

        config = integration.config or {}
        url = config.get("url") or config.get("endpoint")
        if not url:
            raise ValidationException("Integration configuration is missing 'url' or 'endpoint'.")

        method = config.get("method", "POST")
        headers = dict(config.get("headers", {}))
        timeout = float(config.get("timeout", 10.0))
        retries = int(config.get("retries", 2))

        auth = config.get("auth") or config.get("authentication") or {}
        if auth.get("type") == "BEARER_TOKEN" and auth.get("token"):
            headers["Authorization"] = f"Bearer {auth['token']}"
        elif auth.get("type") == "API_KEY" and auth.get("key"):
            hdr = auth.get("header_name", "X-API-Key")
            headers[hdr] = auth["key"]

        body = payload or config.get("request_mapping") or config.get("body")

        return await workflow_engine.execute_http_request_with_retry(
            method=method,
            url=url,
            headers=headers,
            json_body=body,
            timeout=timeout,
            max_retries=retries,
        )

    async def dispatch_webhook(
        self, integration_id: uuid.UUID, workspace_id: uuid.UUID, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Dispatch webhook."""
        return await self.test_integration(integration_id, workspace_id, payload)
