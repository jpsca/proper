import multiprocessing

from rq import Connection, Worker

from .adapters import QUEUES, redis


NUM_WORKERS = 3


def run():
    with Connection(redis):
        workers = []
        for _ in range(NUM_WORKERS):
            worker = Worker(QUEUES)
            p = multiprocessing.Process(
                target=worker.work, kwargs={"with_scheduler": True}
            )
            workers.append(p)
            p.start()
