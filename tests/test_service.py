"""Tests for API-Sports service."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_api_service_initialization(api_service):
    """Test API service initialization."""
    assert api_service.base_url == "https://v3.football.api-sports.io"
    assert api_service.api_key == "test_api_key"
    assert api_service.rate_limiter is not None


@pytest.mark.asyncio
async def test_api_service_make_request_success(api_service, mock_api_response):
    """Test successful API request."""
    mock_response_data = mock_api_response(
        endpoint="/teams",
        results=1,
        response_data=[{"team": {"id": 1, "name": "Test Team"}}]
    )

    with patch.object(api_service, "_get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.headers = {}
        mock_http_response.json.return_value = mock_response_data.model_dump()
        mock_client.get.return_value = mock_http_response
        mock_get_client.return_value = mock_client

        response = await api_service.make_request("/teams", {"id": 1})

        assert response.results == 1
        assert len(response.response) == 1
        mock_client.get.assert_called_once_with("/teams", params={"id": 1})


@pytest.mark.asyncio
async def test_api_service_rate_limiting(api_service):
    """Test rate limiting behavior."""
    with patch.object(api_service, "_get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_http_response = MagicMock()
        mock_http_response.status_code = 429
        mock_http_response.headers = {"Retry-After": "1"}
        mock_client.get.return_value = mock_http_response

        # Second attempt succeeds
        mock_success_response = MagicMock()
        mock_success_response.status_code = 200
        mock_success_response.headers = {}
        mock_success_response.json.return_value = {
            "get": "/test",
            "parameters": {},
            "errors": [],
            "results": 0,
            "response": []
        }
        mock_client.get.side_effect = [mock_http_response, mock_success_response]
        mock_get_client.return_value = mock_client

        with patch("asyncio.sleep", new_callable=AsyncMock):
            response = await api_service.make_request("/test")
            assert response.results == 0


@pytest.mark.asyncio
async def test_cache_service_get_set(cache_service):
    """Test cache get and set operations."""
    key = "test_key"
    value = {"data": "test"}

    # Initially empty
    result = await cache_service.get(key)
    assert result is None

    # Set value
    await cache_service.set(key, value, "teams")

    # Get value
    result = await cache_service.get(key)
    assert result == value

    # Check stats
    stats = cache_service.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1


@pytest.mark.asyncio
async def test_cache_service_ttl_expiration(cache_service):
    """Test cache TTL expiration."""

    key = "test_key"
    value = {"data": "test"}

    # Set with very short TTL
    with patch.object(cache_service, "_get_ttl", return_value=0.1):
        await cache_service.set(key, value, "teams")

    # Should be available immediately
    result = await cache_service.get(key)
    assert result == value

    # Wait for expiration
    await asyncio.sleep(0.2)

    # Should be expired
    result = await cache_service.get(key)
    assert result is None


@pytest.mark.asyncio
async def test_cache_service_lru_eviction(cache_service):
    """Test LRU eviction when cache is full."""
    cache_service.max_size = 2

    # Add items to fill cache
    await cache_service.set("key1", "value1", "teams")
    await cache_service.set("key2", "value2", "teams")

    # Access key1 to make it more recently used
    await cache_service.get("key1")

    # Add another item, should evict key2
    await cache_service.set("key3", "value3", "teams")

    # key1 and key3 should be present
    assert await cache_service.get("key1") == "value1"
    assert await cache_service.get("key3") == "value3"

    # key2 should be evicted
    assert await cache_service.get("key2") is None

    # Check eviction count
    assert cache_service.evictions == 1


@pytest.mark.asyncio
async def test_cache_service_invalidation(cache_service):
    """Test cache invalidation."""
    # Add multiple items
    await cache_service.set("teams:1", "team1", "teams")
    await cache_service.set("teams:2", "team2", "teams")
    await cache_service.set("fixtures:1", "fixture1", "fixtures_upcoming")

    # Invalidate teams
    count = await cache_service.invalidate("teams:")
    assert count == 2

    # Teams should be gone
    assert await cache_service.get("teams:1") is None
    assert await cache_service.get("teams:2") is None

    # Fixtures should remain
    assert await cache_service.get("fixtures:1") == "fixture1"

    # Clear all
    count = await cache_service.invalidate()
    assert count == 1
    assert await cache_service.get("fixtures:1") is None


@pytest.mark.asyncio
async def test_rate_limiter_acquire(api_service):
    """Test rate limiter acquire method."""

    # Should allow initial calls
    await api_service.rate_limiter.acquire()

    # Check remaining calls
    remaining = api_service.rate_limiter.get_remaining()
    assert remaining["minute"] == 29  # 30 - 1
    assert remaining["day"] == 99  # 100 - 1


# Tests for search_teams method (moved from test_tools/test_teams.py)

@pytest.mark.asyncio
async def test_search_teams_by_id(api_service, cache_service, mock_team_response):
    """Test searching teams by ID."""
    api_service.cache_service = cache_service
    
    # Mock API response
    from mcp_server_api_sports.models import ApiResponse
    api_response = ApiResponse(**mock_team_response)

    with patch.object(api_service, "get_teams", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = api_response

        result = await api_service.search_teams(id=33)

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
async def test_search_teams_validation(api_service, cache_service):
    """Test search parameter validation."""
    api_service.cache_service = cache_service

    # Search string too short
    result = await api_service.search_teams(search="ab")

    assert "error" in result
    assert "at least 3 characters" in result["error"]


@pytest.mark.asyncio
async def test_search_teams_with_cache(api_service, cache_service, mock_team_response):
    """Test teams search with caching."""
    api_service.cache_service = cache_service
    
    from mcp_server_api_sports.models import ApiResponse
    api_response = ApiResponse(**mock_team_response)

    with patch.object(api_service, "get_teams", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = api_response

        # First call - should hit API
        result1 = await api_service.search_teams(id=33)
        assert mock_get.call_count == 1

        # Second call - should hit cache
        result2 = await api_service.search_teams(id=33)
        assert mock_get.call_count == 1  # No additional API call

        # Results should be identical
        assert result1 == result2


@pytest.mark.asyncio
async def test_search_teams_multiple_params(api_service, cache_service, mock_team_response):
    """Test searching teams with multiple parameters."""
    api_service.cache_service = cache_service
    
    from mcp_server_api_sports.models import ApiResponse
    api_response = ApiResponse(**mock_team_response)

    with patch.object(api_service, "get_teams", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = api_response

        result = await api_service.search_teams(
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
async def test_search_teams_error_handling(api_service, cache_service):
    """Test error handling in teams search."""
    api_service.cache_service = cache_service

    with patch.object(api_service, "get_teams", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = Exception("API Error")

        result = await api_service.search_teams(id=33)

        assert "error" in result
        assert "Failed to search teams" in result["error"]


# Tests for search_fixtures method (moved from test_tools/test_fixtures.py)

@pytest.mark.asyncio
async def test_search_fixtures_by_id(api_service, cache_service, mock_fixture_response):
    """Test searching fixtures by ID."""
    api_service.cache_service = cache_service
    
    from mcp_server_api_sports.models import ApiResponse
    api_response = ApiResponse(**mock_fixture_response)

    with patch.object(api_service, "get_fixtures", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = api_response

        result = await api_service.search_fixtures(id=1035000)

        assert result["count"] == 1
        assert len(result["fixtures"]) == 1
        assert result["fixtures"][0]["id"] == 1035000
        assert result["fixtures"][0]["teams"]["home"]["name"] == "Manchester United"
        assert result["fixtures"][0]["goals"]["home"] == 2

        mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_search_fixtures_date_validation(api_service, cache_service):
    """Test date parameter validation in fixtures search."""
    api_service.cache_service = cache_service

    # Invalid date format
    result = await api_service.search_fixtures(date="15/01/2024")
    assert "error" in result
    assert "YYYY-MM-DD format" in result["error"]

    # Invalid from_date format
    result = await api_service.search_fixtures(from_date="15/01/2024")
    assert "error" in result
    assert "YYYY-MM-DD format" in result["error"]

    # Invalid to_date format
    result = await api_service.search_fixtures(to_date="2024/01/15")
    assert "error" in result
    assert "YYYY-MM-DD format" in result["error"]


@pytest.mark.asyncio
async def test_search_fixtures_last_next_validation(api_service, cache_service):
    """Test last and next parameter validation."""
    api_service.cache_service = cache_service

    # Last parameter too large
    result = await api_service.search_fixtures(last=100)
    assert "error" in result
    assert "2 digits or less" in result["error"]

    # Next parameter too large
    result = await api_service.search_fixtures(next=100)
    assert "error" in result
    assert "2 digits or less" in result["error"]


# Tests for get_team_statistics_formatted method (moved from test_tools/test_statistics.py)

@pytest.mark.asyncio
async def test_get_team_statistics_formatted(api_service, cache_service, mock_statistics_response):
    """Test getting formatted team statistics."""
    api_service.cache_service = cache_service
    
    from mcp_server_api_sports.models import ApiResponse
    api_response = ApiResponse(**mock_statistics_response)

    with patch.object(api_service, "get_team_statistics", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = api_response

        result = await api_service.get_team_statistics_formatted(
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
async def test_get_team_statistics_formatted_with_date(api_service, cache_service, mock_statistics_response):
    """Test getting formatted team statistics with date snapshot."""
    api_service.cache_service = cache_service
    
    from mcp_server_api_sports.models import ApiResponse
    api_response = ApiResponse(**mock_statistics_response)

    with patch.object(api_service, "get_team_statistics", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = api_response

        result = await api_service.get_team_statistics_formatted(
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
async def test_get_team_statistics_formatted_date_validation(api_service, cache_service):
    """Test date validation in statistics."""
    api_service.cache_service = cache_service

    # Invalid date format
    result = await api_service.get_team_statistics_formatted(
        league=39,
        season=2023,
        team=33,
        date="15/01/2024"
    )
    
    assert "error" in result
    assert "YYYY-MM-DD format" in result["error"]


# Tests for new tool methods

@pytest.mark.asyncio
async def test_get_standings_formatted(api_service, cache_service):
    """Test getting formatted standings."""
    api_service.cache_service = cache_service
    
    mock_standings_response = {
        "response": [{
            "league": {
                "id": 39,
                "name": "Premier League",
                "country": "England",
                "logo": "logo.png",
                "flag": "flag.png",
                "season": 2023,
                "standings": [[
                    {
                        "rank": 1,
                        "team": {"id": 33, "name": "Manchester United", "logo": "team.png"},
                        "points": 75,
                        "goalsDiff": 35,
                        "group": "Premier League",
                        "form": "WDWWW",
                        "status": "same",
                        "description": "Champions League",
                        "all": {"played": 30, "win": 23, "draw": 6, "lose": 1, "goals": {"for": 70, "against": 35}},
                        "home": {"played": 15, "win": 12, "draw": 3, "lose": 0, "goals": {"for": 40, "against": 15}},
                        "away": {"played": 15, "win": 11, "draw": 3, "lose": 1, "goals": {"for": 30, "against": 20}},
                        "update": "2024-01-15"
                    }
                ]]
            }
        }]
    }
    
    from mcp_server_api_sports.models import ApiResponse
    api_response = ApiResponse(**{"get": "/standings", "parameters": {}, "errors": [], "results": 1, "response": mock_standings_response["response"]})

    with patch.object(api_service, "get_standings", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = api_response

        result = await api_service.get_standings_formatted(league=39, season=2023)

        assert "standings" in result
        assert result["count"] == 1
        assert result["standings"][0]["rank"] == 1
        assert result["standings"][0]["team"]["name"] == "Manchester United"
        assert result["standings"][0]["points"] == 75


@pytest.mark.asyncio
async def test_get_head2head_formatted(api_service, cache_service, mock_fixture_response):
    """Test getting formatted head-to-head fixtures."""
    api_service.cache_service = cache_service
    
    from mcp_server_api_sports.models import ApiResponse
    api_response = ApiResponse(**mock_fixture_response)

    with patch.object(api_service, "get_fixtures_head2head", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = api_response

        result = await api_service.get_head2head_formatted(h2h="33-40")

        assert "fixtures" in result
        assert "statistics" in result
        assert result["count"] == 1
        assert "team1_wins" in result["statistics"]
        assert "team2_wins" in result["statistics"]
        assert "draws" in result["statistics"]


@pytest.mark.asyncio
async def test_get_head2head_formatted_validation(api_service, cache_service):
    """Test h2h parameter validation."""
    api_service.cache_service = cache_service

    # Invalid h2h format
    result = await api_service.get_head2head_formatted(h2h="33")
    assert "error" in result
    assert "team1-team2" in result["error"]


@pytest.mark.asyncio
async def test_get_fixture_statistics_formatted(api_service, cache_service):
    """Test getting formatted fixture statistics."""
    api_service.cache_service = cache_service
    
    mock_stats_response = {
        "response": [
            {
                "team": {"id": 33, "name": "Manchester United", "logo": "team.png"},
                "statistics": [
                    {"type": "Shots on Goal", "value": 6},
                    {"type": "Total Shots", "value": 15},
                    {"type": "Possession", "value": "58%"},
                    {"type": "Passes", "value": 456}
                ]
            },
            {
                "team": {"id": 40, "name": "Liverpool", "logo": "team2.png"},
                "statistics": [
                    {"type": "Shots on Goal", "value": 4},
                    {"type": "Total Shots", "value": 12},
                    {"type": "Possession", "value": "42%"},
                    {"type": "Passes", "value": 367}
                ]
            }
        ]
    }
    
    from mcp_server_api_sports.models import ApiResponse
    api_response = ApiResponse(**{"get": "/fixtures/statistics", "parameters": {}, "errors": [], "results": 2, "response": mock_stats_response["response"]})

    with patch.object(api_service, "get_fixture_statistics", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = api_response

        result = await api_service.get_fixture_statistics_formatted(fixture=1035000)

        assert "teams" in result
        assert len(result["teams"]) == 2
        assert result["teams"][0]["statistics"]["Shots on Goal"] == 6
        assert result["teams"][0]["statistics"]["Possession"] == "58%"


@pytest.mark.asyncio
async def test_get_fixture_events_formatted(api_service, cache_service):
    """Test getting formatted fixture events."""
    api_service.cache_service = cache_service
    
    mock_events_response = {
        "response": [
            {
                "time": {"elapsed": 15, "extra": None},
                "team": {"id": 33, "name": "Manchester United", "logo": "team.png"},
                "player": {"id": 1, "name": "Rashford"},
                "assist": {"id": 2, "name": "Bruno"},
                "type": "Goal",
                "detail": "Normal Goal",
                "comments": None
            },
            {
                "time": {"elapsed": 45, "extra": 2},
                "team": {"id": 40, "name": "Liverpool", "logo": "team2.png"},
                "player": {"id": 3, "name": "Salah"},
                "assist": {},
                "type": "Card",
                "detail": "Yellow Card",
                "comments": "Foul"
            }
        ]
    }
    
    from mcp_server_api_sports.models import ApiResponse
    api_response = ApiResponse(**{"get": "/fixtures/events", "parameters": {}, "errors": [], "results": 2, "response": mock_events_response["response"]})

    with patch.object(api_service, "get_fixture_events", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = api_response

        result = await api_service.get_fixture_events_formatted(fixture=1035000)

        assert "events" in result
        assert result["count"] == 2
        assert result["events"][0]["type"] == "Goal"
        assert result["events"][0]["player"]["name"] == "Rashford"


@pytest.mark.asyncio
async def test_get_fixture_lineups_formatted(api_service, cache_service):
    """Test getting formatted fixture lineups."""
    api_service.cache_service = cache_service
    
    mock_lineups_response = {
        "response": [
            {
                "team": {"id": 33, "name": "Manchester United", "logo": "team.png"},
                "formation": "4-2-3-1",
                "startXI": [
                    {"player": {"id": 1, "name": "De Gea", "number": 1, "pos": "G"}}
                ],
                "substitutes": [
                    {"player": {"id": 2, "name": "Heaton", "number": 22, "pos": "G"}}
                ],
                "coach": {"id": 100, "name": "Ten Hag", "photo": "coach.png"}
            }
        ]
    }
    
    from mcp_server_api_sports.models import ApiResponse
    api_response = ApiResponse(**{"get": "/fixtures/lineups", "parameters": {}, "errors": [], "results": 1, "response": mock_lineups_response["response"]})

    with patch.object(api_service, "get_fixture_lineups", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = api_response

        result = await api_service.get_fixture_lineups_formatted(fixture=1035000)

        assert "lineups" in result
        assert len(result["lineups"]) == 1
        assert result["lineups"][0]["formation"] == "4-2-3-1"
        assert result["lineups"][0]["coach"]["name"] == "Ten Hag"


@pytest.mark.asyncio
async def test_get_predictions_formatted(api_service, cache_service):
    """Test getting formatted predictions."""
    api_service.cache_service = cache_service
    
    mock_predictions_response = {
        "response": [{
            "winner": {"id": 33, "name": "Manchester United", "comment": "Win or draw"},
            "win_or_draw": True,
            "under_over": "Over 2.5",
            "goals": {"home": "1.5-2.5", "away": "0.5-1.5"},
            "advice": "Manchester United or draw",
            "percent": {"home": "45%", "draw": "30%", "away": "25%"},
            "league": {"id": 39, "name": "Premier League"},
            "teams": {
                "home": {"id": 33, "name": "Manchester United"},
                "away": {"id": 40, "name": "Liverpool"}
            },
            "comparison": {
                "form": {"home": "60%", "away": "40%"},
                "att": {"home": "55%", "away": "45%"},
                "def": {"home": "52%", "away": "48%"}
            },
            "h2h": []
        }]
    }
    
    from mcp_server_api_sports.models import ApiResponse
    api_response = ApiResponse(**{"get": "/predictions", "parameters": {}, "errors": [], "results": 1, "response": mock_predictions_response["response"]})

    with patch.object(api_service, "get_predictions", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = api_response

        result = await api_service.get_predictions_formatted(fixture=1035000)

        assert "predictions" in result
        assert result["predictions"]["winner"]["name"] == "Manchester United"
        assert result["predictions"]["advice"] == "Manchester United or draw"
        assert result["predictions"]["under_over"] == "Over 2.5"
