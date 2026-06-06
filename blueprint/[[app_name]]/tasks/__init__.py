from proper.emails import EmailMessageDict

from ..main import app


@app.queue.task()
def send_email_task(message: EmailMessageDict, via: str | None = None):
    mailer = app.mailers[via] if via else app.mailer
    mailer.send_now(message)
