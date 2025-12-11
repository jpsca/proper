from proper.mail import ToConsoleEmailSender

from ..main import config


mailer = ToConsoleEmailSender()


def send_email(to, subject, **kw):
    kw.setdefault("from_email", config.MAILER_DEFAULT_FROM)
    mailer.send_email(to=to, subject=subject, **kw)
