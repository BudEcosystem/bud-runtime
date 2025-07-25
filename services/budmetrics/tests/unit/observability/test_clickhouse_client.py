"""Unit tests for ClickHouseClient class."""

import pytest
import pytest_asyncio
import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict, Any

from budmetrics.observability.models import ClickHouseClient, QueryCache


class TestQueryCache:
    """Test cases for QueryCache class."""
    
    def test_cache_initialization(self):
        """Test QueryCache initialization."""
        cache = QueryCache(max_size=100, ttl=300)
        assert cache.max_size == 100
        assert cache.ttl == 300
        assert len(cache.cache) == 0
        assert len(cache.access_order) == 0
    
    @pytest.mark.asyncio
    async def test_cache_set_and_get(self):
        """Test basic cache set and get operations."""
        cache = QueryCache(max_size=10, ttl=60)
        
        # Set a value
        await cache.set("key1", {"data": "value1"})
        
        # Get the value
        result = await cache.get("key1")
        assert result == {"data": "value1"}
        
        # Get non-existent key
        result = await cache.get("key2")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self):
        """Test cache TTL expiration."""
        cache = QueryCache(max_size=10, ttl=1)
        
        # Set a value
        await cache.set("key1", {"data": "value1"})
        
        # Immediate get should work
        assert await cache.get("key1") == {"data": "value1"}
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Should return None after expiration
        assert await cache.get("key1") is None
    
    @pytest.mark.asyncio
    async def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = QueryCache(max_size=3, ttl=60)
        
        # Fill the cache
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        
        # Access key1 to make it most recently used
        await cache.get("key1")
        
        # Add a new item, should evict key2 (least recently used)
        await cache.set("key4", "value4")
        
        # Check cache contents
        assert await cache.get("key1") == "value1"  # Still there
        assert await cache.get("key2") is None      # Evicted
        assert await cache.get("key3") == "value3"  # Still there
        assert await cache.get("key4") == "value4"  # New item
    
    @pytest.mark.asyncio
    async def test_cache_clear(self):
        """Test cache clearing."""
        cache = QueryCache(max_size=10, ttl=60)
        
        # Add some items
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        
        # Clear cache
        await cache.clear()
        
        # Check everything is cleared
        assert len(cache.cache) == 0
        assert len(cache.access_order) == 0
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None
    
    def test_cache_key_generation(self):
        """Test cache key generation from query."""
        cache = QueryCache()
        
        # Same queries should generate same key
        query1 = "SELECT * FROM table WHERE id = 1"
        query2 = "SELECT * FROM table WHERE id = 1"
        assert cache._make_key(query1) == cache._make_key(query2)
        
        # Different queries should generate different keys
        query3 = "SELECT * FROM table WHERE id = 2"
        assert cache._make_key(query1) != cache._make_key(query3)
    
    @pytest.mark.asyncio
    async def test_cache_update_existing_key(self):
        """Test updating existing cache key."""
        cache = QueryCache(max_size=10, ttl=60)
        
        # Set initial value
        await cache.set("key1", "value1")
        
        # Update with new value
        await cache.set("key1", "value2")
        
        # Should get updated value
        assert await cache.get("key1") == "value2"
        
        # Should not create duplicate entries
        assert len(cache.cache) == 1
        assert len(cache.access_order) == 1


