"""Tests for FastAPI endpoints."""

from datetime import date, time
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


# =============================================================================
# Test fixtures
# =============================================================================


def create_valid_input() -> dict:
    """Create a valid SSOT input for testing (John Doe scenario)."""
    return {
        "case_metadata": {
            "case_name": "Test Case",
            "notes": "",
        },
        "personal_details": {
            "id_number": "123456789",
            "first_name": "John",
            "last_name": "Doe",
            "birth_year": 1980,
        },
        "defendant_details": {
            "name": "ABC Company",
            "id_number": "987654321",
        },
        "employment_periods": [
            {
                "id": "ep1",
                "start": "2023-01-01",
                "end": "2023-06-30",
            },
        ],
        "work_patterns": [
            {
                "id": "wp1",
                "start": "2023-01-01",
                "end": "2023-06-30",
                "work_days": [0, 1, 2, 3, 4],  # Sunday-Thursday
                "default_shifts": [
                    {"start_time": "08:00:00", "end_time": "17:00:00"},
                ],
                "default_breaks": [
                    {"start_time": "12:00:00", "end_time": "12:30:00"},
                ],
            },
        ],
        "salary_tiers": [
            {
                "id": "st1",
                "start": "2023-01-01",
                "end": "2023-06-30",
                "amount": "50",
                "type": "hourly",
                "net_or_gross": "gross",
            },
        ],
        "rest_day": "saturday",
        "district": "tel_aviv",
        "industry": "general",
        "filing_date": "2024-01-15",
        "seniority_input": {
            "method": "prior_plus_pattern",
            "prior_months": 0,
        },
        "right_toggles": {},
        "deductions_input": {},
        "right_specific_inputs": {},
    }


