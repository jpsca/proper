from proper.emails import EmailMessageDict
from ..main import app


@app.queue.task()
def send_now_task(message: EmailMessageDict):
    app.mailer.send_now(message)
