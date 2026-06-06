from huey.consumer import Consumer

from [[app_name]].main import app


def get_config():
    return app.config.get("QUEUE_CONSUMER", {}).copy()


def run_consumer(config):
    if app.queue is None:
        raise RuntimeError("Queue not initialized.")
    print("Starting background workers...")
    consumer = Consumer(app.queue, **config)
    consumer.run()


if __name__ == "__main__":
    config = get_config()
    run_consumer(config)
