from proper.mail import ToConsoleMailer

from app.main import config


mailer = ToConsoleMailer()


def send_email(to, subject, **kw):
    kw.setdefault("from_email", config.MAILER_DEFAULT_FROM)
    mailer.send(to=to, subject=subject, **kw)
