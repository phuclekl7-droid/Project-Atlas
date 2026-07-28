"""
Role-Based Access Control (Feature #74).
Manages permissions for users based on their roles.

Built on top of AuthManager (#75).

Roles (hierarchical):
- admin: Full access to everything
- user: Standard user access
- guest: Read-only, limited access

Usage:
    rbac = RBACManager(auth_manager)
    rbac.check_permission("admin", "delete_message")  # True
    rbac.check_permission("guest", "delete_message")   # False
    rbac.require_permission("user", "send_message")     # None
    rbac.require_permission("guest", "delete_message")  # raises PermissionDenied
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

from src.core import setup_logger

logger = setup_logger("rbac")


class PermissionDenied(Exception):
    """Raised when a user doesn't have the required permission."""
    def __init__(self, permission: str, role: str):
        self.permission = permission
        self.role = role
        super().__init__(f"Permission '{permission}' denied for role '{role}'")


class RoleLevel(IntEnum):
    """Numeric role levels (higher = more access)."""
    GUEST = 0
    USER = 10
    ADMIN = 100


# ── Role Hierarchy ──
_ROLE_LEVELS = {
    "guest": RoleLevel.GUEST,
    "user": RoleLevel.USER,
    "admin": RoleLevel.ADMIN,
}

# ── Permission Definitions ──
_PERMISSIONS = {
    # Chat permissions
    "send_message": {"guest", "user", "admin"},
    "delete_own_message": {"user", "admin"},
    "delete_any_message": {"admin"},
    "edit_own_message": {"user", "admin"},
    "edit_any_message": {"admin"},
    "export_chat": {"user", "admin"},

    # Session permissions
    "create_session": {"user", "admin"},
    "list_sessions": {"user", "admin"},
    "delete_session": {"admin"},
    "rename_session": {"user", "admin"},

    # Plugin permissions
    "execute_plugin": {"user", "admin"},
    "manage_plugins": {"admin"},

    # Knowledge base permissions
    "upload_document": {"user", "admin"},
    "search_knowledge": {"guest", "user", "admin"},
    "delete_document": {"admin"},
    "manage_knowledge": {"admin"},

    # Memory permissions
    "view_memory": {"user", "admin"},
    "clear_memory": {"admin"},
    "forget_memory": {"user", "admin"},

    # System permissions
    "view_settings": {"user", "admin"},
    "change_settings": {"admin"},
    "view_logs": {"admin"},
    "manage_users": {"admin"},
    "manage_api_keys": {"admin"},

    # Authentication permissions
    "register_user": {"admin"},
    "login": {"guest", "user", "admin"},
    "view_profile": {"guest", "user", "admin"},
}


@dataclass
class PermissionCheck:
    """Result of a permission check."""
    allowed: bool
    permission: str
    role: str
    reason: str = ""


class RBACManager:
    """
    Role-Based Access Control manager.

    Usage:
        rbac = RBACManager()
        rbac.check_permission("user", "send_message")  # PermissionCheck(allowed=True)
        rbac.require_permission("guest", "delete_message")  # raises PermissionDenied
    """

    def __init__(self, custom_permissions: Optional[dict] = None):
        """
        Initialize the RBAC manager.

        Args:
            custom_permissions: Optional dict of {permission: set(roles)} to extend defaults
        """
        self._permissions = dict(_PERMISSIONS)
        if custom_permissions:
            self._permissions.update(custom_permissions)

    def has_role(self, role: str) -> bool:
        """Check if a role exists in the hierarchy."""
        return role in _ROLE_LEVELS

    def get_role_level(self, role: str) -> int:
        """Get the numeric level of a role."""
        return _ROLE_LEVELS.get(role, RoleLevel.GUEST).value

    def check_permission(self, role: str, permission: str) -> PermissionCheck:
        """
        Check if a role has a specific permission.

        Args:
            role: The user's role (admin, user, guest)
            permission: The permission string to check

        Returns:
            PermissionCheck with result
        """
        # Normalize role
        role = role.lower() if role else "guest"
        if role not in _ROLE_LEVELS:
            return PermissionCheck(
                allowed=False,
                permission=permission,
                role=role,
                reason=f"Unknown role: {role}",
            )

        # Check if permission exists
        allowed_roles = self._permissions.get(permission)
        if allowed_roles is None:
            # Unknown permission: deny by default
            return PermissionCheck(
                allowed=False,
                permission=permission,
                role=role,
                reason=f"Unknown permission: {permission}",
            )

        # Check the role hierarchy
        role_level = self.get_role_level(role)
        for allowed_role in allowed_roles:
            allowed_level = self.get_role_level(allowed_role)
            if role_level >= allowed_level:
                return PermissionCheck(
                    allowed=True,
                    permission=permission,
                    role=role,
                    reason=f"Role '{role}' has permission '{permission}'",
                )

        return PermissionCheck(
            allowed=False,
            permission=permission,
            role=role,
            reason=f"Role '{role}' does not have '{permission}'",
        )

    def require_permission(self, role: str, permission: str) -> None:
        """
        Check permission and raise PermissionDenied if not allowed.

        Args:
            role: The user's role
            permission: The permission to check

        Raises:
            PermissionDenied if the role doesn't have the permission
        """
        check = self.check_permission(role, permission)
        if not check.allowed:
            raise PermissionDenied(permission, role)

    def list_permissions(self, role: str) -> list[str]:
        """List all permissions available to a specific role."""
        return sorted([
            perm for perm, roles in self._permissions.items()
            if self.check_permission(role, perm).allowed
        ])

    def list_all_permissions(self) -> dict[str, list[str]]:
        """List all permissions for all roles."""
        return {
            role: self.list_permissions(role)
            for role in sorted(_ROLE_LEVELS.keys())
        }

    def add_permission(self, permission: str, roles: set[str]) -> None:
        """Add a new permission or extend existing one."""
        if permission in self._permissions:
            self._permissions[permission] |= roles
        else:
            self._permissions[permission] = set(roles)

    def remove_permission(self, permission: str, role: str) -> bool:
        """Remove a role from a permission. Returns True if changed."""
        if permission in self._permissions:
            before = len(self._permissions[permission])
            self._permissions[permission].discard(role)
            return len(self._permissions[permission]) < before
        return False

    def get_stats(self) -> dict:
        """Get RBAC configuration statistics."""
        return {
            "roles": len(_ROLE_LEVELS),
            "permissions": len(self._permissions),
            "role_levels": {k: v.value for k, v in _ROLE_LEVELS.items()},
        }
