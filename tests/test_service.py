"""Tests for API-Sports service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from mcp_server_api_sports.services import ApiSportsService, CacheService
from mcp_server_api_sports.models import ApiResponse


@pytest.mark.asyncio
async def test_api_service_initialization(api_service):
    """Test API service initialization."""
    assert api_service.base_url == "https://test.api-sports.io"
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
        mock_http_response.json.return_value = mock_response_data.dict()
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
    import time
    
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
    import time
    
    # Should allow initial calls
    await api_service.rate_limiter.acquire()
    
    # Check remaining calls
    remaining = api_service.rate_limiter.get_remaining()
    assert remaining["minute"] == 29  # 30 - 1
    assert remaining["day"] == 99  # 100 - 1