"""Tests for admin authentication."""

import pytest
from fastapi import HTTPException

from tgstats.web.auth_enhanced import AdminTokenManager, verify_admin_token


class TestAdminTokenManager:
    """Test AdminTokenManager functionality."""

    def test_generate_token(self):
        """Test token generation."""
        manager = AdminTokenManager()
        token = manager.generate_token()

        assert token.startswith("tgs_")
        assert len(token) > 20

    def test_verify_valid_token(self):
        """Test verifying a valid token."""
        manager = AdminTokenManager()
        token = manager.generate_token()

        is_valid = manager.verify_token(token)
        assert is_valid is True

    def test_verify_invalid_token(self):
        """Test verifying an invalid token."""
        manager = AdminTokenManager()

        is_valid = manager.verify_token("invalid_token_12345")
        assert is_valid is False

    def test_rate_limiting(self):
        """Test rate limiting functionality."""
        manager = AdminTokenManager()
        client_ip = "192.168.1.1"

        # Make multiple attempts
        for _ in range(12):
            manager.verify_token("invalid_token", client_ip)

        # Should be rate limited now
        is_valid = manager.verify_token("any_token", client_ip)
        assert is_valid is False

    def test_revoke_token(self):
        """Test token revocation."""
        manager = AdminTokenManager()
        token = manager.generate_token()

        # Verify token works
        assert manager.verify_token(token) is True

        # Revoke token
        success = manager.revoke_token(token)
        assert success is True

        # Token should no longer work
        assert manager.verify_token(token) is False

    def test_cannot_revoke_master_token(self):
        """Test that master token cannot be revoked."""
        manager = AdminTokenManager()

        if manager.master_token:
            success = manager.revoke_token(manager.master_token)
            assert success is False

    def test_list_tokens(self):
        """Test listing active tokens."""
        manager = AdminTokenManager()
        manager.generate_token()
        manager.generate_token()

        tokens = manager.list_tokens()
        assert len(tokens) >= 2


@pytest.mark.asyncio
class TestVerifyAdminTokenDependency:
    """Test FastAPI dependency for admin authentication."""

    async def test_verify_with_valid_token(self, monkeypatch):
        """Test authentication with valid token."""
        from tgstats.core import config
        from tgstats.web import auth_enhanced

        # Mock settings
        mock_settings = type("obj", (object,), {"admin_api_token": "test_token"})()
        monkeypatch.setattr(config, "settings", mock_settings)

        # Mock token_manager.verify_token to return True
        monkeypatch.setattr(auth_enhanced.token_manager, "verify_token", lambda token, ip: True)

        # Should succeed with valid token
        result = await verify_admin_token(x_admin_token="test_token", x_forwarded_for=None)
        assert result == "test_token"

    async def test_verify_without_token(self, monkeypatch):
        """Test authentication without token."""
        from tgstats.core import config

        mock_settings = type("obj", (object,), {"admin_api_token": "test_token"})()
        monkeypatch.setattr(config, "settings", mock_settings)

        # Should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await verify_admin_token(x_admin_token=None, x_forwarded_for=None)

        assert exc_info.value.status_code == 401
