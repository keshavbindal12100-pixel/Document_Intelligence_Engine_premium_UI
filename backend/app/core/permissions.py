from enum import StrEnum


class WorkspaceRole(StrEnum):
    ADMIN = "ADMIN"
    EDITOR = "EDITOR"
    REVIEWER = "REVIEWER"
    VIEWER = "VIEWER"


class Permission(StrEnum):
    # Workspace
    WORKSPACE_READ = "workspace:read"
    WORKSPACE_UPDATE = "workspace:update"
    WORKSPACE_DELETE = "workspace:delete"
    WORKSPACE_MANAGE_MEMBERS = "workspace:manage_members"

    # Documents
    DOCUMENT_UPLOAD = "document:upload"
    DOCUMENT_READ = "document:read"
    DOCUMENT_DELETE = "document:delete"
    DOCUMENT_PROCESS = "document:process"

    # Extraction & Review
    EXTRACTION_READ = "extraction:read"
    EXTRACTION_CORRECT = "extraction:correct"
    EXTRACTION_APPROVE = "extraction:approve"

    # Templates
    TEMPLATE_READ = "template:read"
    TEMPLATE_WRITE = "template:write"
    TEMPLATE_DELETE = "template:delete"

    # Workflows
    WORKFLOW_READ = "workflow:read"
    WORKFLOW_WRITE = "workflow:write"
    WORKFLOW_EXECUTE = "workflow:execute"

    # Integrations
    INTEGRATION_READ = "integration:read"
    INTEGRATION_WRITE = "integration:write"

    # Audit
    AUDIT_READ = "audit:read"


ROLE_PERMISSIONS: dict[WorkspaceRole, set[Permission]] = {
    WorkspaceRole.ADMIN: set(Permission),
    WorkspaceRole.EDITOR: {
        Permission.WORKSPACE_READ,
        Permission.DOCUMENT_UPLOAD,
        Permission.DOCUMENT_READ,
        Permission.DOCUMENT_DELETE,
        Permission.DOCUMENT_PROCESS,
        Permission.EXTRACTION_READ,
        Permission.EXTRACTION_CORRECT,
        Permission.EXTRACTION_APPROVE,
        Permission.TEMPLATE_READ,
        Permission.TEMPLATE_WRITE,
        Permission.TEMPLATE_DELETE,
        Permission.WORKFLOW_READ,
        Permission.WORKFLOW_WRITE,
        Permission.WORKFLOW_EXECUTE,
        Permission.INTEGRATION_READ,
        Permission.AUDIT_READ,
    },
    WorkspaceRole.REVIEWER: {
        Permission.WORKSPACE_READ,
        Permission.DOCUMENT_READ,
        Permission.EXTRACTION_READ,
        Permission.EXTRACTION_CORRECT,
        Permission.EXTRACTION_APPROVE,
        Permission.TEMPLATE_READ,
        Permission.WORKFLOW_READ,
        Permission.AUDIT_READ,
    },
    WorkspaceRole.VIEWER: {
        Permission.WORKSPACE_READ,
        Permission.DOCUMENT_READ,
        Permission.EXTRACTION_READ,
        Permission.TEMPLATE_READ,
        Permission.WORKFLOW_READ,
        Permission.INTEGRATION_READ,
        Permission.AUDIT_READ,
    },
}


def has_permission(user_role: WorkspaceRole, required_permission: Permission) -> bool:
    """Check if a given workspace role has the requested permission."""
    perms = ROLE_PERMISSIONS.get(user_role, set())
    return required_permission in perms
