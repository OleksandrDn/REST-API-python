import pytest
import asyncio
import time
from unittest.mock import Mock, patch, MagicMock
from fastapi import HTTPException, Request
from bson import ObjectId

from app.rate_limiter import RateLimiter, rate_limit_dependency, authenticated_rate_limit_dependency


class MockRedis:
    """Mock Redis клієнт для тестування"""
    
    def __init__(self):
        self.data = {}
        self.ttl_data = {}
    
    def ping(self):
        return True
    
    def pipeline(self):
        return MockPipeline(self)
    
    def zremrangebyscore(self, key, min_score, max_score):
        if key in self.data:
            # Видаляємо записи з score між min_score та max_score (включно з межами)
            original_data = self.data[key].copy()
            self.data[key] = {
                member: score for member, score in original_data.items()
                if not (min_score <= score <= max_score)
            }
    
    def zadd(self, key, mapping):
        if key not in self.data:
            self.data[key] = {}
        self.data[key].update(mapping)
    
    def zcard(self, key):
        return len(self.data.get(key, {}))
    
    def expire(self, key, seconds):
        self.ttl_data[key] = time.time() + seconds


class MockPipeline:
    """Mock Redis pipeline для тестування"""
    
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.commands = []
    
    def zremrangebyscore(self, key, min_score, max_score):
        self.commands.append(('zremrangebyscore', key, min_score, max_score))
        return self
    
    def zadd(self, key, mapping):
        self.commands.append(('zadd', key, mapping))
        return self
    
    def expire(self, key, seconds):
        self.commands.append(('expire', key, seconds))
        return self
    
    def zcard(self, key):
        self.commands.append(('zcard', key))
        return self
    
    def execute(self):
        results = []
        for command in self.commands:
            if command[0] == 'zremrangebyscore':
                # Виконуємо операцію і повертаємо кількість видалених елементів
                old_count = len(self.redis_client.data.get(command[1], {}))
                self.redis_client.zremrangebyscore(command[1], command[2], command[3])
                new_count = len(self.redis_client.data.get(command[1], {}))
                removed_count = old_count - new_count
                results.append(removed_count)
            elif command[0] == 'zadd':
                self.redis_client.zadd(command[1], command[2])
                results.append(len(command[2]))  # Повертаємо кількість доданих елементів
            elif command[0] == 'expire':
                self.redis_client.expire(command[1], command[2])
                results.append(True)  # Повертаємо True для успішного встановлення TTL
            elif command[0] == 'zcard':
                result = self.redis_client.zcard(command[1])
                results.append(result)
        
        # Очищаємо команди після виконання
        self.commands = []
        return results


class MockRequest:
    """Mock FastAPI Request для тестування"""
    
    def __init__(self, client_host="127.0.0.1", headers=None):
        self.client = Mock()
        self.client.host = client_host
        self.headers = headers or {}
        self.state = Mock()


@pytest.fixture
def mock_redis():
    """Фікстура для mock Redis клієнта"""
    return MockRedis()


@pytest.fixture
def rate_limiter_with_redis(mock_redis):
    """Фікстура для RateLimiter з mock Redis"""
    return RateLimiter(redis_client=mock_redis)


@pytest.fixture
def rate_limiter_memory():
    """Фікстура для RateLimiter з in-memory сховищем"""
    return RateLimiter(redis_client=None)


@pytest.fixture
def mock_user():
    """Фікстура для mock користувача"""
    return {
        "_id": ObjectId(),
        "email": "test@example.com",
        "username": "testuser"
    }


