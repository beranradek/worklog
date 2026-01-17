"""JIRA Cloud API client for logging work time."""

import base64
import logging
from collections import defaultdict
from datetime import date, datetime, time

import httpx
from supabase import Client, create_client

from .auth import User
from .config import Settings, get_settings
from .models import (
    BulkLogResult,
    BulkLogToJiraResponse,
    JiraConfig,
    JiraConfigResponse,
    JiraConfigUpdate,
    LogToJiraResponse,
    WorklogEntry,
)

logger = logging.getLogger(__name__)


class JiraClient:
    """Client for JIRA Cloud REST API v3."""

    def __init__(self, settings: Settings, user: User, access_token: str | None = None):
        """
        Initialize JIRA client.

        Args:
            settings: Application settings
            user: Authenticated user
            access_token: User's Supabase access token for RLS
        """
        self.settings = settings
        self.user = user
        self.access_token = access_token
        self._supabase: Client | None = None
        self._config: JiraConfig | None = None

    @property
    def supabase(self) -> Client:
        """Get authenticated Supabase client."""
        if not self._supabase:
            self._supabase = create_client(
                self.settings.supabase_url,
                self.settings.supabase_publishable_key,
            )
            if self.access_token:
                self._supabase.postgrest.auth(self.access_token)
        return self._supabase

    async def get_config(self) -> JiraConfigResponse:
        """
        Get user's JIRA configuration.

        Returns:
            JiraConfigResponse with configuration status
        """
        try:
            result = (
                self.supabase.table("user_jira_config")
                .select("*")
                .eq("user_id", str(self.user.id))
                .execute()
            )

            if result.data:
                config = result.data[0]
                return JiraConfigResponse(
                    configured=bool(config.get("jira_base_url")),
                    base_url=config.get("jira_base_url"),
                    has_token=bool(config.get("jira_api_token_encrypted")),
                    has_email=bool(config.get("jira_user_email")),
                )

            return JiraConfigResponse(
                configured=False,
                base_url=None,
                has_token=False,
                has_email=False,
            )

        except Exception as e:
            logger.error(f"Error fetching JIRA config: {e}")
            return JiraConfigResponse(
                configured=False, base_url=None, has_token=False, has_email=False
            )

    async def update_config(self, update: JiraConfigUpdate) -> JiraConfigResponse:
        """
        Update user's JIRA configuration.

        Args:
            update: Configuration updates

        Returns:
            Updated JiraConfigResponse
        """
        try:
            # Check if config exists
            existing = (
                self.supabase.table("user_jira_config")
                .select("id")
                .eq("user_id", str(self.user.id))
                .execute()
            )

            data = {"user_id": str(self.user.id)}
            if update.jira_base_url is not None:
                data["jira_base_url"] = update.jira_base_url
            if update.jira_user_email is not None:
                data["jira_user_email"] = update.jira_user_email
            if update.jira_api_token is not None:
                # In production, encrypt the token before storing
                # For now, we store it as-is (Supabase RLS protects it)
                data["jira_api_token_encrypted"] = update.jira_api_token

            if existing.data:
                # Update existing
                self.supabase.table("user_jira_config").update(data).eq(
                    "user_id", str(self.user.id)
                ).execute()
            else:
                # Insert new
                self.supabase.table("user_jira_config").insert(data).execute()

            return await self.get_config()

        except Exception as e:
            logger.error(f"Error updating JIRA config: {e}")
            raise

    async def _get_auth_header(self) -> str | None:
        """Get Basic auth header from stored credentials."""
        try:
            result = (
                self.supabase.table("user_jira_config")
                .select("jira_user_email, jira_api_token_encrypted")
                .eq("user_id", str(self.user.id))
                .execute()
            )

            if not result.data:
                return None

            config = result.data[0]
            email = config.get("jira_user_email")
            token = config.get("jira_api_token_encrypted")

            if not email or not token:
                return None

            credentials = f"{email}:{token}"
            encoded = base64.b64encode(credentials.encode()).decode()
            return f"Basic {encoded}"

        except Exception as e:
            logger.error(f"Error getting auth header: {e}")
            return None

    async def _get_base_url(self) -> str | None:
        """Get JIRA base URL from stored config."""
        try:
            result = (
                self.supabase.table("user_jira_config")
                .select("jira_base_url")
                .eq("user_id", str(self.user.id))
                .execute()
            )

            if result.data:
                return result.data[0].get("jira_base_url")
            return None

        except Exception as e:
            logger.error(f"Error getting base URL: {e}")
            return None

    def _calculate_time_spent(self, start_time: time, end_time: time) -> str:
        """
        Calculate time spent in JIRA format.

        Args:
            start_time: Start time
            end_time: End time

        Returns:
            Duration string like "2h 30m"
        """
        start_dt = datetime.combine(datetime.today(), start_time)
        end_dt = datetime.combine(datetime.today(), end_time)
        total_minutes = int((end_dt - start_dt).total_seconds() / 60)

        hours = total_minutes // 60
        minutes = total_minutes % 60

        if hours and minutes:
            return f"{hours}h {minutes}m"
        elif hours:
            return f"{hours}h"
        else:
            return f"{minutes}m"

    async def log_entry(self, entry: WorklogEntry, entry_date: date) -> LogToJiraResponse:
        """
        Log a single worklog entry to JIRA.

        Args:
            entry: Worklog entry to log
            entry_date: Date of the entry

        Returns:
            LogToJiraResponse with result
        """
        auth_header = await self._get_auth_header()
        base_url = await self._get_base_url()

        if not auth_header or not base_url:
            return LogToJiraResponse(
                success=False,
                entry_id=entry.id,
                error="JIRA not configured. Please set up JIRA credentials.",
            )

        try:
            # Calculate time spent
            time_spent = self._calculate_time_spent(entry.start_time, entry.end_time)

            # Build request body (no "started" field - JIRA uses current server time)
            body = {
                "timeSpent": time_spent,
            }

            # Add comment if description exists (in Atlassian Document Format)
            if entry.description:
                body["comment"] = {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": entry.description}],
                        }
                    ],
                }

            # Make API request
            url = f"{base_url}/rest/api/3/issue/{entry.issue_key}/worklog"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=body,
                    headers={
                        "Authorization": auth_header,
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    timeout=30.0,
                )

                if response.status_code == 201:
                    data = response.json()
                    return LogToJiraResponse(
                        success=True,
                        entry_id=entry.id,
                        jira_worklog_id=data.get("id"),
                    )
                else:
                    error_text = response.text
                    logger.error(f"JIRA API error: {response.status_code} - {error_text}")
                    return LogToJiraResponse(
                        success=False,
                        entry_id=entry.id,
                        error=f"JIRA API error: {response.status_code}",
                    )

        except httpx.TimeoutException:
            return LogToJiraResponse(
                success=False,
                entry_id=entry.id,
                error="Request timed out",
            )
        except Exception as e:
            logger.error(f"Error logging to JIRA: {e}")
            return LogToJiraResponse(
                success=False,
                entry_id=entry.id,
                error=str(e),
            )

    async def bulk_log_entries(
        self, entries: list[WorklogEntry], entry_date: date
    ) -> BulkLogToJiraResponse:
        """
        Bulk log entries to JIRA, aggregating by issue key.

        Entries with the same issue key are combined into a single worklog
        with summed duration and concatenated descriptions.

        Args:
            entries: List of entries to log
            entry_date: Date of the entries

        Returns:
            BulkLogToJiraResponse with results
        """
        if not entries:
            return BulkLogToJiraResponse(
                success=True,
                total_issues=0,
                success_count=0,
                failure_count=0,
                results=[],
            )

        # Group entries by issue key
        grouped: dict[str, list[WorklogEntry]] = defaultdict(list)
        for entry in entries:
            grouped[entry.issue_key].append(entry)

        results: list[BulkLogResult] = []
        success_count = 0
        failure_count = 0

        auth_header = await self._get_auth_header()
        base_url = await self._get_base_url()

        if not auth_header or not base_url:
            # Return all as failed
            for issue_key, issue_entries in grouped.items():
                results.append(
                    BulkLogResult(
                        issue_key=issue_key,
                        success=False,
                        entry_ids=[e.id for e in issue_entries],
                        duration="0m",
                        error="JIRA not configured",
                    )
                )
                failure_count += 1

            return BulkLogToJiraResponse(
                success=False,
                total_issues=len(grouped),
                success_count=0,
                failure_count=failure_count,
                results=results,
            )

        # Process each issue group
        for issue_key, issue_entries in grouped.items():
            # Calculate total duration
            total_minutes = 0
            descriptions = []
            entry_ids = []

            for entry in issue_entries:
                start_dt = datetime.combine(datetime.today(), entry.start_time)
                end_dt = datetime.combine(datetime.today(), entry.end_time)
                total_minutes += int((end_dt - start_dt).total_seconds() / 60)

                if entry.description:
                    descriptions.append(entry.description)
                entry_ids.append(entry.id)

            # Format duration
            hours = total_minutes // 60
            minutes = total_minutes % 60
            if hours and minutes:
                duration = f"{hours}h {minutes}m"
            elif hours:
                duration = f"{hours}h"
            else:
                duration = f"{minutes}m"

            # Build request body (no "started" field - JIRA uses current server time)
            body = {
                "timeSpent": duration,
            }

            # Combine descriptions
            if descriptions:
                combined_desc = " ".join(descriptions)
                body["comment"] = {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": combined_desc}],
                        }
                    ],
                }

            try:
                url = f"{base_url}/rest/api/3/issue/{issue_key}/worklog"
                logger.debug(f"Logging to JIRA {issue_key}: {body}")

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        url,
                        json=body,
                        headers={
                            "Authorization": auth_header,
                            "Content-Type": "application/json",
                            "Accept": "application/json",
                        },
                        timeout=30.0,
                    )

                    if response.status_code == 201:
                        data = response.json()
                        results.append(
                            BulkLogResult(
                                issue_key=issue_key,
                                success=True,
                                entry_ids=entry_ids,
                                duration=duration,
                                jira_worklog_id=data.get("id"),
                            )
                        )
                        success_count += 1
                    else:
                        error_text = response.text
                        logger.error(
                            f"JIRA API error for {issue_key}: {response.status_code} - {error_text}"
                        )
                        results.append(
                            BulkLogResult(
                                issue_key=issue_key,
                                success=False,
                                entry_ids=entry_ids,
                                duration=duration,
                                error=f"JIRA API error: {response.status_code} - {error_text[:200]}",
                            )
                        )
                        failure_count += 1

            except Exception as e:
                logger.error(f"Error logging {issue_key} to JIRA: {e}")
                results.append(
                    BulkLogResult(
                        issue_key=issue_key,
                        success=False,
                        entry_ids=entry_ids,
                        duration=duration,
                        error=str(e),
                    )
                )
                failure_count += 1

        return BulkLogToJiraResponse(
            success=failure_count == 0,
            total_issues=len(grouped),
            success_count=success_count,
            failure_count=failure_count,
            results=results,
        )


def get_jira_client(
    user: User, settings: Settings = None, access_token: str | None = None
) -> JiraClient:
    """Get JiraClient instance."""
    settings = settings or get_settings()
    return JiraClient(settings, user, access_token)
