"""Tests for Pydantic models."""

from datetime import date, datetime, time
from uuid import uuid4

import pytest
from pydantic import ValidationError

from worklog_app.models import (
    DayWorklog,
    WorklogEntry,
    WorklogEntryBase,
    WorklogEntryCreate,
    WorklogEntryUpdate,
)


class TestWorklogEntryBase:
    """Tests for WorklogEntryBase model."""

    def test_valid_entry(self):
        """Test creating a valid entry."""
        entry = WorklogEntryBase(
            issue_key="PROJ-123",
            start_time=time(9, 0),
            end_time=time(11, 30),
            description="Working on feature",
        )
        assert entry.issue_key == "PROJ-123"
        assert entry.start_time == time(9, 0)
        assert entry.end_time == time(11, 30)

    def test_issue_key_uppercase(self):
        """Test that issue key is converted to uppercase."""
        entry = WorklogEntryBase(
            issue_key="proj-123",
            start_time=time(9, 0),
            end_time=time(11, 30),
        )
        assert entry.issue_key == "PROJ-123"

    def test_issue_key_stripped(self):
        """Test that issue key whitespace is stripped."""
        entry = WorklogEntryBase(
            issue_key="  PROJ-123  ",
            start_time=time(9, 0),
            end_time=time(11, 30),
        )
        assert entry.issue_key == "PROJ-123"

    def test_empty_issue_key_fails(self):
        """Test that empty issue key raises validation error."""
        with pytest.raises(ValidationError):
            WorklogEntryBase(
                issue_key="",
                start_time=time(9, 0),
                end_time=time(11, 30),
            )

    def test_end_before_start_fails(self):
        """Test that end time before start time raises validation error."""
        with pytest.raises(ValidationError):
            WorklogEntryBase(
                issue_key="PROJ-123",
                start_time=time(11, 0),
                end_time=time(9, 0),  # Before start
            )

    def test_optional_description(self):
        """Test that description is optional."""
        entry = WorklogEntryBase(
            issue_key="PROJ-123",
            start_time=time(9, 0),
            end_time=time(11, 30),
        )
        assert entry.description is None


class TestWorklogEntryCreate:
    """Tests for WorklogEntryCreate model."""

    def test_includes_date(self):
        """Test that create model includes date."""
        entry = WorklogEntryCreate(
            date=date(2024, 1, 15),
            issue_key="PROJ-123",
            start_time=time(9, 0),
            end_time=time(11, 30),
        )
        assert entry.date == date(2024, 1, 15)


class TestWorklogEntry:
    """Tests for complete WorklogEntry model."""

    def test_duration_minutes(self):
        """Test duration calculation in minutes."""
        entry = WorklogEntry(
            id=uuid4(),
            user_id=uuid4(),
            date=date(2024, 1, 15),
            issue_key="PROJ-123",
            start_time=time(9, 0),
            end_time=time(11, 30),
            logged_to_jira=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert entry.duration_minutes == 150  # 2.5 hours

    def test_duration_formatted_hours_and_minutes(self):
        """Test formatted duration with hours and minutes."""
        entry = WorklogEntry(
            id=uuid4(),
            user_id=uuid4(),
            date=date(2024, 1, 15),
            issue_key="PROJ-123",
            start_time=time(9, 0),
            end_time=time(11, 30),
            logged_to_jira=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert entry.duration_formatted == "2h 30m"

    def test_duration_formatted_hours_only(self):
        """Test formatted duration with whole hours."""
        entry = WorklogEntry(
            id=uuid4(),
            user_id=uuid4(),
            date=date(2024, 1, 15),
            issue_key="PROJ-123",
            start_time=time(9, 0),
            end_time=time(11, 0),
            logged_to_jira=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert entry.duration_formatted == "2h"

    def test_duration_formatted_minutes_only(self):
        """Test formatted duration with minutes only."""
        entry = WorklogEntry(
            id=uuid4(),
            user_id=uuid4(),
            date=date(2024, 1, 15),
            issue_key="PROJ-123",
            start_time=time(9, 0),
            end_time=time(9, 45),
            logged_to_jira=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert entry.duration_formatted == "45m"


class TestDayWorklog:
    """Tests for DayWorklog model."""

    def test_from_entries(self):
        """Test creating DayWorklog from entries."""
        entry1 = WorklogEntry(
            id=uuid4(),
            user_id=uuid4(),
            date=date(2024, 1, 15),
            issue_key="PROJ-123",
            start_time=time(9, 0),
            end_time=time(11, 0),
            logged_to_jira=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        entry2 = WorklogEntry(
            id=uuid4(),
            user_id=uuid4(),
            date=date(2024, 1, 15),
            issue_key="PROJ-456",
            start_time=time(13, 0),
            end_time=time(15, 30),
            logged_to_jira=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        day_worklog = DayWorklog.from_entries(date(2024, 1, 15), [entry1, entry2])

        assert day_worklog.date == date(2024, 1, 15)
        assert len(day_worklog.entries) == 2
        assert day_worklog.total_minutes == 270  # 2h + 2.5h = 4.5h = 270m

    def test_empty_entries(self):
        """Test DayWorklog with no entries."""
        day_worklog = DayWorklog.from_entries(date(2024, 1, 15), [])
        assert day_worklog.total_minutes == 0
        assert len(day_worklog.entries) == 0


class TestWorklogEntryUpdate:
    """Tests for WorklogEntryUpdate model."""

    def test_all_fields_optional(self):
        """Test that all fields are optional for update."""
        update = WorklogEntryUpdate()
        assert update.issue_key is None
        assert update.start_time is None
        assert update.end_time is None
        assert update.description is None

    def test_partial_update(self):
        """Test partial update with some fields."""
        update = WorklogEntryUpdate(
            issue_key="PROJ-999",
            description="Updated description",
        )
        assert update.issue_key == "PROJ-999"
        assert update.description == "Updated description"
        assert update.start_time is None
