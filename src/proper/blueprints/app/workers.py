from proper.queue.consumer import Consumer

from app.main import app


def run_workers():
    if app.queue is None:
        raise RuntimeError("Queue not initialized.")

    config = app.config.get("QUEUE_CONSUMER", {}).copy()
    config["queue"] = app.queue
    consumer = Consumer(**config)
    consumer.run()


if __name__ == "__main__":
    run_workers()
