"""Database initialization and connection management using Supabase."""

import logging
from pathlib import Path

from supabase import Client, create_client

from .config import Settings, get_settings
from .models import DbStatus

logger = logging.getLogger(__name__)

# SQL initialization script path
SQL_INIT_PATH = Path(__file__).parent.parent.parent / "sql" / "init.sql"


class DatabaseManager:
    """Manages database initialization and health checks."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: Client | None = None

    @property
    def client(self) -> Client:
        """Get or create Supabase client."""
        if not self._client:
            self._client = create_client(
                self.settings.supabase_url,
                self.settings.supabase_service_role_key or self.settings.supabase_publishable_key,
            )
        return self._client

    async def check_tables_exist(self) -> bool:
        """Check if required tables exist in the database."""
        try:
            # Try to query worklog_entries table
            self.client.table("worklog_entries").select("id").limit(1).execute()
            return True
        except Exception as e:
            logger.debug(f"Tables check failed: {e}")
            return False

    async def get_status(self) -> DbStatus:
        """Get current database status."""
        tables_exist = await self.check_tables_exist()

        if tables_exist:
            return DbStatus(
                initialized=True,
                tables_exist=True,
                message="Database is initialized and ready",
            )
        else:
            return DbStatus(
                initialized=False,
                tables_exist=False,
                message="Database tables not found. Run initialization.",
            )

    def get_init_sql(self) -> str:
        """Load SQL initialization script."""
        if not SQL_INIT_PATH.exists():
            raise FileNotFoundError(f"SQL init script not found at {SQL_INIT_PATH}")
        return SQL_INIT_PATH.read_text()

    async def initialize(self, force: bool = False) -> DbStatus:
        """
        Initialize database with required tables.

        Note: This requires the service role key and should be run
        via Supabase SQL Editor or migration tool for production.

        Args:
            force: If True, reinitialize even if tables exist

        Returns:
            DbStatus with initialization result
        """
        if not force:
            tables_exist = await self.check_tables_exist()
            if tables_exist:
                return DbStatus(
                    initialized=True,
                    tables_exist=True,
                    message="Database already initialized",
                )

        # For Supabase, SQL must be run via:
        # 1. Supabase Dashboard SQL Editor
        # 2. Supabase CLI migrations
        # 3. Direct PostgreSQL connection (if available)

        self.get_init_sql()

        return DbStatus(
            initialized=False,
            tables_exist=False,
            message=(
                "Database initialization SQL is available. "
                "Please run it via Supabase Dashboard SQL Editor or CLI. "
                f"SQL file location: {SQL_INIT_PATH}"
            ),
        )


_db_manager: DatabaseManager | None = None


def get_database_manager(settings: Settings = None) -> DatabaseManager:
    """Get or create DatabaseManager instance."""
    global _db_manager
    if _db_manager is None:
        settings = settings or get_settings()
        _db_manager = DatabaseManager(settings)
    return _db_manager


async def init_database_on_startup():
    """
    Initialize database on application startup.

    This checks if tables exist and logs appropriate messages.
    """
    settings = get_settings()
    db_manager = get_database_manager(settings)

    status = await db_manager.get_status()

    if status.initialized:
        logger.info("Database is ready")
    else:
        logger.warning(
            "Database tables not found. Please run initialization SQL:\n"
            f"  SQL file: {SQL_INIT_PATH}\n"
            "  Run via Supabase Dashboard > SQL Editor"
        )

    return status
