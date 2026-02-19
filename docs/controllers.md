# Controllers

A controller is responsible for processing the request and generating the appropriate output.
They are defined in individual files (one for each class) inside the `myapp/controllers/` folder (or a subfolder).
It is customary that:

* Their names are **singular** ("PhotoController" instead of "PhotosController")
* Their names are suffixed with "Controller"
* Their files are named with the same name in snake-case, including the "controller" suffix (e.g.: "photo_controller.py")

For convenience, they should all inherit from the `AppController` class, located at `myapp/controllers/app_controller.py`. `AppController` is a class that inherits from `proper.Controller`.


## The Core Principle: Everything is CRUD

The `router.resource` class decorator is the most common method to mount a controller in the right URLs.
This decorator maps the `index`, `new`, `create`, `show`, `edit`, `update`, and `delete` methods of the controller class (if they exist) to CRUD actions with the same name.

```python {title="myapp/controllers/card_controller.py"}
from ..router import router
from .app_controller import AppController

@router.resource("cards")
class CardController(AppController):

    # GET /cards
    def index(self):
        """A list of all cards"""

    # GET /cards/new
    def new(self):
        """Show a form for a new card"""

    # POST /cards
    def create(self):
        """Create a card"""

    # GET /cards/:card_id
    def show(self):
        """Show a specific card"""

    # GET /cards/:card_id/edit
    def edit(self):
        """Page for editing a card"""

    # PATCH /cards/:card_id
    def update(self):
        """Update a card"""

    # DELETE /cards/:card_id
    def delete(self):
        """Delete a card"""

```

The auto-generated URLs in this example are:

| HTTP     | PATH                 | ACTION   | USED FOR
| -------- | -------------------- | -------- | -------------------------------
| GET      | /cards               | index    | a list of all cards
| GET      | /cards/new           | new      | form for creating a new card
| POST     | /cards               | create   | create a new card
| GET      | /cards/:card_id      | show     | show a specific card
| GET      | /cards/:card_id/edit | edit     | form for editing a specific card
| PATCH    | /cards/:card_id      | update   | update a specific card
| PUT      | /cards/:card_id      | update   | replace a specific card
| DELETE   | /cards/:card_id      | delete   | delete a specific card


### ID parameter

The `:card_id` parameter is auto-generated from the singular of the snake-cased controller name (after removing the "Controller" suffix).

Examples:

* `CardController` -> `card_id`
* `UserPhotoController` -> `user_photo_id`

It can also be manually specified with the `pk` argument. For example, `router.resource("cards", pk="object")` will use the `object_id` parameter (instead of `card_id`) in their URLs.

The ID parameter can be also disabled by using `pk=None`. This is desirable for resources that clients always look up without referencing an ID.

Example: `@router.resource("profile", pk=None)` will generate the following URLs:

| HTTP     | PATH                | ACTION   | USED FOR
| -------- | ------------------- | -------- | -------------------------------
| GET      | /profile/new        | new      | form for creating the profile
| POST     | /profile            | create   | create the profile
| GET      | /profile            | show     | show the profile
| GET      | /profile/edit       | edit     | form for editing the profile
| PATCH    | /profile            | update   | update the profile
| PUT      | /profile            | update   | replace the profile
| DELETE   | /profile            | delete   | delete the profile

Note that the `index` method is ignored when the ID parameter is disabled.


## Manually defined URLs

It is also possible to add routes for individual methods using the decorators `router.get`, `router.post`, `router.patch`, and `router.delete`, for example:

```python {title="myapp/controllers/public_controller.py"}
from ..router import router
from .app_controller import AppController

class PublicController(AppController):
    @router.get("")
    def index(self):
        pass

```

This should be used only for exceptional cases, such as the home page.


## Parameters

Data sent by the incoming request is available in your controller in the params hash. There are two types of parameter data:

* Query string parameters which are sent as part of the URL (for example, after the "?" in "http://example.com/accounts?filter=free").
* POST parameters which are submitted from an HTML form.

Proper does not make a distinction between query string parameters and POST parameters; both are collected and available in the `params` attribute in your controller. For example:

```python
from proper.status import unprocessable
from ..forms.card import CardForm
from ..router import router
from .app_controller import AppController

@router.resource("clients")
class ClientController(AppController):

    # This action receives query string parameters from an HTTP GET request
    # at the URL "/clients?status=activated"
    def index(self):
        if self.params.get("status") == "activated":
        self.clients = Client.get_activated()
    else:
        self.clients = Client.get_inactivated()

  # This action receives parameters from a POST request to "/clients" URL with  form data in the request body.
  # The `CardForm` is a concept we will explore later.
  def create(self):
        self.form = CardForm(self.params)
        if self.form.is_invalid:
            return self.render("new", status=unprocessable)

        card = self.form.save()
        self.response.redirect_to(
            "Card.show",
            card_id=card.id,
            flash="Card was created",
        )

```

TODO: How :card_id becomes self.params["card_id"] isn't explicit


## The Request and Response Objects

### The request Object

TODO

### The response Object

TODO


## Rendering Responses

### HTML Templates

TODO

- `self.render("template.jinja")` — render a Jinja template
- `self.render("template.jinja", status=404)` — with status code
- Template lookup conventions

### Other response types

TODO

