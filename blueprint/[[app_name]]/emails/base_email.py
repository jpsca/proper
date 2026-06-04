from proper.emails import EmailMessage

from ..tasks import send_email_task


class BaseEmail(EmailMessage):
    def send_later(self, **options):
        self.update(**options)
        send_email_task(message=self.serialize())
