from mailshake import AmazonSESMailer, ToConsoleMailer

from ..config import config


__all__ = ("mailer", )

if config.debug:
    mailer = ToConsoleMailer()
else:
    mailer = AmazonSESMailer(
        config.mailer.aws_access_key_id,
        config.mailer.aws_secret_access_key,
        region_name=config.mailer.region_name,
    )
