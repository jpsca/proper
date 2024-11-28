from .mailers.base import BaseMailer  # noqa
from .mailers.console import ToConsoleMailer  # noqa
from .mailers.memory import ToMemoryMailer  # noqa
from .mailers.smtp import SMTPMailer  # noqa
from .mailers.amazon_ses import AmazonSESMailer, AmazonSES2Mailer  # noqa
from .message import EmailMessage  # noqa


Mailer = ToConsoleMailer