class TestRateLimiterRedis:
    """Тести для RateLimiter з Redis"""
    
    @pytest.mark.asyncio
    async def test_anonymous_user_within_limit(self, rate_limiter_with_redis):
        """Тест: анонімний користувач не досяг ліміту - статус 200"""
        request = MockRequest()
        
        # Перший запит - має пройти
        allowed, remaining, reset_time = await rate_limiter_with_redis.check_rate_limit(request)
        
        assert allowed is True
        assert remaining == 1  # Залишилось 1 запит з 2
        assert isinstance(reset_time, int)
        assert reset_time > int(time.time())
    
    @pytest.mark.asyncio
    async def test_anonymous_user_exceeds_limit(self, rate_limiter_with_redis):
        """Тест: анонімний користувач досяг ліміту - статус 429"""
        request = MockRequest()
        
        print(f"Початковий стан Redis: {rate_limiter_with_redis.redis_client.data}")
        
        # Робимо 2 запити (ліміт для анонімних користувачів)
        result1 = await rate_limiter_with_redis.check_rate_limit(request)
        print(f"Запит 1: allowed={result1[0]}, remaining={result1[1]}")
        print(f"Стан після запиту 1: {rate_limiter_with_redis.redis_client.data}")
        
        # Додаємо невелику затримку щоб забезпечити різні часові мітки
        await asyncio.sleep(0.001)
        
        result2 = await rate_limiter_with_redis.check_rate_limit(request)
        print(f"Запит 2: allowed={result2[0]}, remaining={result2[1]}")
        print(f"Стан після запиту 2: {rate_limiter_with_redis.redis_client.data}")
        
        # Додаємо ще одну невелику затримку
        await asyncio.sleep(0.001)
        
        # Третій запит - має бути заблокований
        allowed, remaining, reset_time = await rate_limiter_with_redis.check_rate_limit(request)
        print(f"Запит 3: allowed={allowed}, remaining={remaining}")
        print(f"Фінальний стан: {rate_limiter_with_redis.redis_client.data}")
        
        assert allowed is False
        assert remaining == 0
        assert isinstance(reset_time, int)
    
    @pytest.mark.asyncio
    async def test_authenticated_user_within_limit(self, rate_limiter_with_redis, mock_user):
        """Тест: авторизований користувач не досяг ліміту - статус 200"""
        request = MockRequest()
        user_id = str(mock_user["_id"])
        
        # Перший запит - має пройти
        allowed, remaining, reset_time = await rate_limiter_with_redis.check_rate_limit(request, user_id)
        
        assert allowed is True
        assert remaining == 9  # Залишилось 9 запитів з 10
        assert isinstance(reset_time, int)
        assert reset_time > int(time.time())
    
    @pytest.mark.asyncio
    async def test_authenticated_user_exceeds_limit(self, rate_limiter_with_redis, mock_user):
        """Тест: авторизований користувач досяг ліміту - статус 429"""
        request = MockRequest()
        user_id = str(mock_user["_id"])
        
        print(f"Тестуємо з user_id: {user_id}")
        print(f"Початковий стан Redis: {rate_limiter_with_redis.redis_client.data}")
        
        # Робимо 10 запитів (ліміт для авторизованих користувачів)
        for i in range(10):
            result = await rate_limiter_with_redis.check_rate_limit(request, user_id)
            print(f"Запит {i+1}: allowed={result[0]}, remaining={result[1]}")
            # Невелика затримка між запитами
            await asyncio.sleep(0.001)
        
        print(f"Стан після 10 запитів: {rate_limiter_with_redis.redis_client.data}")
        
        # 11-й запит - має бути заблокований
        allowed, remaining, reset_time = await rate_limiter_with_redis.check_rate_limit(request, user_id)
        print(f"11-й запит: allowed={allowed}, remaining={remaining}")
        
        assert allowed is False
        assert remaining == 0
        assert isinstance(reset_time, int)
    
    @pytest.mark.asyncio
    async def test_different_users_separate_limits(self, rate_limiter_with_redis):
        """Тест: різні користувачі мають окремі ліміти"""
        request1 = MockRequest(client_host="192.168.1.1")
        request2 = MockRequest(client_host="192.168.1.2")
        
        print("Тестуємо різних користувачів:")
        print(f"Request1 IP: 192.168.1.1")
        print(f"Request2 IP: 192.168.1.2")
        
        # Перший користувач вичерпує свій ліміт (2 запити для анонімних)
        result1_1 = await rate_limiter_with_redis.check_rate_limit(request1)
        print(f"User1 запит 1: allowed={result1_1[0]}, remaining={result1_1[1]}")
        
        await asyncio.sleep(0.001)
        
        result1_2 = await rate_limiter_with_redis.check_rate_limit(request1)
        print(f"User1 запит 2: allowed={result1_2[0]}, remaining={result1_2[1]}")
        
        await asyncio.sleep(0.001)
        
        # Третій запит першого користувача має бути заблокований
        allowed1, remaining1, _ = await rate_limiter_with_redis.check_rate_limit(request1)
        print(f"User1 запит 3: allowed={allowed1}, remaining={remaining1}")
        
        # Другий користувач все ще може робити запити
        allowed2, remaining2, _ = await rate_limiter_with_redis.check_rate_limit(request2)
        print(f"User2 запит 1: allowed={allowed2}, remaining={remaining2}")
        
        print(f"Фінальний стан Redis: {rate_limiter_with_redis.redis_client.data}")
        
        assert allowed1 is False
        assert allowed2 is True
        assert remaining2 == 1
    
    @pytest.mark.asyncio
    async def test_forwarded_ip_header(self, rate_limiter_with_redis):
        """Тест: використання X-Forwarded-For заголовка"""
        request = MockRequest(
            client_host="127.0.0.1",
            headers={"X-Forwarded-For": "203.0.113.1, 198.51.100.1"}
        )
        
        identifier = rate_limiter_with_redis._get_client_identifier(request)
        assert identifier == "anon:203.0.113.1"
    
    @pytest.mark.asyncio
    async def test_real_ip_header(self, rate_limiter_with_redis):
        """Тест: використання X-Real-IP заголовка"""
        request = MockRequest(
            client_host="127.0.0.1",
            headers={"X-Real-IP": "203.0.113.1"}
        )
        
        identifier = rate_limiter_with_redis._get_client_identifier(request)
        assert identifier == "anon:203.0.113.1"


