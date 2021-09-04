from mailshake import ToConsoleMailer
from proper import App

from .config import config


app = App("[[ app_name ]]", config=config)

mailer = ToConsoleMailer()


def send_email(to, subject, **kw):
    kw.setdefault("from_email", config.mailer_default_from)
    mailer.send(to=to, subject=subject, **kw)
