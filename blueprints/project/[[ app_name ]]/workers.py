import multiprocessing

from rq import Connection, Worker

from .adapters import redis, QUEUES


NUM_WORKERS = 3


def run():
    with Connection(redis):
        workers = []
        for i in range(NUM_WORKERS):
            worker = Worker(QUEUES)
            p = multiprocessing.Process(
                target=worker.work, kwargs={"with_scheduler": True}
            )
            workers.append(p)
            p.start()
