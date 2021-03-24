from rq.decorators import job

from ..config import config
from ..adapters import mailer
from . import DEFAULT_JOB_OPTIONS


@job("default", **DEFAULT_JOB_OPTIONS)
def send_email(to, subject, **kwargs):
    kwargs.setdefault("from_email", config.mailer.default_from)
    mailer.send(to=to, subject=subject, **kwargs)