class TestRateLimiterMemory:
    """Тести для RateLimiter з in-memory сховищем"""
    
    @pytest.mark.asyncio
    async def test_anonymous_user_within_limit_memory(self, rate_limiter_memory):
        """Тест: анонімний користувач не досяг ліміту (memory) - статус 200"""
        request = MockRequest()
        
        # Перший запит - має пройти
        allowed, remaining, reset_time = await rate_limiter_memory.check_rate_limit(request)
        
        assert allowed is True
        assert remaining == 1  # Залишилось 1 запит з 2
        assert isinstance(reset_time, int)
        assert reset_time > int(time.time())
    
    @pytest.mark.asyncio
    async def test_anonymous_user_exceeds_limit_memory(self, rate_limiter_memory):
        """Тест: анонімний користувач досяг ліміту (memory) - статус 429"""
        request = MockRequest()
        
        # Робимо 2 запити (ліміт для анонімних користувачів)
        await rate_limiter_memory.check_rate_limit(request)
        await rate_limiter_memory.check_rate_limit(request)
        
        # Третій запит - має бути заблокований
        allowed, remaining, reset_time = await rate_limiter_memory.check_rate_limit(request)
        
        assert allowed is False
        assert remaining == 0
        assert isinstance(reset_time, int)
    
    @pytest.mark.asyncio
    async def test_authenticated_user_within_limit_memory(self, rate_limiter_memory, mock_user):
        """Тест: авторизований користувач не досяг ліміту (memory) - статус 200"""
        request = MockRequest()
        user_id = str(mock_user["_id"])
        
        # Перший запит - має пройти
        allowed, remaining, reset_time = await rate_limiter_memory.check_rate_limit(request, user_id)
        
        assert allowed is True
        assert remaining == 9  # Залишилось 9 запитів з 10
        assert isinstance(reset_time, int)
        assert reset_time > int(time.time())
    
    @pytest.mark.asyncio
    async def test_authenticated_user_exceeds_limit_memory(self, rate_limiter_memory, mock_user):
        """Тест: авторизований користувач досяг ліміту (memory) - статус 429"""
        request = MockRequest()
        user_id = str(mock_user["_id"])
        
        # Робимо 10 запитів (ліміт для авторизованих користувачів)
        for _ in range(10):
            await rate_limiter_memory.check_rate_limit(request, user_id)
        
        # 11-й запит - має бути заблокований
        allowed, remaining, reset_time = await rate_limiter_memory.check_rate_limit(request, user_id)
        
        assert allowed is False
        assert remaining == 0
        assert isinstance(reset_time, int)


