"""Main FastAPI application with worklog and authentication endpoints."""

import logging
from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .auth import (
    AuthCallbackRequest,
    AuthResponse,
    AuthService,
    TokenResponse,
    User,
    get_auth_service,
    get_current_user,
    optional_current_user,
)
from .config import Settings, get_settings
from .database import get_database_manager, init_database_on_startup
from .jira_client import JiraClient, get_jira_client
from .models import (
    BulkLogToJiraResponse,
    DayWorklog,
    DbStatus,
    JiraConfigResponse,
    JiraConfigUpdate,
    LogToJiraResponse,
    SaveWorklogRequest,
    WorklogEntry,
    WorklogEntryCreate,
    WorklogEntryUpdate,
)
from .storage import WorklogStorage, get_worklog_storage

logger = logging.getLogger(__name__)

# HTTP Bearer for extracting token
security = HTTPBearer(auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler - runs on startup and shutdown."""
    # Startup
    logger.info("Starting Worklog application...")

    # Check database status
    status = await init_database_on_startup()
    if not status.initialized:
        logger.warning(
            "Database not initialized. Please run the SQL initialization script."
        )

    yield

    # Shutdown
    logger.info("Shutting down Worklog application...")


def create_app(settings: Settings = None) -> FastAPI:
    """Create and configure FastAPI application."""
    settings = settings or get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="Worklog tracking application with Supabase auth and JIRA integration",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    register_routes(app, settings)

    return app


def register_routes(app: FastAPI, settings: Settings):
    """Register all API routes."""

    # ==========================================================================
    # Health & Status Endpoints
    # ==========================================================================

    @app.get("/health", tags=["Health"])
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "app": settings.app_name}

    @app.get("/api/status", tags=["Health"])
    async def api_status():
        """API status endpoint."""
        return {
            "status": "operational",
            "version": "1.0.0",
            "environment": settings.app_env,
        }

    @app.get("/api/db/status", response_model=DbStatus, tags=["Database"])
    async def database_status():
        """Check database initialization status."""
        db_manager = get_database_manager(settings)
        return await db_manager.get_status()

    @app.get("/api/db/init-sql", tags=["Database"])
    async def get_init_sql():
        """Get database initialization SQL script."""
        db_manager = get_database_manager(settings)
        try:
            sql = db_manager.get_init_sql()
            return {"sql": sql}
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))

    # ==========================================================================
    # Authentication Endpoints
    # ==========================================================================

    @app.get("/api/auth/google", response_model=AuthResponse, tags=["Authentication"])
    async def google_auth(
        redirect_url: Optional[str] = Query(None, description="Custom redirect URL"),
        code_challenge: Optional[str] = Query(None, description="PKCE code challenge"),
        auth_service: AuthService = Depends(get_auth_service),
    ):
        """
        Get Google OAuth authorization URL with PKCE support.

        Redirect user to this URL to start Google sign-in flow.
        For PKCE flow, provide code_challenge (SHA-256 hash of code_verifier).
        """
        url = auth_service.get_google_oauth_url(redirect_url, code_challenge)
        return AuthResponse(url=url)

    @app.get("/api/auth/google/redirect", tags=["Authentication"])
    async def google_auth_redirect(
        redirect_url: Optional[str] = Query(None),
        code_challenge: Optional[str] = Query(None),
        auth_service: AuthService = Depends(get_auth_service),
    ):
        """Redirect to Google OAuth (convenience endpoint) with PKCE support."""
        url = auth_service.get_google_oauth_url(redirect_url, code_challenge)
        return RedirectResponse(url=url)

    @app.post("/api/auth/callback", response_model=TokenResponse, tags=["Authentication"])
    async def auth_callback(
        request: AuthCallbackRequest,
        auth_service: AuthService = Depends(get_auth_service),
    ):
        """
        Exchange OAuth code for session tokens with PKCE.

        Called after user completes Google sign-in.
        Requires both the authorization code and PKCE code verifier.
        """
        return await auth_service.exchange_code_for_session(request.code, request.code_verifier)

    @app.post("/api/auth/refresh", response_model=TokenResponse, tags=["Authentication"])
    async def refresh_token(
        refresh_token: str = Query(..., description="Refresh token"),
        auth_service: AuthService = Depends(get_auth_service),
    ):
        """Refresh access token using refresh token."""
        return await auth_service.refresh_session(refresh_token)

    @app.post("/api/auth/logout", tags=["Authentication"])
    async def logout(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
        auth_service: AuthService = Depends(get_auth_service),
    ):
        """Sign out and invalidate session."""
        if credentials:
            await auth_service.sign_out(credentials.credentials)
        return {"message": "Logged out successfully"}

    @app.get("/api/auth/me", response_model=User, tags=["Authentication"])
    async def get_me(user: User = Depends(get_current_user)):
        """Get current authenticated user info."""
        return user

    # ==========================================================================
    # Worklog Endpoints
    # ==========================================================================

    def get_storage_with_token(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    ) -> WorklogStorage:
        """Get storage with user's access token for RLS."""
        token = credentials.credentials if credentials else None
        return get_worklog_storage(settings, token)

    @app.get(
        "/api/worklog/{entry_date}",
        response_model=DayWorklog,
        tags=["Worklog"],
    )
    async def get_worklog(
        entry_date: date,
        user: User = Depends(get_current_user),
        storage: WorklogStorage = Depends(get_storage_with_token),
    ):
        """
        Get all worklog entries for a specific date.

        Args:
            entry_date: Date in YYYY-MM-DD format
        """
        return await storage.get_entries_for_date(user, entry_date)

    @app.put(
        "/api/worklog/{entry_date}",
        response_model=DayWorklog,
        tags=["Worklog"],
    )
    async def save_worklog(
        entry_date: date,
        request: SaveWorklogRequest,
        user: User = Depends(get_current_user),
        storage: WorklogStorage = Depends(get_storage_with_token),
    ):
        """
        Save/replace all worklog entries for a date.

        This replaces all existing entries for the date.
        """
        entries = [
            WorklogEntryCreate(
                date=entry_date,
                issue_key=e.issue_key,
                start_time=e.start_time,
                end_time=e.end_time,
                description=e.description,
            )
            for e in request.entries
        ]
        return await storage.save_entries_for_date(user, entry_date, entries)

    @app.post(
        "/api/worklog/{entry_date}/entries",
        response_model=WorklogEntry,
        status_code=status.HTTP_201_CREATED,
        tags=["Worklog"],
    )
    async def create_entry(
        entry_date: date,
        entry: WorklogEntryCreate,
        user: User = Depends(get_current_user),
        storage: WorklogStorage = Depends(get_storage_with_token),
    ):
        """Create a new worklog entry."""
        # Ensure date matches
        entry.date = entry_date
        return await storage.create_entry(user, entry)

    @app.get(
        "/api/worklog/entries/{entry_id}",
        response_model=WorklogEntry,
        tags=["Worklog"],
    )
    async def get_entry(
        entry_id: int,
        user: User = Depends(get_current_user),
        storage: WorklogStorage = Depends(get_storage_with_token),
    ):
        """Get a specific worklog entry by ID."""
        entry = await storage.get_entry_by_id(user, entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")
        return entry

    @app.patch(
        "/api/worklog/entries/{entry_id}",
        response_model=WorklogEntry,
        tags=["Worklog"],
    )
    async def update_entry(
        entry_id: int,
        update: WorklogEntryUpdate,
        user: User = Depends(get_current_user),
        storage: WorklogStorage = Depends(get_storage_with_token),
    ):
        """Update a worklog entry."""
        entry = await storage.update_entry(user, entry_id, update)
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")
        return entry

    @app.delete(
        "/api/worklog/entries/{entry_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["Worklog"],
    )
    async def delete_entry(
        entry_id: int,
        user: User = Depends(get_current_user),
        storage: WorklogStorage = Depends(get_storage_with_token),
    ):
        """Delete a worklog entry."""
        deleted = await storage.delete_entry(user, entry_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Entry not found")

    @app.get(
        "/api/worklog/range",
        response_model=list[WorklogEntry],
        tags=["Worklog"],
    )
    async def get_entries_range(
        start_date: date = Query(..., description="Start date (inclusive)"),
        end_date: date = Query(..., description="End date (inclusive)"),
        user: User = Depends(get_current_user),
        storage: WorklogStorage = Depends(get_storage_with_token),
    ):
        """Get worklog entries for a date range."""
        return await storage.get_entries_for_date_range(user, start_date, end_date)

    # ==========================================================================
    # JIRA Integration Endpoints
    # ==========================================================================

    def get_jira_with_token(
        user: User = Depends(get_current_user),
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    ) -> JiraClient:
        """Get JIRA client with user's access token."""
        token = credentials.credentials if credentials else None
        return get_jira_client(user, settings, token)

    @app.get(
        "/api/worklog/jira/config",
        response_model=JiraConfigResponse,
        tags=["JIRA"],
    )
    async def get_jira_config(
        jira: JiraClient = Depends(get_jira_with_token),
    ):
        """Get current user's JIRA configuration status."""
        return await jira.get_config()

    @app.put(
        "/api/worklog/jira/config",
        response_model=JiraConfigResponse,
        tags=["JIRA"],
    )
    async def update_jira_config(
        config: JiraConfigUpdate,
        jira: JiraClient = Depends(get_jira_with_token),
    ):
        """Update current user's JIRA configuration."""
        return await jira.update_config(config)

    @app.post(
        "/api/worklog/{entry_date}/entries/{entry_id}/log-to-jira",
        response_model=LogToJiraResponse,
        tags=["JIRA"],
    )
    async def log_entry_to_jira(
        entry_date: date,
        entry_id: int,
        user: User = Depends(get_current_user),
        storage: WorklogStorage = Depends(get_storage_with_token),
        jira: JiraClient = Depends(get_jira_with_token),
    ):
        """Log a single worklog entry to JIRA."""
        # Get entry
        entry = await storage.get_entry_by_id(user, entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")

        if entry.logged_to_jira:
            return LogToJiraResponse(
                success=True,
                entry_id=entry_id,
                jira_worklog_id=entry.jira_worklog_id,
                error="Entry already logged to JIRA",
            )

        # Log to JIRA
        result = await jira.log_entry(entry, entry_date)

        # Update entry if successful
        if result.success and result.jira_worklog_id:
            await storage.mark_entry_as_logged(user, entry_id, result.jira_worklog_id)

        return result

    @app.post(
        "/api/worklog/{entry_date}/bulk-log-to-jira",
        response_model=BulkLogToJiraResponse,
        tags=["JIRA"],
    )
    async def bulk_log_to_jira(
        entry_date: date,
        user: User = Depends(get_current_user),
        storage: WorklogStorage = Depends(get_storage_with_token),
        jira: JiraClient = Depends(get_jira_with_token),
    ):
        """
        Bulk log all unlogged entries for a date to JIRA.

        Entries with the same issue key are aggregated into a single JIRA worklog.
        """
        # Get unlogged entries
        entries = await storage.get_unlogged_entries_for_date(user, entry_date)

        if not entries:
            return BulkLogToJiraResponse(
                success=True,
                total_entries=0,
                logged_entries=0,
                failed_entries=0,
                results=[],
            )

        # Bulk log to JIRA
        result = await jira.bulk_log_entries(entries, entry_date)

        # Mark successful entries as logged
        for bulk_result in result.results:
            if bulk_result.success and bulk_result.jira_worklog_id:
                for entry_id in bulk_result.entry_ids:
                    await storage.mark_entry_as_logged(
                        user, entry_id, bulk_result.jira_worklog_id
                    )

        return result


# Create the app instance
app = create_app()


def run():
    """Run the application with uvicorn."""
    settings = get_settings()

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    uvicorn.run(
        "worklog_app.main:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )


if __name__ == "__main__":
    run()
