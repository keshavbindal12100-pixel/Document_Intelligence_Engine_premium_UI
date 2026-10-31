import pytest
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_list_workspaces(client: AsyncClient, auth_headers: dict[str, str]):
    """Test workspace creation and listing via API."""
    # List workspaces
    list_res = await client.get("/api/v1/workspaces", headers=auth_headers)
    assert list_res.status_code == 200
    workspaces = list_res.json()
    assert len(workspaces) >= 1

    # Create new workspace
    create_payload = {
        "name": "Operations Team",
        "description": "Operations document workspace",
    }
    create_res = await client.post("/api/v1/workspaces", json=create_payload, headers=auth_headers)
    assert create_res.status_code == 201
    new_ws = create_res.json()
    assert new_ws["name"] == "Operations Team"
    assert "id" in new_ws


@pytest.mark.asyncio
async def test_workspace_membership_management(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_workspace: Workspace,
):
    """Test inviting new member to workspace."""
    # Register member user first
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "reviewer.member@example.com",
            "password": "Password12345!",
            "full_name": "Reviewer Person",
        },
    )

    # Add member to workspace
    add_member_payload = {
        "user_email": "reviewer.member@example.com",
        "role": "REVIEWER",
    }
    add_res = await client.post(
        f"/api/v1/workspaces/{test_workspace.id}/members",
        json=add_member_payload,
        headers=auth_headers,
    )
    assert add_res.status_code == 201
    member_data = add_res.json()
    assert member_data["role"] == "REVIEWER"

    # List members
    members_res = await client.get(
        f"/api/v1/workspaces/{test_workspace.id}/members",
        headers=auth_headers,
    )
    assert members_res.status_code == 200
    members = members_res.json()
    assert len(members) >= 2


@pytest.mark.asyncio
async def test_workspace_auto_fallback_without_header(
    client: AsyncClient,
    test_user: User,
    test_workspace: Workspace,
):
    """Ensure endpoints requiring workspace context resolve automatically without X-Workspace-Id header."""
    from backend.app.core.security import create_access_token

    token = create_access_token(subject=str(test_user.id))
    headers_no_ws = {"Authorization": f"Bearer {token}"}

    # Access /api/v1/workflows without X-Workspace-Id header
    res = await client.get("/api/v1/workflows", headers=headers_no_ws)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    # Access /api/v1/templates without X-Workspace-Id header
    res_tpl = await client.get("/api/v1/templates", headers=headers_no_ws)
    assert res_tpl.status_code == 200


@pytest.mark.asyncio
async def test_workspace_query_param_fallback(
    client: AsyncClient,
    test_user: User,
    test_workspace: Workspace,
):
    """Ensure workspace can be resolved via workspace_id query parameter."""
    from backend.app.core.security import create_access_token

    token = create_access_token(subject=str(test_user.id))
    headers_no_ws = {"Authorization": f"Bearer {token}"}

    # Pass workspace_id as query parameter
    res = await client.get(
        f"/api/v1/workflows?workspace_id={test_workspace.id}",
        headers=headers_no_ws,
    )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_workspace_auto_provisioning_for_user_without_workspaces(
    client: AsyncClient,
):
    """Ensure a user with zero existing workspaces gets a default workspace auto-created seamlessly."""
    # 1. Register a brand new user
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "auto.provision@example.com",
            "password": "Password12345!",
            "full_name": "New Auto Provision User",
        },
    )
    assert reg_res.status_code == 201

    login_res = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "auto.provision@example.com",
            "password": "Password12345!",
        },
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Call /api/v1/workflows with zero headers/params for workspace
    res = await client.get("/api/v1/workflows", headers=headers)
    assert res.status_code == 200
    assert res.json() == []

    # 3. Verify workspace was provisioned
    ws_list_res = await client.get("/api/v1/workspaces", headers=headers)
    assert ws_list_res.status_code == 200
    workspaces = ws_list_res.json()
    assert len(workspaces) >= 1
    assert "Default Workspace" in workspaces[0]["name"] or "workspace-" in workspaces[0]["slug"]