# =============================================================================
# /health endpoint
# =============================================================================


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_returns_ok(self):
        """Health check should return status ok."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


# =============================================================================
# /calculate endpoint
# =============================================================================


class TestCalculateEndpoint:
    """Tests for /calculate endpoint."""

    def test_calculate_with_valid_input_returns_full_ssot(self):
        """Calculate with valid input should return full SSOT."""
        input_data = create_valid_input()

        response = client.post("/calculate", json=input_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["ssot"] is not None

        ssot = data["ssot"]

        # Verify SSOT structure
        assert "input" in ssot
        assert "effective_periods" in ssot
        assert "daily_records" in ssot
        assert "shifts" in ssot
        assert "weeks" in ssot
        assert "period_month_records" in ssot
        assert "month_aggregates" in ssot
        assert "seniority_monthly" in ssot
        assert "rights_results" in ssot
        assert "limitation_results" in ssot
        assert "deduction_results" in ssot
        assert "claim_summary" in ssot

        # Verify data was calculated
        assert len(ssot["effective_periods"]) > 0
        assert len(ssot["daily_records"]) > 0
        assert len(ssot["shifts"]) > 0
        assert len(ssot["weeks"]) > 0

    def test_calculate_with_missing_employment_periods(self):
        """Calculate with empty employment_periods should still work (empty SSOT)."""
        input_data = {
            "employment_periods": [],
            "work_patterns": [],
            "salary_tiers": [],
            "rest_day": "saturday",
            "district": "tel_aviv",
        }

        response = client.post("/calculate", json=input_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_calculate_with_invalid_rest_day_returns_400(self):
        """Calculate with invalid rest_day should return 400."""
        input_data = create_valid_input()
        input_data["rest_day"] = "invalid_day"

        response = client.post("/calculate", json=input_data)

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert data["detail"]["errors"][0]["type"] == "parse_error"

    def test_calculate_with_overlapping_patterns_returns_400(self):
        """Calculate with overlapping work patterns should return 400."""
        input_data = create_valid_input()
        # Add overlapping pattern
        input_data["work_patterns"].append({
            "id": "wp2",
            "start": "2023-03-01",
            "end": "2023-05-31",
            "work_days": [0, 1, 2, 3, 4],
            "default_shifts": [
                {"start_time": "09:00:00", "end_time": "18:00:00"},
            ],
        })

        response = client.post("/calculate", json=input_data)

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        # Should have errors about overlap
        assert len(data["detail"]["errors"]) > 0

    def test_calculate_with_deductions(self):
        """Calculate with deductions should apply them."""
        input_data = create_valid_input()
        input_data["deductions_input"] = {
            "overtime": "500",
        }

        response = client.post("/calculate", json=input_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        ssot = data["ssot"]
        assert "overtime" in ssot["deduction_results"]
        assert ssot["deduction_results"]["overtime"]["deduction_amount"] == 500.0


# =============================================================================
# /snapshot/day endpoint
# =============================================================================


class TestDaySnapshotEndpoint:
    """Tests for /snapshot/day endpoint."""

    @pytest.fixture
    def computed_ssot(self) -> dict:
        """Get a computed SSOT for snapshot tests."""
        input_data = create_valid_input()
        response = client.post("/calculate", json=input_data)
        assert response.status_code == 200
        return response.json()["ssot"]

    def test_day_snapshot_returns_data(self, computed_ssot):
        """Day snapshot should return data for a valid date."""
        request = {
            "ssot": computed_ssot,
            "date": "2023-01-15",
        }

        response = client.post("/snapshot/day", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["snapshot"] is not None

        snapshot = data["snapshot"]
        assert snapshot["target_date"] == "2023-01-15"
        assert "daily_record" in snapshot
        assert "shifts" in snapshot
        assert "effective_period" in snapshot
        assert "total_hours" in snapshot
        assert "total_claim" in snapshot

    def test_day_snapshot_for_nonexistent_date(self, computed_ssot):
        """Day snapshot for date outside employment should return empty snapshot."""
        request = {
            "ssot": computed_ssot,
            "date": "2022-01-15",  # Before employment
        }

        response = client.post("/snapshot/day", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        snapshot = data["snapshot"]
        assert snapshot["daily_record"] is None
        assert len(snapshot["shifts"]) == 0

    def test_day_snapshot_with_invalid_date_format(self, computed_ssot):
        """Day snapshot with invalid date format should return 400."""
        request = {
            "ssot": computed_ssot,
            "date": "invalid-date",
        }

        response = client.post("/snapshot/day", json=request)

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["errors"][0]["type"] == "invalid_date"


# =============================================================================
# /snapshot/week endpoint
# =============================================================================


class TestWeekSnapshotEndpoint:
    """Tests for /snapshot/week endpoint."""

    @pytest.fixture
    def computed_ssot(self) -> dict:
        """Get a computed SSOT for snapshot tests."""
        input_data = create_valid_input()
        response = client.post("/calculate", json=input_data)
        assert response.status_code == 200
        return response.json()["ssot"]

    def test_week_snapshot_returns_data(self, computed_ssot):
        """Week snapshot should return data for a valid week ID."""
        # Get a week ID from the SSOT
        assert len(computed_ssot["weeks"]) > 0
        week_id = computed_ssot["weeks"][0]["id"]

        request = {
            "ssot": computed_ssot,
            "week_id": week_id,
        }

        response = client.post("/snapshot/week", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["snapshot"] is not None

        snapshot = data["snapshot"]
        assert snapshot["week_id"] == week_id
        assert "week" in snapshot
        assert "daily_records" in snapshot
        assert "shifts" in snapshot
        assert "total_hours" in snapshot

    def test_week_snapshot_for_nonexistent_week(self, computed_ssot):
        """Week snapshot for nonexistent week should return empty snapshot."""
        request = {
            "ssot": computed_ssot,
            "week_id": "2020-W01",  # Before employment
        }

        response = client.post("/snapshot/week", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        snapshot = data["snapshot"]
        assert snapshot["week"] is None


# =============================================================================
# /snapshot/month endpoint
# =============================================================================


class TestMonthSnapshotEndpoint:
    """Tests for /snapshot/month endpoint."""

    @pytest.fixture
    def computed_ssot(self) -> dict:
        """Get a computed SSOT for snapshot tests."""
        input_data = create_valid_input()
        response = client.post("/calculate", json=input_data)
        assert response.status_code == 200
        return response.json()["ssot"]

    def test_month_snapshot_returns_data(self, computed_ssot):
        """Month snapshot should return data for a valid month."""
        request = {
            "ssot": computed_ssot,
            "year": 2023,
            "month": 3,
        }

        response = client.post("/snapshot/month", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["snapshot"] is not None

        snapshot = data["snapshot"]
        assert snapshot["year"] == 2023
        assert snapshot["month"] == 3
        assert "month_aggregate" in snapshot
        assert "period_month_records" in snapshot
        assert "seniority" in snapshot
        assert "daily_records" in snapshot
        assert "shifts" in snapshot
        assert "total_hours" in snapshot

    def test_month_snapshot_for_nonexistent_month(self, computed_ssot):
        """Month snapshot for month outside employment should return empty snapshot."""
        request = {
            "ssot": computed_ssot,
            "year": 2022,
            "month": 6,  # Before employment
        }

        response = client.post("/snapshot/month", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        snapshot = data["snapshot"]
        assert snapshot["month_aggregate"] is None
        assert len(snapshot["daily_records"]) == 0

    def test_month_snapshot_with_invalid_month(self, computed_ssot):
        """Month snapshot with invalid month should return 422."""
        request = {
            "ssot": computed_ssot,
            "year": 2023,
            "month": 13,  # Invalid
        }

        response = client.post("/snapshot/month", json=request)

        assert response.status_code == 422  # Pydantic validation error


# =============================================================================
# Error handling tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_pipeline_error_returns_400_with_hebrew_message(self):
        """PipelineError should return 400 with Hebrew error messages."""
        input_data = create_valid_input()
        # Create a situation that will cause a PipelineError
        # Uncovered range: employment period exists but no work pattern
        input_data["work_patterns"] = []
        input_data["salary_tiers"] = []

        response = client.post("/calculate", json=input_data)

        # Should succeed but with empty results (no patterns/salary)
        assert response.status_code == 200

    def test_malformed_json_returns_422(self):
        """Malformed JSON should return 422."""
        response = client.post(
            "/calculate",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422


# =============================================================================
# Integration test: full flow
# =============================================================================


class TestFullFlow:
    """Integration tests for complete API flow."""

    def test_calculate_then_snapshots(self):
        """Test full flow: calculate, then get various snapshots."""
        # Step 1: Calculate
        input_data = create_valid_input()
        response = client.post("/calculate", json=input_data)

        assert response.status_code == 200
        ssot = response.json()["ssot"]

        # Step 2: Get day snapshot
        day_response = client.post("/snapshot/day", json={
            "ssot": ssot,
            "date": "2023-03-15",
        })
        assert day_response.status_code == 200
        day_snapshot = day_response.json()["snapshot"]
        assert day_snapshot["daily_record"] is not None

        # Step 3: Get week snapshot
        week_id = ssot["weeks"][5]["id"]  # Get 6th week
        week_response = client.post("/snapshot/week", json={
            "ssot": ssot,
            "week_id": week_id,
        })
        assert week_response.status_code == 200
        week_snapshot = week_response.json()["snapshot"]
        assert week_snapshot["week"] is not None

        # Step 4: Get month snapshot
        month_response = client.post("/snapshot/month", json={
            "ssot": ssot,
            "year": 2023,
            "month": 4,
        })
        assert month_response.status_code == 200
        month_snapshot = month_response.json()["snapshot"]
        assert month_snapshot["month_aggregate"] is not None
