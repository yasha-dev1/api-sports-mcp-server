"""Tests for Team Statistics tool."""

import pytest
from unittest.mock import AsyncMock, patch

from mcp_server_api_sports.tools import TeamStatisticsTool
from mcp_server_api_sports.models import ApiResponse


@pytest.mark.asyncio
async def test_statistics_tool_get_stats(api_service, cache_service, mock_statistics_response):
    """Test getting team statistics."""
    tool = TeamStatisticsTool(api_service, cache_service)
    
    # Mock API response
    api_response = ApiResponse(**mock_statistics_response)
    
    with patch.object(api_service, "get_team_statistics", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = api_response
        
        result = await tool.get_team_statistics(
            league=39,
            season=2023,
            team=33
        )
        
        assert "statistics" in result
        stats = result["statistics"]
        
        assert stats["team"]["id"] == 33
        assert stats["team"]["name"] == "Manchester United"
        assert stats["form"] == "WDWLW"
        assert stats["fixtures"]["played"]["total"] == 20
        assert stats["goals"]["for"]["total"]["total"] == 45
        assert stats["clean_sheet"]["total"] == 7
        
        mock_get.assert_called_once_with(
            league=39,
            season=2023,
            team=33,
            date=None
        )


@pytest.mark.asyncio
async def test_statistics_tool_with_date(api_service, cache_service, mock_statistics_response):
    """Test getting team statistics with date snapshot."""
    tool = TeamStatisticsTool(api_service, cache_service)
    
    # Mock API response
    api_response = ApiResponse(**mock_statistics_response)
    
    with patch.object(api_service, "get_team_statistics", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = api_response
        
        result = await tool.get_team_statistics(
            league=39,
            season=2023,
            team=33,
            date="2024-01-15"
        )
        
        assert "statistics" in result
        
        mock_get.assert_called_once_with(
            league=39,
            season=2023,
            team=33,
            date="2024-01-15"
        )


@pytest.mark.asyncio
async def test_statistics_tool_date_validation(api_service, cache_service):
    """Test date parameter validation."""
    tool = TeamStatisticsTool(api_service, cache_service)
    
    # Invalid date format
    result = await tool.get_team_statistics(
        league=39,
        season=2023,
        team=33,
        date="15-01-2024"
    )
    
    assert "error" in result
    assert "YYYY-MM-DD format" in result["error"]


@pytest.mark.asyncio
async def test_statistics_tool_no_results(api_service, cache_service):
    """Test handling when no statistics are found."""
    tool = TeamStatisticsTool(api_service, cache_service)
    
    # Mock empty API response
    empty_response = ApiResponse(
        get="teams/statistics",
        parameters={},
        errors=[],
        results=0,
        response=[]
    )
    
    with patch.object(api_service, "get_team_statistics", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = empty_response
        
        result = await tool.get_team_statistics(
            league=39,
            season=2023,
            team=999  # Non-existent team
        )
        
        assert "error" in result
        assert "No statistics found" in result["error"]


@pytest.mark.asyncio
async def test_statistics_tool_with_cache(api_service, cache_service, mock_statistics_response):
    """Test statistics tool with caching."""
    tool = TeamStatisticsTool(api_service, cache_service)
    
    # Mock API response
    api_response = ApiResponse(**mock_statistics_response)
    
    with patch.object(api_service, "get_team_statistics", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = api_response
        
        # First call - should hit API
        result1 = await tool.get_team_statistics(
            league=39,
            season=2023,
            team=33
        )
        assert mock_get.call_count == 1
        
        # Second call - should hit cache
        result2 = await tool.get_team_statistics(
            league=39,
            season=2023,
            team=33
        )
        assert mock_get.call_count == 1  # No additional API call
        
        # Results should be identical
        assert result1 == result2


@pytest.mark.asyncio
async def test_statistics_tool_error_handling(api_service, cache_service):
    """Test error handling in statistics tool."""
    tool = TeamStatisticsTool(api_service, cache_service)
    
    with patch.object(api_service, "get_team_statistics", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = Exception("API Error")
        
        result = await tool.get_team_statistics(
            league=39,
            season=2023,
            team=33
        )
        
        assert "error" in result
        assert "Failed to retrieve team statistics" in result["error"]


@pytest.mark.asyncio
async def test_statistics_tool_definition():
    """Test statistics tool definition."""
    tool = TeamStatisticsTool(None, None)
    definition = tool.get_tool_definition()
    
    assert definition["name"] == "team_statistics"
    assert "description" in definition
    assert "inputSchema" in definition
    
    schema = definition["inputSchema"]
    assert schema["type"] == "object"
    assert "required" in schema
    assert set(schema["required"]) == {"league", "season", "team"}
    
    assert "properties" in schema
    assert "league" in schema["properties"]
    assert "season" in schema["properties"]
    assert "team" in schema["properties"]
    assert "date" in schema["properties"]