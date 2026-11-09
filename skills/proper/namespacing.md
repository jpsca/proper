---
title: Namespacing Controllers
description: A separate controller, form and views for the same resource under a URL prefix (an admin interface): generator, scoped router, `Admin:Post.index` route names
last_verified: 2026-11-08
sources:
  - src/proper/generators
  - src/proper/router
---

# Namespacing Controllers

Use a namespace when the same resource needs a second controller, for example an admin interface next to the public one. The scoped router itself (`router.scope()`) is in [routing.md](routing.md#scoped-routes).

## Namespacing

When you need a separate controller for the same resource — for example, an admin interface alongside a public one — namespace the controller under a subfolder. This gives the namespaced controller its own routes, forms, and views without conflicting with the public version.

**ALWAYS** generate a namespaced controller using the commands:

- `proper g resource NAME --namespace=NAMESPACE`, if you need to add a model as well; or
- `proper g controller NAME --namespace=NAMESPACE` for just the controller, form, and views.


### What the generator creates

For `proper g controller Post --namespace=admin`:

```
myapp/
├── controllers/
│   ├── __init__.py               # Modified: adds `from .admin import post_controller`
│   └── admin/
│       ├── __init__.py
│       └── post_controller.py
├── forms/
│   └── admin/
│       ├── __init__.py
│       └── post.py
└── views/
    └── admin/
        └── post/
            ├── index.jx
            ├── show.jx
            ├── new.jx
            ├── edit.jx
            └── form.jx
```


### The scoped router

The generator adds a scoped router to `router.py`:

```python {title="myapp/router.py"}
admin_router = router.scope("admin")
```

The namespaced controller uses this scoped router instead of the root one. All routes are automatically prefixed with `/admin`:

```python {title="myapp/controllers/admin/post_controller.py"}
from proper.errors import NotFound

from myapp.forms.admin.post import PostForm
from myapp.models import Post
from myapp.router import admin_router
from ..app_controller import AppController


@admin_router.resource("posts")
class PostController(AppController):

    def index(self):
        self.posts = Post.select()

    def show(self):
        self.load_post()
        if not self.post:
            raise NotFound

    def new(self):
        self.form = PostForm(self.params)

    def create(self):
        self.form = PostForm(self.params)
        if self.form.is_invalid:
            return self.redo()

        self.form.save()
        self.response.redirect_to("Admin:Post.index", flash="Post was created")

    # ... other actions ...

    # Private

    def load_post(self):
        post_id = self.params.get("post_id", "")
        self.post = Post.find(int(post_id)) if post_id.isdigit() else None
```


### Namespaced route names

Route names are prefixed with the namespace in PascalCase, separated by a colon. The prefix comes from the controller's module path under `controllers/`, not from the scoped router: a controller in `controllers/admin/` gets `Admin:` even on the root router, one in `controllers/admin/reports/` gets `Admin:Reports:`, and one in `controllers/` mounted on `admin_router` gets no prefix:

| Method | Path | Named route |
|--------|------|-------------|
| GET | `/admin/posts` | `Admin:Post.index` |
| GET | `/admin/posts/new` | `Admin:Post.new` |
| POST | `/admin/posts` | `Admin:Post.create` |
| GET | `/admin/posts/:post_id` | `Admin:Post.show` |
| GET | `/admin/posts/:post_id/edit` | `Admin:Post.edit` |
| PATCH | `/admin/posts/:post_id` | `Admin:Post.update` |
| DELETE | `/admin/posts/:post_id` | `Admin:Post.delete` |

Use these prefixed names for `url_for` and `redirect_to`:

```python
app.url_for("Admin:Post.index")               # /admin/posts
app.url_for("Admin:Post.show", post)           # /admin/posts/42
self.response.redirect_to("Admin:Post.show", post, flash="Done")
```

In templates:

```html+jinja
<a href="{{ url_for('Admin:Post.index') }}">Manage Posts</a>
```


### The model is shared

Namespaced controllers import the model from the same `models/` directory as all other controllers. The namespace only affects controllers, forms, and views — not models. This means both the public `PostController` and the admin `PostController` operate on the same `Post` model.


### Imports

The namespaced controller is imported through the root `controllers/__init__.py`:

```python {title="myapp/controllers/__init__.py"}
from . import public_controller  # noqa
from . import post_controller  # noqa
from .admin import post_controller  # noqa
```