class TestClickHouseClient:
    """Test cases for ClickHouseClient class."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock config for ClickHouseClient."""
        from budmetrics.observability.models import ClickHouseConfig
        config = ClickHouseConfig(
            host="localhost",
            port=9000,
            database="test_db",
            user="test_user",
            password="test_pass",
            pool_max_size=10
        )
        return config
    
    @pytest_asyncio.fixture
    async def client(self, mock_config):
        """Create ClickHouseClient instance with mocked connection."""
        with patch('asynch.Pool') as mock_pool_class:
            mock_pool = AsyncMock()
            mock_pool_class.return_value = mock_pool
            mock_pool.startup = AsyncMock()
            
            client = ClickHouseClient(mock_config)
            yield client
            
            # Cleanup
            if hasattr(client, '_pool') and client._pool:
                await client.close()
    
    @pytest.mark.asyncio
    async def test_client_initialization(self, mock_config):
        """Test ClickHouseClient initialization."""
        with patch('asynch.Pool'):
            client = ClickHouseClient(mock_config)
            
            assert client.config.host == "localhost"
            assert client.config.port == 9000
            assert client.config.database == "test_db"
            assert client.config.user == "test_user"
            assert client.config.password == "test_pass"
            assert client.config.pool_max_size == 10
            # Query cache is initialized after initialize() is called
    
    @pytest.mark.asyncio
    async def test_connect(self, mock_config):
        """Test connection establishment."""
        mock_pool = AsyncMock()
        
        with patch('asynch.Pool') as mock_pool_class:
            mock_pool_class.return_value = mock_pool
            mock_pool.startup = AsyncMock()
            
            client = ClickHouseClient(mock_config)
            await client.initialize()
            
            # Check connection was created with correct parameters
            mock_pool_class.assert_called_once()
            call_args = mock_pool_class.call_args[1]
            assert call_args['host'] == 'localhost'
            assert call_args['port'] == 9000
            assert call_args['database'] == 'test_db'
            assert call_args['user'] == 'test_user'
            assert call_args['password'] == 'test_pass'
            
            assert client._pool == mock_pool
    
    
    
    @pytest.mark.asyncio
    async def test_warmup(self, client):
        """Test connection warmup happens during initialize."""
        client._initialized = False
        client.config.enable_connection_warmup = True
        
        with patch.object(client, '_warmup_connections', new_callable=AsyncMock) as mock_warmup:
            await client.initialize()
            mock_warmup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close(self, client):
        """Test connection closing."""
        # Mock connection
        mock_pool = AsyncMock()
        client._pool = mock_pool
        
        await client.close()
        
        # Should close connection 
        mock_pool.shutdown.assert_called_once()
        # Pool reference might still exist, but initialized flag should be False
        assert not client._initialized
    
    def test_profile_decorator_sync(self):
        """Test profile decorator with sync function."""
        from budmetrics.commons.profiling_utils import profile_sync, PerformanceMetrics
        
        # Create a mock performance metrics instance
        mock_metrics = Mock(spec=PerformanceMetrics)
        
        # Create a test class with the decorator
        class TestClass:
            def __init__(self):
                self.performance_metrics = mock_metrics
                
            @profile_sync("test_operation")
            def test_func(self, x, y):
                return x + y
        
        # Enable debug mode
        with patch('budmetrics.commons.config.app_settings.debug', True):
            # Create instance and call the function
            test_obj = TestClass()
            result = test_obj.test_func(1, 2)
        
        # Verify the function works correctly
        assert result == 3
        
        # Verify performance metrics were recorded
        mock_metrics.record_timing.assert_called_once()
        call_args = mock_metrics.record_timing.call_args
        assert call_args[0][0] == "test_operation"
        assert isinstance(call_args[0][1], float)  # Execution time
    
    @pytest.mark.asyncio
    async def test_profile_decorator_async(self):
        """Test profile decorator with async function."""
        from budmetrics.commons.profiling_utils import profile_async, PerformanceMetrics
        
        # Create a mock performance metrics instance
        mock_metrics = Mock(spec=PerformanceMetrics)
        
        # Create a test class with the decorator
        class TestClass:
            def __init__(self):
                self.performance_metrics = mock_metrics
                
            @profile_async("test_async_operation")
            async def test_async_func(self, x, y):
                await asyncio.sleep(0.01)
                return x + y
        
        # Enable debug mode
        with patch('budmetrics.commons.config.app_settings.debug', True):
            # Create instance and call the function
            test_obj = TestClass()
            result = await test_obj.test_async_func(3, 4)
        
        # Verify the function works correctly
        assert result == 7
        
        # Verify performance metrics were recorded
        mock_metrics.record_timing.assert_called_once()
        call_args = mock_metrics.record_timing.call_args
        assert call_args[0][0] == "test_async_operation"
        assert isinstance(call_args[0][1], float)  # Execution time
        assert call_args[0][1] >= 0.01  # Should be at least the sleep time
    
    
