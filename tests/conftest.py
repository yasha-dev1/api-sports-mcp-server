"""Pytest configuration and fixtures."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from mcp_server_api_sports.services import ApiSportsService, CacheService
from mcp_server_api_sports.models import ApiResponse


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch("mcp_server_api_sports.config.get_settings") as mock:
        settings = MagicMock()
        settings.api_sports_api_key = "test_api_key"
        settings.api_sports_base_url = "https://test.api-sports.io"
        settings.cache_enabled = True
        settings.cache_max_size = 100
        settings.cache_ttl_teams = 3600
        settings.cache_ttl_fixtures_completed = 0
        settings.cache_ttl_fixtures_upcoming = 1800
        settings.cache_ttl_statistics = 3600
        settings.cache_ttl_standings = 1800
        settings.cache_ttl_predictions = 3600
        settings.rate_limit_calls_per_minute = 30
        settings.rate_limit_calls_per_day = 100
        settings.rate_limit_burst_size = 10
        settings.rate_limit_backoff_factor = 2.0
        settings.rate_limit_max_retries = 3
        settings.log_level = "INFO"
        settings.log_file_path = "test.log"
        settings.log_rotation_size = "10MB"
        settings.log_retention_days = 7
        settings.log_format = "json"
        mock.return_value = settings
        yield settings


@pytest.fixture
async def api_service(mock_settings):
    """Create API service instance for testing."""
    service = ApiSportsService()
    yield service
    await service.close()


@pytest.fixture
def cache_service(mock_settings):
    """Create cache service instance for testing."""
    return CacheService()


@pytest.fixture
def mock_api_response():
    """Factory for creating mock API responses."""
    def _create_response(
        endpoint: str = "/test",
        results: int = 1,
        response_data: list = None,
        errors: Any = None
    ) -> ApiResponse:
        return ApiResponse(
            get=endpoint,
            parameters={},
            errors=errors or [],
            results=results,
            paging=None,
            response=response_data or []
        )
    return _create_response


@pytest.fixture
def mock_team_response():
    """Mock team API response."""
    return {
        "get": "teams",
        "parameters": {"id": "33"},
        "errors": [],
        "results": 1,
        "paging": {"current": 1, "total": 1},
        "response": [
            {
                "team": {
                    "id": 33,
                    "name": "Manchester United",
                    "code": "MUN",
                    "country": "England",
                    "founded": 1878,
                    "national": False,
                    "logo": "https://media.api-sports.io/football/teams/33.png"
                },
                "venue": {
                    "id": 556,
                    "name": "Old Trafford",
                    "address": "Sir Matt Busby Way",
                    "city": "Manchester",
                    "capacity": 74879,
                    "surface": "grass",
                    "image": "https://media.api-sports.io/football/venues/556.png"
                }
            }
        ]
    }


@pytest.fixture
def mock_fixture_response():
    """Mock fixture API response."""
    return {
        "get": "fixtures",
        "parameters": {"id": "1035000"},
        "errors": [],
        "results": 1,
        "paging": {"current": 1, "total": 1},
        "response": [
            {
                "fixture": {
                    "id": 1035000,
                    "referee": "Michael Oliver",
                    "timezone": "UTC",
                    "date": "2024-01-15T20:00:00+00:00",
                    "timestamp": 1705344000,
                    "periods": {
                        "first": 1705344000,
                        "second": 1705347600
                    },
                    "venue": {
                        "id": 556,
                        "name": "Old Trafford",
                        "city": "Manchester"
                    },
                    "status": {
                        "long": "Match Finished",
                        "short": "FT",
                        "elapsed": 90
                    }
                },
                "league": {
                    "id": 39,
                    "name": "Premier League",
                    "country": "England",
                    "logo": "https://media.api-sports.io/football/leagues/39.png",
                    "flag": "https://media.api-sports.io/flags/gb.svg",
                    "season": 2023,
                    "round": "Regular Season - 21"
                },
                "teams": {
                    "home": {
                        "id": 33,
                        "name": "Manchester United",
                        "logo": "https://media.api-sports.io/football/teams/33.png",
                        "winner": True
                    },
                    "away": {
                        "id": 40,
                        "name": "Liverpool",
                        "logo": "https://media.api-sports.io/football/teams/40.png",
                        "winner": False
                    }
                },
                "goals": {
                    "home": 2,
                    "away": 1
                },
                "score": {
                    "halftime": {
                        "home": 1,
                        "away": 0
                    },
                    "fulltime": {
                        "home": 2,
                        "away": 1
                    },
                    "extratime": {
                        "home": None,
                        "away": None
                    },
                    "penalty": {
                        "home": None,
                        "away": None
                    }
                }
            }
        ]
    }


@pytest.fixture
def mock_statistics_response():
    """Mock team statistics API response."""
    return {
        "get": "teams/statistics",
        "parameters": {
            "league": "39",
            "season": "2023",
            "team": "33"
        },
        "errors": [],
        "results": 1,
        "paging": {"current": 1, "total": 1},
        "response": {
            "league": {
                "id": 39,
                "name": "Premier League",
                "country": "England",
                "logo": "https://media.api-sports.io/football/leagues/39.png",
                "flag": "https://media.api-sports.io/flags/gb.svg",
                "season": 2023
            },
            "team": {
                "id": 33,
                "name": "Manchester United",
                "logo": "https://media.api-sports.io/football/teams/33.png"
            },
            "form": "WDWLW",
            "fixtures": {
                "played": {"home": 10, "away": 10, "total": 20},
                "wins": {"home": 7, "away": 5, "total": 12},
                "draws": {"home": 2, "away": 2, "total": 4},
                "loses": {"home": 1, "away": 3, "total": 4}
            },
            "goals": {
                "for": {
                    "total": {"home": 25, "away": 20, "total": 45},
                    "average": {"home": "2.5", "away": "2.0", "total": "2.3"},
                    "minute": {
                        "0-15": {"total": 5, "percentage": "11.11%"},
                        "16-30": {"total": 8, "percentage": "17.78%"},
                        "31-45": {"total": 6, "percentage": "13.33%"},
                        "46-60": {"total": 10, "percentage": "22.22%"},
                        "61-75": {"total": 9, "percentage": "20.00%"},
                        "76-90": {"total": 7, "percentage": "15.56%"}
                    }
                },
                "against": {
                    "total": {"home": 10, "away": 15, "total": 25},
                    "average": {"home": "1.0", "away": "1.5", "total": "1.3"},
                    "minute": {
                        "0-15": {"total": 3, "percentage": "12.00%"},
                        "16-30": {"total": 4, "percentage": "16.00%"},
                        "31-45": {"total": 5, "percentage": "20.00%"},
                        "46-60": {"total": 6, "percentage": "24.00%"},
                        "61-75": {"total": 4, "percentage": "16.00%"},
                        "76-90": {"total": 3, "percentage": "12.00%"}
                    }
                }
            },
            "biggest": {
                "streak": {"wins": 4, "draws": 2, "loses": 2},
                "wins": {"home": "4-0", "away": "3-1"},
                "loses": {"home": "1-2", "away": "0-3"},
                "goals": {
                    "for": {"home": 4, "away": 3},
                    "against": {"home": 2, "away": 3}
                }
            },
            "clean_sheet": {"home": 4, "away": 3, "total": 7},
            "failed_to_score": {"home": 1, "away": 2, "total": 3},
            "penalty": {
                "scored": {"total": 3, "percentage": "100.00%"},
                "missed": {"total": 0, "percentage": "0.00%"},
                "total": 3
            },
            "lineups": [
                {
                    "formation": "4-2-3-1",
                    "played": 15
                },
                {
                    "formation": "4-3-3",
                    "played": 5
                }
            ],
            "cards": {
                "yellow": {
                    "0-15": {"total": 2, "percentage": "6.67%"},
                    "16-30": {"total": 3, "percentage": "10.00%"},
                    "31-45": {"total": 5, "percentage": "16.67%"},
                    "46-60": {"total": 8, "percentage": "26.67%"},
                    "61-75": {"total": 7, "percentage": "23.33%"},
                    "76-90": {"total": 5, "percentage": "16.67%"},
                    "91-105": {"total": None, "percentage": None},
                    "106-120": {"total": None, "percentage": None}
                },
                "red": {
                    "0-15": {"total": 0, "percentage": "0.00%"},
                    "16-30": {"total": 0, "percentage": "0.00%"},
                    "31-45": {"total": 0, "percentage": "0.00%"},
                    "46-60": {"total": 1, "percentage": "50.00%"},
                    "61-75": {"total": 1, "percentage": "50.00%"},
                    "76-90": {"total": 0, "percentage": "0.00%"},
                    "91-105": {"total": None, "percentage": None},
                    "106-120": {"total": None, "percentage": None}
                }
            }
        }
    }