class TestRateLimitDependencies:
    """Тести для FastAPI dependencies"""
    
    @pytest.mark.asyncio
    async def test_rate_limit_dependency_allows_request(self):
        """Тест: dependency дозволяє запит в межах ліміту"""
        request = MockRequest()
        
        # Mock rate_limiter.check_rate_limit
        with patch('app.rate_limiter.rate_limiter.check_rate_limit') as mock_check:
            mock_check.return_value = (True, 1, int(time.time()) + 60)
            
            # Не повинно піднімати виключення
            await rate_limit_dependency(request)
            
            # Перевіряємо, що заголовки були встановлені
            assert hasattr(request.state, 'rate_limit_headers')
            assert 'X-RateLimit-Limit' in request.state.rate_limit_headers
    
    @pytest.mark.asyncio
    async def test_rate_limit_dependency_blocks_request(self):
        """Тест: dependency блокує запит при перевищенні ліміту"""
        request = MockRequest()
        
        # Mock rate_limiter.check_rate_limit
        with patch('app.rate_limiter.rate_limiter.check_rate_limit') as mock_check:
            mock_check.return_value = (False, 0, int(time.time()) + 60)
            
            # Повинно піднімати HTTPException з кодом 429
            with pytest.raises(HTTPException) as exc_info:
                await rate_limit_dependency(request)
            
            assert exc_info.value.status_code == 429
            assert exc_info.value.detail == "Перевищено ліміт запитів"
            assert 'X-RateLimit-Limit' in exc_info.value.headers
            assert 'Retry-After' in exc_info.value.headers
    
    @pytest.mark.asyncio
    async def test_authenticated_rate_limit_dependency_allows_request(self, mock_user):
        """Тест: authenticated dependency дозволяє запит в межах ліміту"""
        request = MockRequest()
        
        # Mock rate_limiter.check_rate_limit
        with patch('app.rate_limiter.rate_limiter.check_rate_limit') as mock_check:
            mock_check.return_value = (True, 9, int(time.time()) + 60)
            
            # Не повинно піднімати виключення
            await authenticated_rate_limit_dependency(request, mock_user)
            
            # Перевіряємо, що заголовки були встановлені
            assert hasattr(request.state, 'rate_limit_headers')
            assert 'X-RateLimit-Limit' in request.state.rate_limit_headers
    
    @pytest.mark.asyncio
    async def test_authenticated_rate_limit_dependency_blocks_request(self, mock_user):
        """Тест: authenticated dependency блокує запит при перевищенні ліміту"""
        request = MockRequest()
        
        # Mock rate_limiter.check_rate_limit
        with patch('app.rate_limiter.rate_limiter.check_rate_limit') as mock_check:
            mock_check.return_value = (False, 0, int(time.time()) + 60)
            
            # Повинно піднімати HTTPException з кодом 429
            with pytest.raises(HTTPException) as exc_info:
                await authenticated_rate_limit_dependency(request, mock_user)
            
            assert exc_info.value.status_code == 429
            assert exc_info.value.detail == "Перевищено ліміт запитів"
            assert 'X-RateLimit-Limit' in exc_info.value.headers
            assert 'Retry-After' in exc_info.value.headers


class TestRateLimiterEdgeCases:
    """Тести для граничних випадків"""
    
    @pytest.mark.asyncio
    async def test_redis_connection_error(self):
        """Тест: обробка помилки з'єднання з Redis"""
        mock_redis = Mock()
        mock_redis.ping.side_effect = Exception("Connection failed")
        
        rate_limiter = RateLimiter(redis_client=mock_redis)
        request = MockRequest()
        
        # При помилці Redis повинен дозволити запит
        allowed, remaining, reset_time = await rate_limiter.check_rate_limit(request)
        
        assert allowed is True
        assert remaining > 0
    
    def test_get_client_identifier_authenticated(self, rate_limiter_with_redis, mock_user):
        """Тест: ідентифікатор для авторизованого користувача"""
        request = MockRequest()
        user_id = str(mock_user["_id"])
        
        identifier = rate_limiter_with_redis._get_client_identifier(request, user_id)
        
        assert identifier == f"user:{user_id}"
    
    def test_get_client_identifier_anonymous(self, rate_limiter_with_redis):
        """Тест: ідентифікатор для анонімного користувача"""
        request = MockRequest(client_host="192.168.1.100")
        
        identifier = rate_limiter_with_redis._get_client_identifier(request)
        
        assert identifier == "anon:192.168.1.100"
    
    def test_get_limit_for_user(self, rate_limiter_with_redis, mock_user):
        """Тест: отримання ліміту для різних типів користувачів"""
        user_id = str(mock_user["_id"])
        
        # Ліміт для авторизованого користувача
        auth_limit = rate_limiter_with_redis._get_limit_for_user(user_id)
        assert auth_limit == 10
        
        # Ліміт для анонімного користувача
        anon_limit = rate_limiter_with_redis._get_limit_for_user(None)
        assert anon_limit == 2