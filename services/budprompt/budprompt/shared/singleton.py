import time
from threading import Lock

from budmicroframe.commons import logging

logger = logging.get_logger(__name__)


class SingletonMeta(type):
    """This is a thread-safe implementation of Singleton.

    Ref: https://refactoring.guru/design-patterns/singleton/python/example#example-1
    """

    _instances = {}
    _lock: Lock = Lock()
    """We now have a lock object that will be used to synchronize threads during
    first access to the Singleton.
    """

    def __call__(cls, *args, **kwargs):
        """Possible changes to the value of the `__init__` argument do not affect the returned instance."""
        # [CP-LOCK] Performance checkpoint - Singleton lock acquisition
        lock_start = time.time()
        with cls._lock:
            lock_wait = (time.time() - lock_start) * 1000
            if lock_wait > 1.0:  # Only log if wait time > 1ms (indicates contention)
                logger.info(f"[CP-LOCK] Lock acquired | class={cls.__name__} | wait={lock_wait:.1f}ms")
            if cls not in cls._instances:
                logger.info(f"[CP-LOCK] Creating new singleton instance | class={cls.__name__}")
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
        return cls._instances[cls]
