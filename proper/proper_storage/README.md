
class Post(db.Model):
    header = attachment("header", ...)
    images = many_attachments("images", ...)
    ...


class attachment:
    many = False

    def __init__(self, ...):
        ...

    def attach(self, ...):
        ...

    def remove(self, ...):
        ...

    def __iter__(self):
        items = self.load()
        return items.__iter__()


class many_attachments(attachment):
    many = True

