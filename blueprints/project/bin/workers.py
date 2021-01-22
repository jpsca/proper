#!/usr/bin/env python
import multiprocessing

from rq import Connection, Worker

from [[ name ]].adapters import redis, QUEUES


NUM_WORKERS = 3


def run_workers():
    with Connection(redis):
        workers = []
        for i in range(NUM_WORKERS):
            worker = Worker(QUEUES)
            p = multiprocessing.Process(
                target=worker.work, kwargs={"with_scheduler": True}
            )
            workers.append(p)
            p.start()


if __name__ == "__main__":
    run_workers()
