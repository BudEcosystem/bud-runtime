from budapp.shared.redis_service import RedisService
import asyncio
from threading import Thread

# test event loop
print("Event loop test started")
asyncio.run(RedisService().set("test", "test"))
asyncio.run(RedisService().set("test1", "test"))
asyncio.run(RedisService().get("test"))
asyncio.run(RedisService().keys("test*"))
asyncio.run(RedisService().delete("test", "test1"))
print("RedisService event loop test completed")

# test async function
async def async_main():
    """Async function to test RedisService."""
    print("Async function started")
    redis_service = RedisService()
    await redis_service.set("test", "test")
    await redis_service.set("test1", "test")
    keys = await redis_service.keys("test*")
    await redis_service.delete(*keys)
    print("Async function completed")
asyncio.run(async_main())
print("RedisService async function test completed")

def thread_main():
    """Thread function to test RedisService."""
    print("Thread function started")
    asyncio.run(RedisService().set("test", "test"))
    asyncio.run(RedisService().set("test1", "test"))
    print("Thread function completed")

# Thread safe test
process_1 = Thread(target=thread_main)
print("Thread 1 started")
process_2 = Thread(target=thread_main)
print("Thread 2 started")
process_1.start()
process_1.join()
process_2.start()
process_2.join()
print("RedisService thread safe test completed")

# python -m tests.test_redis
