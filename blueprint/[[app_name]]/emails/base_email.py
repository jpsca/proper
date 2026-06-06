from proper.emails import EmailMessage

from ..tasks import send_email_task


class BaseEmail(EmailMessage):
    def send_later(self, *, via=None, **options):
        """Queue the email to be sent by a worker.

        Pass `via` to route the message through a specific mailer from
        `MAILERS` (by name). Defaults to the configured default mailer.
        """
        self.update(**options)
        send_email_task(message=self.serialize(), via=via)
