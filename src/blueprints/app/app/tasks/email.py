from app.main import app


@app.queue.task()
def send_email(**data):
    app.mailer.send(**data)
