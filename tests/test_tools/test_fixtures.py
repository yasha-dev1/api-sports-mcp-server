"""Tests for Fixtures tool."""

from unittest.mock import AsyncMock, patch

import pytest

from mcp_server_api_sports.models import ApiResponse
from mcp_server_api_sports.tools import FixturesTool


@pytest.mark.asyncio
async def test_fixtures_tool_get_by_id(api_service, cache_service, mock_fixture_response):
    """Test getting fixture by ID."""
    tool = FixturesTool(api_service, cache_service)

    # Mock API response
    api_response = ApiResponse(**mock_fixture_response)

    with patch.object(api_service, "get_fixtures", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = api_response

        result = await tool.get_fixtures(id=1035000)

        assert result["count"] == 1
        assert len(result["fixtures"]) == 1
        assert result["fixtures"][0]["id"] == 1035000
        assert result["fixtures"][0]["teams"]["home"]["name"] == "Manchester United"
        assert result["fixtures"][0]["goals"]["home"] == 2

        mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_fixtures_tool_date_validation(api_service, cache_service):
    """Test date parameter validation."""
    tool = FixturesTool(api_service, cache_service)

    # Invalid date format
    result = await tool.get_fixtures(date="15/01/2024")
    assert "error" in result
    assert "YYYY-MM-DD format" in result["error"]

    # Invalid from_date format
    result = await tool.get_fixtures(from_date="15/01/2024")
    assert "error" in result
    assert "YYYY-MM-DD format" in result["error"]

    # Invalid to_date format
    result = await tool.get_fixtures(to_date="2024/01/15")
    assert "error" in result
    assert "YYYY-MM-DD format" in result["error"]


@pytest.mark.asyncio
async def test_fixtures_tool_parameter_validation(api_service, cache_service):
    """Test parameter validation."""
    tool = FixturesTool(api_service, cache_service)

    # Last parameter too large
    result = await tool.get_fixtures(last=100)
    assert "error" in result
    assert "2 digits or less" in result["error"]

    # Next parameter too large
    result = await tool.get_fixtures(next=150)
    assert "error" in result
    assert "2 digits or less" in result["error"]


@pytest.mark.asyncio
async def test_fixtures_tool_live_no_cache(api_service, cache_service, mock_fixture_response):
    """Test that live fixtures are not cached."""
    tool = FixturesTool(api_service, cache_service)

    # Mock API response
    api_response = ApiResponse(**mock_fixture_response)

    with patch.object(api_service, "get_fixtures", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = api_response

        # First call with live parameter
        result1 = await tool.get_fixtures(live="all")
        assert mock_get.call_count == 1

        # Second call with same parameters - should hit API again (no cache)
        result2 = await tool.get_fixtures(live="all")
        assert mock_get.call_count == 2


@pytest.mark.asyncio
async def test_fixtures_tool_completed_cache(api_service, cache_service):
    """Test caching for completed fixtures."""
    tool = FixturesTool(api_service, cache_service)

    # Create a completed fixture response
    completed_response = {
        "get": "fixtures",
        "parameters": {},
        "errors": [],
        "results": 1,
        "response": [
            {
                "fixture": {
                    "id": 1,
                    "status": {"short": "FT", "long": "Match Finished"}
                },
                "league": {},
                "teams": {"home": {}, "away": {}},
                "goals": {},
                "score": {}
            }
        ]
    }

    api_response = ApiResponse(**completed_response)

    with patch.object(api_service, "get_fixtures", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = api_response

        # First call - should hit API
        result1 = await tool.get_fixtures(id=1)
        assert mock_get.call_count == 1

        # Second call - should hit cache
        result2 = await tool.get_fixtures(id=1)
        assert mock_get.call_count == 1  # No additional API call


@pytest.mark.asyncio
async def test_fixtures_tool_is_completed_status(api_service, cache_service):
    """Test fixture completion status detection."""
    tool = FixturesTool(api_service, cache_service)

    # Test completed statuses
    completed_statuses = ["FT", "AET", "PEN", "PST", "CANC", "ABD", "AWD", "WO"]
    for status in completed_statuses:
        assert tool._is_fixture_completed(status) is True

    # Test non-completed statuses
    non_completed_statuses = ["NS", "1H", "HT", "2H", "LIVE", "ET", "P"]
    for status in non_completed_statuses:
        assert tool._is_fixture_completed(status) is False


@pytest.mark.asyncio
async def test_fixtures_tool_multiple_filters(api_service, cache_service, mock_fixture_response):
    """Test getting fixtures with multiple filters."""
    tool = FixturesTool(api_service, cache_service)

    # Mock API response
    api_response = ApiResponse(**mock_fixture_response)

    with patch.object(api_service, "get_fixtures", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = api_response

        result = await tool.get_fixtures(
            league=39,
            season=2023,
            team=33,
            date="2024-01-15",
            status="FT"
        )

        assert result["count"] == 1

        mock_get.assert_called_once_with(
            id=None,
            ids=None,
            live=None,
            date="2024-01-15",
            league=39,
            season=2023,
            team=33,
            last=None,
            next=None,
            from_date=None,
            to_date=None,
            round=None,
            status="FT",
            venue=None,
            timezone=None
        )


@pytest.mark.asyncio
async def test_fixtures_tool_error_handling(api_service, cache_service):
    """Test error handling in fixtures tool."""
    tool = FixturesTool(api_service, cache_service)

    with patch.object(api_service, "get_fixtures", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = Exception("API Error")

        result = await tool.get_fixtures(id=1)

        assert "error" in result
        assert "Failed to retrieve fixtures" in result["error"]


@pytest.mark.asyncio
async def test_fixtures_tool_definition():
    """Test fixtures tool definition."""
    tool = FixturesTool(None, None)
    definition = tool.get_tool_definition()

    assert definition["name"] == "fixtures_get"
    assert "description" in definition
    assert "inputSchema" in definition

    schema = definition["inputSchema"]
    assert schema["type"] == "object"
    assert "properties" in schema

    # Check key properties
    important_properties = ["id", "date", "league", "season", "team", "from", "to"]
    for prop in important_properties:
        assert prop in schema["properties"]
