from threading import Lock


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
        with cls._lock:
            if cls not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
        return cls._instances[cls]
