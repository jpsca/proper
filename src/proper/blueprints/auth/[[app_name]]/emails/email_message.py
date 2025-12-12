import proper

from ..tasks import send_email_task


class EmailMessage(proper.EmailMessage):
    def send_later(self, **options):
        self.update(**options)
        send_email_task(message=self.serialize())
