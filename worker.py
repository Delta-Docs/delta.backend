from rq import Worker
from app.core.queue import redis_conn, task_queue

if __name__ == "__main__":
    worker = Worker([task_queue], connection=redis_conn)
    print(f"Redis Queue worker started... Listening for tasks...")
    worker.work()
