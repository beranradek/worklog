"""Supabase authentication module with Google OAuth support."""

import logging
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from supabase import Client, create_client

from .config import Settings, get_settings

logger = logging.getLogger(__name__)

# HTTP Bearer token security scheme
security = HTTPBearer(auto_error=False)


class User(BaseModel):
    """Authenticated user model."""

    id: UUID
    email: str
    name: str | None = None
    avatar_url: str | None = None
    provider: str | None = None


class AuthResponse(BaseModel):
    """OAuth authentication response."""

    url: str


class TokenResponse(BaseModel):
    """Token exchange response."""

    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"
    user: User


class AuthCallbackRequest(BaseModel):
    """OAuth callback request with code and code verifier."""

    code: str
    code_verifier: str


def get_supabase_client(settings: Settings = Depends(get_settings)) -> Client:
    """Create Supabase client instance."""
    return create_client(settings.supabase_url, settings.supabase_publishable_key)


def get_supabase_admin_client(settings: Settings = Depends(get_settings)) -> Client | None:
    """Create Supabase admin client with service role key (for admin operations)."""
    if not settings.supabase_service_role_key:
        return None
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    settings: Settings = Depends(get_settings),
) -> User:
    """
    Validate JWT token and return current user.

    This function verifies the Supabase JWT token and extracts user information.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        # Create Supabase client and verify token
        supabase = create_client(settings.supabase_url, settings.supabase_publishable_key)

        # Get user from token
        user_response = supabase.auth.get_user(token)

        if not user_response or not user_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_data = user_response.user

        # Extract user metadata
        user_metadata = user_data.user_metadata or {}

        return User(
            id=UUID(user_data.id),
            email=user_data.email,
            name=user_metadata.get("full_name") or user_metadata.get("name"),
            avatar_url=user_metadata.get("avatar_url") or user_metadata.get("picture"),
            provider=user_data.app_metadata.get("provider") if user_data.app_metadata else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    settings: Settings = Depends(get_settings),
) -> User | None:
    """
    Optionally get current user if authenticated.

    Returns None if no valid token provided (doesn't raise exception).
    """
    if not credentials:
        return None

    try:
        supabase = create_client(settings.supabase_url, settings.supabase_publishable_key)
        user_response = supabase.auth.get_user(credentials.credentials)

        if not user_response or not user_response.user:
            return None

        user_data = user_response.user
        user_metadata = user_data.user_metadata or {}

        return User(
            id=UUID(user_data.id),
            email=user_data.email,
            name=user_metadata.get("full_name") or user_metadata.get("name"),
            avatar_url=user_metadata.get("avatar_url") or user_metadata.get("picture"),
            provider=user_data.app_metadata.get("provider") if user_data.app_metadata else None,
        )
    except Exception:
        return None


class AuthService:
    """Authentication service for handling OAuth flows."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.supabase = create_client(settings.supabase_url, settings.supabase_publishable_key)

    def get_google_oauth_url(
        self, redirect_url: str | None = None, code_challenge: str | None = None
    ) -> str:
        """
        Generate Google OAuth authorization URL with PKCE.

        Args:
            redirect_url: Optional custom redirect URL after authentication
            code_challenge: PKCE code challenge (SHA-256 hash of code_verifier)

        Returns:
            Google OAuth authorization URL
        """
        redirect_to = redirect_url or self.settings.frontend_url

        # Build query parameters for PKCE
        params = {
            "provider": "google",
            "redirect_to": redirect_to,
        }

        if code_challenge:
            logger.info(
                f"Adding PKCE code_challenge (length={len(code_challenge)}): {code_challenge[:10]}..."
            )
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
        else:
            logger.warning("No code_challenge provided - PKCE may fail")

        logger.info(f"OAuth params: {params}")

        # Use the raw authorize endpoint with PKCE parameters
        from urllib.parse import urlencode

        query_string = urlencode(params)
        auth_url = f"{self.settings.supabase_url}/auth/v1/authorize?{query_string}"

        logger.info(f"Generated OAuth URL: {auth_url[:150]}...")
        return auth_url

    async def exchange_code_for_session(self, code: str, code_verifier: str) -> TokenResponse:
        """
        Exchange OAuth code for session tokens with PKCE.

        Args:
            code: OAuth authorization code from callback
            code_verifier: PKCE code verifier generated before OAuth flow

        Returns:
            TokenResponse with access token and user info
        """
        try:
            logger.info(
                f"Exchanging code (length={len(code)}, starts={code[:10]}...) with verifier (length={len(code_verifier)}, starts={code_verifier[:10]}...)"
            )

            response = self.supabase.auth.exchange_code_for_session(
                {"auth_code": code, "code_verifier": code_verifier}
            )

            logger.info("Code exchange successful")

            if not response.session:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to exchange code for session",
                )

            session = response.session
            user_data = response.user
            user_metadata = user_data.user_metadata or {}

            return TokenResponse(
                access_token=session.access_token,
                refresh_token=session.refresh_token,
                expires_in=session.expires_in,
                user=User(
                    id=UUID(user_data.id),
                    email=user_data.email,
                    name=user_metadata.get("full_name") or user_metadata.get("name"),
                    avatar_url=user_metadata.get("avatar_url") or user_metadata.get("picture"),
                    provider=(
                        user_data.app_metadata.get("provider") if user_data.app_metadata else None
                    ),
                ),
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Code exchange error: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to exchange authorization code: {str(e)}",
            ) from e

    async def refresh_session(self, refresh_token: str) -> TokenResponse:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: Valid refresh token

        Returns:
            TokenResponse with new access token
        """
        try:
            response = self.supabase.auth.refresh_session(refresh_token)

            if not response.session:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Failed to refresh session",
                )

            session = response.session
            user_data = response.user
            user_metadata = user_data.user_metadata or {}

            return TokenResponse(
                access_token=session.access_token,
                refresh_token=session.refresh_token,
                expires_in=session.expires_in,
                user=User(
                    id=UUID(user_data.id),
                    email=user_data.email,
                    name=user_metadata.get("full_name") or user_metadata.get("name"),
                    avatar_url=user_metadata.get("avatar_url") or user_metadata.get("picture"),
                    provider=(
                        user_data.app_metadata.get("provider") if user_data.app_metadata else None
                    ),
                ),
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Session refresh error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to refresh session",
            ) from e

    async def sign_out(self, access_token: str) -> bool:
        """
        Sign out user and invalidate session.

        Args:
            access_token: Current access token

        Returns:
            True if sign out successful
        """
        try:
            self.supabase.auth.sign_out()
            return True
        except Exception as e:
            logger.error(f"Sign out error: {e}")
            return False


def get_auth_service(settings: Settings = Depends(get_settings)) -> AuthService:
    """Get AuthService instance."""
    return AuthService(settings)
