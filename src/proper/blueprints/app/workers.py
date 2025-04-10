from proper.queue.consumer import Consumer

from app.main import app


def get_config():
    if app.queue is None:
        raise RuntimeError("Queue not initialized.")

    config = app.config.get("QUEUE_CONSUMER", {}).copy()
    config["queue"] = app.queue
    return config


def run_consumer(config):
    print("Starting background workers...")
    consumer = Consumer(**config)
    consumer.run()


def run_consumer_proc():
    import multiprocessing
    import sys

    if sys.platform == "darwin":
        try:
            multiprocessing.set_start_method("fork")
        except RuntimeError:
            pass

    config = get_config()
    consumer_proc = multiprocessing.Process(
        target=run_consumer,
        kwargs={"config": config},
    )
    consumer_proc.start()


if __name__ == "__main__":
    config = get_config()
    run_consumer(config)
