from huey.consumer import Consumer
from app.main import app


def get_config():
    return app.config.get("QUEUE_CONSUMER", {}).copy()


def run_consumer(config):
    if app.queue is None:
        raise RuntimeError("Queue not initialized.")
    print("Starting background workers...")
    consumer = Consumer(app.queue, **options)
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
