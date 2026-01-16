"""Pydantic models for worklog entries and API requests/responses."""

from datetime import date as Date, datetime, time
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class WorklogEntryBase(BaseModel):
    """Base worklog entry fields."""

    issue_key: str = Field(..., min_length=1, max_length=50, description="JIRA issue key")
    start_time: time = Field(..., description="Start time (HH:MM)")
    end_time: time = Field(..., description="End time (HH:MM)")
    description: Optional[str] = Field(None, max_length=2000, description="Work description")

    @field_validator("issue_key")
    @classmethod
    def validate_issue_key(cls, v: str) -> str:
        """Validate JIRA issue key format (e.g., PROJ-123)."""
        v = v.strip().upper()
        if not v:
            raise ValueError("Issue key cannot be empty")
        return v

    @field_validator("end_time")
    @classmethod
    def validate_time_range(cls, v: time, info) -> time:
        """Validate that end_time is after start_time."""
        if "start_time" in info.data and v <= info.data["start_time"]:
            raise ValueError("End time must be after start time")
        return v


class WorklogEntryCreate(WorklogEntryBase):
    """Model for creating a new worklog entry."""

    date: Date = Field(..., description="Entry date (YYYY-MM-DD)")


class WorklogEntryUpdate(BaseModel):
    """Model for updating a worklog entry (all fields optional)."""

    issue_key: Optional[str] = Field(None, min_length=1, max_length=50)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    description: Optional[str] = Field(None, max_length=2000)
    logged_to_jira: Optional[bool] = None
    jira_worklog_id: Optional[str] = None


class WorklogEntry(WorklogEntryBase):
    """Complete worklog entry with all fields."""

    id: int | str  # Support both integer (BIGSERIAL) and UUID string
    user_id: str
    date: Date
    logged_to_jira: bool = False
    jira_worklog_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @property
    def duration_minutes(self) -> int:
        """Calculate duration in minutes."""
        start_dt = datetime.combine(datetime.today(), self.start_time)
        end_dt = datetime.combine(datetime.today(), self.end_time)
        return int((end_dt - start_dt).total_seconds() / 60)

    @property
    def duration_formatted(self) -> str:
        """Format duration as human-readable string (e.g., '2h 30m')."""
        minutes = self.duration_minutes
        hours = minutes // 60
        remaining_minutes = minutes % 60

        if hours and remaining_minutes:
            return f"{hours}h {remaining_minutes}m"
        elif hours:
            return f"{hours}h"
        else:
            return f"{remaining_minutes}m"


class DayWorklog(BaseModel):
    """All worklog entries for a specific day."""

    date: Date
    entries: list[WorklogEntry]
    total_minutes: int = 0

    @classmethod
    def from_entries(cls, entry_date: Date, entries: list[WorklogEntry]) -> "DayWorklog":
        """Create DayWorklog from list of entries."""
        total = sum(e.duration_minutes for e in entries)
        return cls(date=entry_date, entries=entries, total_minutes=total)


class SaveWorklogRequest(BaseModel):
    """Request to save/update multiple worklog entries for a day."""

    entries: list[WorklogEntryBase]


# JIRA Integration Models


class JiraConfig(BaseModel):
    """User's JIRA configuration."""

    jira_base_url: Optional[str] = None
    jira_user_email: Optional[str] = None
    has_token: bool = False


class JiraConfigUpdate(BaseModel):
    """Request to update JIRA configuration."""

    jira_base_url: Optional[str] = Field(None, max_length=255)
    jira_user_email: Optional[str] = Field(None, max_length=255)
    jira_api_token: Optional[str] = Field(None, max_length=500)


class JiraConfigResponse(BaseModel):
    """Response with JIRA configuration status."""

    configured: bool
    base_url: Optional[str] = None
    has_token: bool = False
    has_email: bool = False


class LogToJiraRequest(BaseModel):
    """Request to log entry to JIRA."""

    entry_id: int


class LogToJiraResponse(BaseModel):
    """Response from logging to JIRA."""

    success: bool
    entry_id: int | str
    jira_worklog_id: Optional[str] = None
    error: Optional[str] = None


class BulkLogResult(BaseModel):
    """Result of logging multiple entries for one issue."""

    issue_key: str
    success: bool
    entry_ids: list[int | str]
    duration: str
    jira_worklog_id: Optional[str] = None
    error: Optional[str] = None


class BulkLogToJiraResponse(BaseModel):
    """Response from bulk logging to JIRA."""

    success: bool
    total_issues: int
    success_count: int
    failure_count: int
    results: list[BulkLogResult]


# Database initialization


class DbStatus(BaseModel):
    """Database status response."""

    initialized: bool
    tables_exist: bool
    message: str
