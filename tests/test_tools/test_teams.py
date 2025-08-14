"""Tests for Teams tool."""

from unittest.mock import AsyncMock, patch

import pytest

from mcp_server_api_sports.models import ApiResponse
from mcp_server_api_sports.tools import TeamsTool


@pytest.mark.asyncio
async def test_teams_tool_search_by_id(api_service, cache_service, mock_team_response):
    """Test searching teams by ID."""
    tool = TeamsTool(api_service, cache_service)

    # Mock API response
    api_response = ApiResponse(**mock_team_response)

    with patch.object(api_service, "get_teams", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = api_response

        result = await tool.search_teams(id=33)

        assert result["count"] == 1
        assert len(result["teams"]) == 1
        assert result["teams"][0]["id"] == 33
        assert result["teams"][0]["name"] == "Manchester United"
        assert result["teams"][0]["venue"]["name"] == "Old Trafford"

        mock_get.assert_called_once_with(
            id=33,
            name=None,
            league=None,
            season=None,
            country=None,
            code=None,
            venue=None,
            search=None
        )


@pytest.mark.asyncio
async def test_teams_tool_search_validation(api_service, cache_service):
    """Test search parameter validation."""
    tool = TeamsTool(api_service, cache_service)

    # Search string too short
    result = await tool.search_teams(search="ab")

    assert "error" in result
    assert "at least 3 characters" in result["error"]


@pytest.mark.asyncio
async def test_teams_tool_search_with_cache(api_service, cache_service, mock_team_response):
    """Test teams search with caching."""
    tool = TeamsTool(api_service, cache_service)

    # Mock API response
    api_response = ApiResponse(**mock_team_response)

    with patch.object(api_service, "get_teams", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = api_response

        # First call - should hit API
        result1 = await tool.search_teams(id=33)
        assert mock_get.call_count == 1

        # Second call - should hit cache
        result2 = await tool.search_teams(id=33)
        assert mock_get.call_count == 1  # No additional API call

        # Results should be identical
        assert result1 == result2


@pytest.mark.asyncio
async def test_teams_tool_search_multiple_params(api_service, cache_service, mock_team_response):
    """Test searching teams with multiple parameters."""
    tool = TeamsTool(api_service, cache_service)

    # Mock API response
    api_response = ApiResponse(**mock_team_response)

    with patch.object(api_service, "get_teams", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = api_response

        result = await tool.search_teams(
            name="Manchester United",
            league=39,
            season=2023,
            country="England"
        )

        assert result["count"] == 1

        mock_get.assert_called_once_with(
            id=None,
            name="Manchester United",
            league=39,
            season=2023,
            country="England",
            code=None,
            venue=None,
            search=None
        )


@pytest.mark.asyncio
async def test_teams_tool_error_handling(api_service, cache_service):
    """Test error handling in teams tool."""
    tool = TeamsTool(api_service, cache_service)

    with patch.object(api_service, "get_teams", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = Exception("API Error")

        result = await tool.search_teams(id=33)

        assert "error" in result
        assert "Failed to search teams" in result["error"]


@pytest.mark.asyncio
async def test_teams_tool_definition():
    """Test teams tool definition."""
    tool = TeamsTool(None, None)
    definition = tool.get_tool_definition()

    assert definition["name"] == "teams_search"
    assert "description" in definition
    assert "inputSchema" in definition

    schema = definition["inputSchema"]
    assert schema["type"] == "object"
    assert "properties" in schema

    # Check all expected properties
    expected_properties = ["id", "name", "league", "season", "country", "code", "venue", "search"]
    for prop in expected_properties:
        assert prop in schema["properties"]
