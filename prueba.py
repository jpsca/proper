
class BaseAttachment:
    name = None
    obj = None

    def __repr__(self):
        cls = self.__class__.__name__
        if self.obj is None:
           return f"<{cls}>"
        model_id = getattr(self.obj, "id", None)
        model = self.obj.__class__.__name__
        return f"<{cls} {model}#{model_id}.{self.name}>"


class Attachment(BaseAttachment):
    pass

class AttachmentList(BaseAttachment):
    pass


def attach_one():
    return Attachment()


def attach_many():
    return AttachmentList()


class Attachable:
    def __new__(cls, *args, **kw):
        obj = super().__new__(cls, *args, **kw)
        for key, value in cls.__dict__.items():
            if isinstance(value, BaseAttachment):
                value.name = key
                value.obj = obj
        return obj


class User(Attachable):
    avatar = attach_one()

    def __init__(self):
        self.id = 2


class Post(Attachable):
    images = attach_many()

    def __init__(self):
        self.id = 1

print(User.avatar)
user = User()
print(user.avatar)

print(Post.images)
post = Post()
print(post.images)
