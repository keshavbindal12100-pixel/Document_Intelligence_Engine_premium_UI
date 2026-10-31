import pytest
from backend.app.repositories.user_repo import UserRepository


@pytest.mark.asyncio
async def test_get_user_with_workspaces_eager_loads_memberships(
    db_session, test_user, test_workspace
):
    user = await UserRepository(db_session).get_with_workspaces(test_user.id)

    assert user is not None
    assert user.id == test_user.id
    assert len(user.workspace_memberships) == 1
    assert user.workspace_memberships[0].workspace.id == test_workspace.id
