from mailshake import ToConsoleMailer

from ..app import config


mailer = ToConsoleMailer()

def send_email(to, subject, **kw):
    kw.setdefault("from_email", config.mailer.default_from)
    mailer.send(to=to, subject=subject, **kw)
