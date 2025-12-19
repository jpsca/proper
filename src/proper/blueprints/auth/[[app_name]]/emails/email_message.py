import proper

from ..tasks import send_now_task


class EmailMessage(proper.EmailMessage):
    def send_later(self, **options):
        self.update(**options)
        send_now_task(message=self.serialize())
