"""Worklog storage operations using Supabase PostgreSQL."""

import logging
from datetime import date, datetime, time

from supabase import Client, create_client

from .auth import User
from .config import Settings, get_settings
from .models import (
    DayWorklog,
    WorklogEntry,
    WorklogEntryCreate,
    WorklogEntryUpdate,
)

logger = logging.getLogger(__name__)


class WorklogStorage:
    """Storage operations for worklog entries."""

    def __init__(self, settings: Settings, access_token: str | None = None):
        """
        Initialize storage with Supabase client.

        Args:
            settings: Application settings
            access_token: User's access token for RLS authentication
        """
        self.settings = settings
        self._client: Client | None = None
        self._access_token = access_token

    @property
    def client(self) -> Client:
        """Get authenticated Supabase client."""
        if not self._client:
            self._client = create_client(
                self.settings.supabase_url,
                self.settings.supabase_publishable_key,
            )
            # Set auth header if we have a token (enables RLS)
            if self._access_token:
                self._client.postgrest.auth(self._access_token)
        return self._client

    def _row_to_entry(self, row: dict) -> WorklogEntry:
        """Convert database row to WorklogEntry model."""
        return WorklogEntry(
            id=row["id"],
            user_id=str(row["user_id"]),
            date=date.fromisoformat(row["date"]) if isinstance(row["date"], str) else row["date"],
            issue_key=row["issue_key"],
            start_time=(
                time.fromisoformat(row["start_time"])
                if isinstance(row["start_time"], str)
                else row["start_time"]
            ),
            end_time=(
                time.fromisoformat(row["end_time"])
                if isinstance(row["end_time"], str)
                else row["end_time"]
            ),
            description=row.get("description"),
            logged_to_jira=row.get("logged_to_jira", False),
            jira_worklog_id=row.get("jira_worklog_id"),
            created_at=(
                datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
                if isinstance(row["created_at"], str)
                else row["created_at"]
            ),
            updated_at=(
                datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00"))
                if isinstance(row["updated_at"], str)
                else row["updated_at"]
            ),
        )

    async def get_entries_for_date(self, user: User, entry_date: date) -> DayWorklog:
        """
        Get all worklog entries for a specific date.

        Args:
            user: Authenticated user
            entry_date: Date to fetch entries for

        Returns:
            DayWorklog containing all entries for the date
        """
        try:
            result = (
                self.client.table("worklog_entries")
                .select("*")
                .eq("user_id", str(user.id))
                .eq("date", entry_date.isoformat())
                .order("start_time")
                .execute()
            )

            entries = [self._row_to_entry(row) for row in result.data]
            return DayWorklog.from_entries(entry_date, entries)

        except Exception as e:
            logger.error(f"Error fetching entries for {entry_date}: {e}")
            raise

    async def get_entry_by_id(self, user: User, entry_id: int) -> WorklogEntry | None:
        """
        Get a specific worklog entry by ID.

        Args:
            user: Authenticated user
            entry_id: Entry ID

        Returns:
            WorklogEntry if found, None otherwise
        """
        try:
            result = (
                self.client.table("worklog_entries")
                .select("*")
                .eq("id", entry_id)
                .eq("user_id", str(user.id))
                .execute()
            )

            if result.data:
                return self._row_to_entry(result.data[0])
            return None

        except Exception as e:
            logger.error(f"Error fetching entry {entry_id}: {e}")
            raise

    async def create_entry(self, user: User, entry: WorklogEntryCreate) -> WorklogEntry:
        """
        Create a new worklog entry.

        Args:
            user: Authenticated user
            entry: Entry data

        Returns:
            Created WorklogEntry with generated ID
        """
        try:
            data = {
                "user_id": str(user.id),
                "date": entry.date.isoformat(),
                "issue_key": entry.issue_key,
                "start_time": entry.start_time.isoformat(),
                "end_time": entry.end_time.isoformat(),
                "description": entry.description,
                "logged_to_jira": False,
            }

            result = self.client.table("worklog_entries").insert(data).execute()

            if not result.data:
                raise Exception("Failed to create entry - no data returned")

            return self._row_to_entry(result.data[0])

        except Exception as e:
            logger.error(f"Error creating entry: {e}")
            raise

    async def update_entry(
        self, user: User, entry_id: int, update: WorklogEntryUpdate
    ) -> WorklogEntry | None:
        """
        Update an existing worklog entry.

        Args:
            user: Authenticated user
            entry_id: Entry ID to update
            update: Fields to update

        Returns:
            Updated WorklogEntry if found, None otherwise
        """
        try:
            # Build update data, excluding None values
            data = {}
            if update.issue_key is not None:
                data["issue_key"] = update.issue_key
            if update.start_time is not None:
                data["start_time"] = update.start_time.isoformat()
            if update.end_time is not None:
                data["end_time"] = update.end_time.isoformat()
            if update.description is not None:
                data["description"] = update.description
            if update.logged_to_jira is not None:
                data["logged_to_jira"] = update.logged_to_jira
            if update.jira_worklog_id is not None:
                data["jira_worklog_id"] = update.jira_worklog_id

            if not data:
                # Nothing to update, just return current entry
                return await self.get_entry_by_id(user, entry_id)

            result = (
                self.client.table("worklog_entries")
                .update(data)
                .eq("id", entry_id)
                .eq("user_id", str(user.id))
                .execute()
            )

            if result.data:
                return self._row_to_entry(result.data[0])
            return None

        except Exception as e:
            logger.error(f"Error updating entry {entry_id}: {e}")
            raise

    async def delete_entry(self, user: User, entry_id: int) -> bool:
        """
        Delete a worklog entry.

        Args:
            user: Authenticated user
            entry_id: Entry ID to delete

        Returns:
            True if entry was deleted, False if not found
        """
        try:
            result = (
                self.client.table("worklog_entries")
                .delete()
                .eq("id", entry_id)
                .eq("user_id", str(user.id))
                .execute()
            )

            return len(result.data) > 0

        except Exception as e:
            logger.error(f"Error deleting entry {entry_id}: {e}")
            raise

    async def save_entries_for_date(
        self, user: User, entry_date: date, entries: list[WorklogEntryCreate]
    ) -> DayWorklog:
        """
        Replace all entries for a date with new entries.

        This deletes existing entries and creates new ones.
        Used for bulk save operations from the UI.

        Args:
            user: Authenticated user
            entry_date: Date to save entries for
            entries: New entries to save

        Returns:
            DayWorklog with saved entries
        """
        try:
            # Delete existing entries for this date
            self.client.table("worklog_entries").delete().eq("user_id", str(user.id)).eq(
                "date", entry_date.isoformat()
            ).execute()

            # Insert new entries
            if entries:
                data = [
                    {
                        "user_id": str(user.id),
                        "date": entry_date.isoformat(),
                        "issue_key": e.issue_key,
                        "start_time": e.start_time.isoformat(),
                        "end_time": e.end_time.isoformat(),
                        "description": e.description,
                        "logged_to_jira": False,
                    }
                    for e in entries
                ]

                result = self.client.table("worklog_entries").insert(data).execute()
                saved_entries = [self._row_to_entry(row) for row in result.data]
            else:
                saved_entries = []

            return DayWorklog.from_entries(entry_date, saved_entries)

        except Exception as e:
            logger.error(f"Error saving entries for {entry_date}: {e}")
            raise

    async def get_entries_for_date_range(
        self, user: User, start_date: date, end_date: date
    ) -> list[WorklogEntry]:
        """
        Get entries for a date range.

        Args:
            user: Authenticated user
            start_date: Start of range (inclusive)
            end_date: End of range (inclusive)

        Returns:
            List of entries in the date range
        """
        try:
            result = (
                self.client.table("worklog_entries")
                .select("*")
                .eq("user_id", str(user.id))
                .gte("date", start_date.isoformat())
                .lte("date", end_date.isoformat())
                .order("date")
                .order("start_time")
                .execute()
            )

            return [self._row_to_entry(row) for row in result.data]

        except Exception as e:
            logger.error(f"Error fetching entries for range {start_date} - {end_date}: {e}")
            raise

    async def get_unlogged_entries_for_date(
        self, user: User, entry_date: date
    ) -> list[WorklogEntry]:
        """
        Get entries not yet logged to JIRA for a specific date.

        Args:
            user: Authenticated user
            entry_date: Date to fetch entries for

        Returns:
            List of unlogged entries
        """
        try:
            result = (
                self.client.table("worklog_entries")
                .select("*")
                .eq("user_id", str(user.id))
                .eq("date", entry_date.isoformat())
                .eq("logged_to_jira", False)
                .order("start_time")
                .execute()
            )

            return [self._row_to_entry(row) for row in result.data]

        except Exception as e:
            logger.error(f"Error fetching unlogged entries for {entry_date}: {e}")
            raise

    async def mark_entry_as_logged(
        self, user: User, entry_id: int, jira_worklog_id: str
    ) -> WorklogEntry | None:
        """
        Mark an entry as logged to JIRA.

        Args:
            user: Authenticated user
            entry_id: Entry ID
            jira_worklog_id: JIRA worklog ID

        Returns:
            Updated entry if found
        """
        return await self.update_entry(
            user,
            entry_id,
            WorklogEntryUpdate(logged_to_jira=True, jira_worklog_id=jira_worklog_id),
        )


def get_worklog_storage(
    settings: Settings = None, access_token: str | None = None
) -> WorklogStorage:
    """Get WorklogStorage instance."""
    settings = settings or get_settings()
    return WorklogStorage(settings, access_token)
