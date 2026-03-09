import sys
import redis
from app.core.config import settings

# Shared Redis connection
redis_conn = redis.from_url(settings.REDIS_URL)

if sys.platform == "win32":
    class MockQueue:
        def __init__(self, *args, **kwargs):
            pass
        def enqueue(self, *args, **kwargs):
            print("WARNING: Background jobs (RQ) are skipped natively on Windows.", file=sys.stderr)
            return None
    task_queue = MockQueue()
else:
    from rq import Queue
    task_queue = Queue(connection=redis_conn)