- Returning JSON from actions
- Setting content-type

### Status Codes and Errors

TODO

- Common status codes (200, 201, 422, etc.)
- `raise NotFound` — 404
- `raise Forbidden` — 403
- `raise BadRequest` — 400
- Custom error pages

### Headers

TODO

### Redirects

TODO

### Cookies

TODO


## Controller Callbacks

Controller callbacks are methods that are defined to automatically run before and/or after a controller action. A controller callback method can be defined in a given controller or in a parent class, like the `AppController`. Since all controllers inherit from `AppController`, callbacks defined here will run on every controller in your application.

### `before` callback

Callback methods registered via `before` run before a controller action. They may halt the request cycle if they set a body or a redirect.
A common use case for `before` is ensuring that a user is logged in:

```python
from proper import Controller

class AppController(Controller):
    before = {"do": "require_login"}

    def require_login(self):
        if not current.auth_session:
            self.response.redirect_to("Session.new")
```

The method redirects to the login form if the user is not already logged in. When a `before` callback renders or redirects (like in the example above), the original controller action is not run. If there are additional callbacks registered to run, they are also cancelled and not run.

The `"do"` argument must be a name or a list of names of methods defined in the class or in one of its parent classes.

Another common use is to load an object from the database:

```python
from .app_controller import AppController

class CardController(AppController):
    before = {"do": "set_card", "only": ["show", "edit", "update", "delete"]}

    def set_card(self):
        card_id = self.params.get("card_id")
        self.card = Card.get_or_none(card_id)
        if not self.card:
            raise NotFound

```

In this example, there is no point of trying to load a card in the "index" or "new" actions, there is not even a "card_id" parameter available.
The `only` option run the callback only for the listed actions; there is also an `ignore` option which works the other way.

### `after` callback

You can also define action callbacks to run after a controller action has been executed with the `after` callback.

The `after` callbacks are similar to the `before` callbacks, but because the controller action has already been run they have access to the response data that's about to be sent to the client.

/// warning |
`after` callbacks are executed only after a successful controller action, and not if an exception is raised in the request cycle.
///


### Multiple callbacks

Both `before` and `after` callbacks can be written as list of dictionaries, to have many callbacks with different options in the same controller. The callbacks will be executed in order.

```python
from .app_controller import AppController

class CardController(AppController):
    before = [
        {"do": "set_card"},
        {"do": "ensure_editor_access", "only": ["edit", "update", "delete"]}
    ]

    ...
```

### Inheritance

The `before` and `after` callbacks are always inherited and are not obscured by new declarations. Invoking an action in a controller with `before` callbacks defined, will first call any `before` callbacks defined in its parent classes, and then the ones defined in the controller class itself.


## Controller Concerns

A controller concern is simply a mixin class that defines callbacks and possibly other methods, so they can be easily re-used in several controllers by inheriting from them. The convention is to declare them in the `myapp/controllers/concerns/`, one per file. Example:

```python {title="myapp/controllers/concerns/security_headers.py"}
from proper import Concern

class SecurityHeaders(Concern):
    after = {"do": "set_security_headers"}

    def set_security_headers(self):
        ...

```

Concern classes must inherit from `proper.Concern`.


## Adding more actions

When something doesn't fit the CRUD actions in a controller, create a new controller instead of adding new methods.

**BAD:** Custom actions on an existing controller

```python {title="myapp/controllers/card_controller.py"}
from ..router import router
from .app_controller import AppController

@router.resource("cards")
class CardController(AppController):

    @router.patch("cards/:card_id/close")
    def close(self):
        """Close card"""

    @router.patch("/cards/:card_id/reopen")
    def reopen(self):
        """Reopen card"""

    @router.patch("/cards/:card_id/not-now")
    def not_now(self):
        """Postpone card"""

    ...
```

**GOOD:** New controllers for each state change

```python {title="myapp/controllers/card/closure_controller.py"}
from ...router import router
from ..concerns.card_scoped import CardScoped

@router.resource("cards/:card_id/closure", pk=None)
class ClosureController(CardScoped, AppController):

    # POST /cards/:card_id/closure
    def create(self):
        """Close a card"""

    # DELETE /cards/:card_id/closure
    def delete(self):
        """Reopen a card"""

```

```python {title="myapp/controllers/card/not_now_controller.py"}
from ...router import router
from ..concerns.card_scoped import CardScoped

@router.resource("cards/:card_id/not-now", pk=None)
class NotNowController(CardScoped, AppController):

    # POST /cards/:card_id/not-now
    def create(self):
        """Postpone a card"""

```

In these cases:

1. The card is loaded using a shared concern:

```python {title="myapp/controllers/concerns/card_scoped.py"}
from proper import Concern
from proper.errors import NotFound
from ...models import Card

class CardScoped(Concern):
    before = {"do": "set_card"}

    def set_card(self):
        card_id = self.params.get("card_id")
        if card_id:
            self.card = Card.get_or_none(card_id)
            if self.request.matched_action != "delete" and not self.card:
                raise NotFound

```

2. The new controllers do not have their own IDs, so they are mounted at "cards/:card_id/" and use the argument `pk=None`.

3. The original controller file (`card_controller.py`) and the new ones (`closure_controller.py` and `not_now_controller.py`) are moved into a subfolder `myapp/controllers/card/`.
