"""
Tests for Feature #74: Role-Based Access Control.
"""

import pytest

from src.core.rbac_manager import RBACManager, PermissionDenied, PermissionCheck


class TestRBACManager:
    """Tests for the RBACManager class."""

    def test_admin_has_all_permissions(self):
        rbac = RBACManager()
        check = rbac.check_permission("admin", "send_message")
        assert check.allowed
        check = rbac.check_permission("admin", "delete_any_message")
        assert check.allowed
        check = rbac.check_permission("admin", "manage_users")
        assert check.allowed

    def test_user_has_basic_permissions(self):
        rbac = RBACManager()
        assert rbac.check_permission("user", "send_message").allowed
        assert rbac.check_permission("user", "list_sessions").allowed
        assert rbac.check_permission("user", "upload_document").allowed

    def test_user_lacks_admin_permissions(self):
        rbac = RBACManager()
        assert not rbac.check_permission("user", "manage_users").allowed
        assert not rbac.check_permission("user", "delete_any_message").allowed
        assert not rbac.check_permission("user", "manage_api_keys").allowed

    def test_guest_has_limited_permissions(self):
        rbac = RBACManager()
        assert rbac.check_permission("guest", "login").allowed
        assert rbac.check_permission("guest", "search_knowledge").allowed
        assert not rbac.check_permission("guest", "send_message").allowed
        assert not rbac.check_permission("guest", "upload_document").allowed

    def test_unknown_role(self):
        rbac = RBACManager()
        check = rbac.check_permission("unknown_role", "send_message")
        assert not check.allowed
        assert "Unknown role" in check.reason

    def test_unknown_permission(self):
        rbac = RBACManager()
        check = rbac.check_permission("admin", "nonexistent_permission")
        assert not check.allowed

    def test_require_permission_passes(self):
        rbac = RBACManager()
        rbac.require_permission("admin", "manage_users")  # Should not raise

    def test_require_permission_raises(self):
        rbac = RBACManager()
        with pytest.raises(PermissionDenied):
            rbac.require_permission("guest", "manage_users")

    def test_list_permissions_for_admin(self):
        rbac = RBACManager()
        perms = rbac.list_permissions("admin")
        assert len(perms) > 20
        assert "send_message" in perms
        assert "manage_users" in perms

    def test_list_permissions_for_guest(self):
        rbac = RBACManager()
        perms = rbac.list_permissions("guest")
        assert len(perms) < 10
        assert "login" in perms
        assert "manage_users" not in perms

    def test_list_all_permissions(self):
        rbac = RBACManager()
        all_perms = rbac.list_all_permissions()
        assert "admin" in all_perms
        assert "user" in all_perms
        assert "guest" in all_perms

    def test_add_permission(self):
        rbac = RBACManager()
        rbac.add_permission("custom_perm", {"admin", "user"})
        assert rbac.check_permission("user", "custom_perm").allowed
        assert not rbac.check_permission("guest", "custom_perm").allowed

    def test_remove_permission(self):
        rbac = RBACManager()
        assert rbac.check_permission("user", "delete_own_message").allowed
        rbac.remove_permission("delete_own_message", "user")
        assert not rbac.check_permission("user", "delete_own_message").allowed
        # Admin should still have it
        assert rbac.check_permission("admin", "delete_own_message").allowed

    def test_get_stats(self):
        rbac = RBACManager()
        stats = rbac.get_stats()
        assert stats["roles"] == 3
        assert stats["permissions"] > 20

    def test_has_role(self):
        rbac = RBACManager()
        assert rbac.has_role("admin")
        assert rbac.has_role("user")
        assert rbac.has_role("guest")
        assert not rbac.has_role("superadmin")

    def test_role_level(self):
        rbac = RBACManager()
        assert rbac.get_role_level("admin") > rbac.get_role_level("user")
        assert rbac.get_role_level("user") > rbac.get_role_level("guest")
