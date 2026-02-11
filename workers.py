import multiprocessing
from rq import Worker
from app.core.queue import redis_conn, task_queue
from app.core.config import settings


def start_worker(worker_num: int):
    worker = Worker([task_queue], connection=redis_conn, name=f"worker-{worker_num}")
    print(f"Worker {worker_num} started... Listening for tasks...")
    worker.work()


if __name__ == "__main__":
    num_workers = settings.NUM_WORKERS
    print(f"Starting {num_workers} RQ worker(s)...")
    
    if num_workers == 1:
        start_worker(1)
    else:
        processes = []
        for i in range(1, num_workers + 1):
            process = multiprocessing.Process(target=start_worker, args=(i,))
            process.start()
            processes.append(process)
        
        for process in processes:
            process.join()
