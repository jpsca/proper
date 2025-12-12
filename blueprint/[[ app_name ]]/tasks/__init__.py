from proper.mail import EmailMessageDict
from ..main import app


@app.queue.task()
def send_email_task(message: EmailMessageDict):
    app.mailer.send_email(message)
