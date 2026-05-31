---
title: Sending Emails
description: |
  How to compose and deliver email in Proper. Covers the email class, templates, attachments, foreground and background sending, the bundled mailer backends, per-environment configuration, and testing.
number_headers: true
---

# Sending Emails

Most apps send mail eventually: a confirmation when someone signs up, a password reset link, a receipt, a weekly digest. The mechanics are unglamorous - compose a message, hand it to something that talks SMTP (or an HTTP API), hope it lands in the inbox - but the surrounding decisions matter: where the email *lives* in your code, how its body is rendered, whether sending blocks the request or runs in the background, and what happens to it in development and tests.

This guide covers all of that in Proper.

After reading this guide, you will know:

- How an email is shaped in a Proper app - the class, the template, the layout, and the controller call that sends it.
- When to send through `send()` vs. `send_later()`, and which mailer backend belongs in development, tests, and production.
- How to test email-sending code without ever touching SMTP.

---

## The shape of email in Proper

Before any API reference, it's worth walking through one real email end-to-end. The auth addon ships with a password-reset flow that exercises every part of the system: a class, a template, a layout, a controller, and a background task. Each section after this one decomposes one piece of it.

Here is the layout in a freshly generated app with the auth addon installed:

```
myapp/
├── emails/
│   ├── __init__.py
│   ├── base_email.py              # BaseEmail adds send_later()
│   └── password_reset_email.py    # one class per email
├── views/
│   ├── emails/
│   │   └── password_reset.jx      # the HTML template
│   └── layouts/
│       └── email.jx               # the layout every email wraps in
├── tasks/
│   └── __init__.py                # ships with send_email_task
└── config/
    └── main.py                    # MAILER and MAILER_DEFAULT_OPTIONS
```

### The class

`PasswordResetEmail` lives in `emails/password_reset_email.py`. It carries the data a single message needs - in this case, two URLs derived from the user - and not much else:

```python
# emails/password_reset_email.py
from ..main import app
from .base_email import BaseEmail


class PasswordResetEmail(BaseEmail):
    subject = "Reset your password"

    def __init__(self, user, **kwargs):
        super().__init__(**kwargs)
        token = user.generate_token_for("password_reset")
        self.validate_url = app.url_for("PasswordReset.edit", token=token, _full=True)
        self.reset_url = app.url_for("PasswordReset.new", _full=True)
```

A few things to notice:

- `subject` is a **class attribute**. Anything you set at class level becomes the default for every instance; you can still override it per-call.
- The constructor receives the domain object (`user`), not just primitives. Pulling `user.email` and friends inside the email class - rather than at the call site - keeps the controller short and the email class self-contained.
- Instance attributes like `self.validate_url` aren't required parameters of `EmailMessage`. They're free-form, and the template will see them as variables - we'll get to template auto-discovery in [Templates](#templates).
- `_full=True` on `app.url_for()` produces an absolute URL with scheme and host. Emails travel outside your app, so a relative URL is useless. Always pass `_full=True`.

### The template

The email body comes from `views/emails/password_reset.jx`:

```html+jinja
{#import "layouts/email.jx" as Layout #}

{#def subject, validate_url, reset_url #}

<Layout>
  <p>
    I heard that you lost your password. Sorry about that!
  </p>
  <p>
    But don't worry! You can use the following link to reset your password:
    <a href="{{ validate_url }}">{{ validate_url }}</a>.
  </p>
  <p>
    If you don't use this link within 3 hours, it will expire.
    To get a new password reset link, visit
    <a href="{{ reset_url }}">{{ reset_url }}</a>.
  </p>
</Layout>
```

`{#def subject, validate_url, reset_url #}` declares the variables the template expects. Every instance attribute on the email class is passed in as a template variable, so `self.validate_url` becomes `{{ validate_url }}`.

### The layout

`views/layouts/email.jx` is a thin HTML document that every email wraps in. The generated one is intentionally minimal:

```html+jinja
{#def lang='en' #}

<!DOCTYPE html>
<html lang="{{ lang }}">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style>
      /* Email styles need to be inline */
    </style>
  </head>
  <body>
    {{ content }}
  </body>
</html>
```

That empty `<style>` block with the inline-only comment is honest: most email clients strip or ignore `<style>` tags. The pragmatic answer today is to write inline `style="..."` attributes on the elements that need them. A CSS-inlining pass at render time is a likely future addition - see [Where this could grow](#where-this-could-grow).

### The controller call

A controller sends the email in two lines:

```python
# controllers/password_reset_controller.py
from ..emails.password_reset_email import PasswordResetEmail


def create(self):
    self.form = PasswordResetForm(self.params)
    if self.form.is_invalid:
        return self.redo()

    user = User.get_by_login(self.form.save()["login"])
    PasswordResetEmail(user).send_later(to=user.email)
    self.response.redirect_to("PasswordReset.show", token="sent")
```

`PasswordResetEmail(user)` builds the message; `.send_later(to=user.email)` hands it to the background queue and returns immediately. The user sees the redirect right away, and a worker picks up the actual SMTP conversation seconds later. The request didn't have to wait for it.

That's the whole loop. The rest of this guide is the reference for each piece.

---

## Generating an email

The `proper g email` generator stubs the three files that go together. Pass a PascalCase name, singular, **without** an `_email` suffix:

```bash
$ proper g email Welcome
```

That creates `emails/welcome_email.py` and `views/emails/welcome.jx`.

The Python file gets the `_email` suffix; the template does not. That keeps the `emails/` folder readable as a list of nouns (`welcome_email.py`, `password_reset_email.py`, `invoice_email.py`) while the templates stay short (`welcome.jx`). The template discovery rule, covered in [Templates](#templates), bridges the two.

The generated class is a skeleton:

```python
# emails/welcome_email.py
from .base_email import BaseEmail


class WelcomeEmail(BaseEmail):
    subject = ""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
```

Fill in `subject`, accept whatever domain objects the email needs, and stash anything the template should see as `self.something`. Then write the template at `views/emails/welcome.jx`.

---

## The email class

Every email in your app is a subclass of `BaseEmail`, which is itself a thin subclass of `proper.EmailMessage`. The hierarchy:

- `EmailMessage` (from the framework) - composes a message, renders templates, sends through the configured mailer.
- `BaseEmail` (in *your* app, at `emails/base_email.py`) - adds `send_later()` so you can hand the message off to the background queue. You can edit this class.
- Your specific emails (`WelcomeEmail`, `PasswordResetEmail`, ...) - one per kind of message.

For one-off messages you don't need a class at all - `EmailMessage` is usable directly:

```python
from proper import EmailMessage

EmailMessage(
    subject="Welcome!",
    body="Thanks for signing up.",
    to="alice@example.com",
).send()
```

But the class-per-email pattern is the convention, because emails almost always end up needing some setup (build URLs, look up records, decide a subject), and the class is the natural place for it.

### Constructor arguments

All arguments to `EmailMessage` are keyword-only:

```python
EmailMessage(
    from_email="hello@example.com",
    subject="Welcome!",
    body="Thanks for signing up.",
    to="alice@example.com",
    cc=["manager@example.com"],
    bcc=["audit@example.com"],
    reply_to=["support@example.com"],
    headers={"X-Campaign": "spring-launch"},
)
```

`to`, `cc`, `bcc`, and `reply_to` each accept a single string or a list of strings - whichever is more convenient. Pass a list when you mean it: a single `to=` with multiple addresses joined by commas is *not* the same thing.

### Class-level defaults

Any attribute you set at class level becomes the default for every instance. `subject` is the most common, but `from_email`, `content_subtype`, and `charset` work the same way:

```python
class NewsletterEmail(BaseEmail):
    subject = "Your weekly digest"
    from_email = "news@example.com"
    content_subtype = "html"
```

A constructor argument overrides the class-level default for that one instance.

### Free-form attributes

Anything you assign in `__init__` beyond the constructor's known fields is yours. Those attributes are passed straight to the template as variables, which is the whole reason for the convention:

```python
class InvoiceEmail(BaseEmail):
    subject = "Your invoice"

    def __init__(self, invoice, **kwargs):
        super().__init__(**kwargs)
        self.invoice = invoice
        self.total = invoice.total
        self.download_url = app.url_for("Invoice.download", invoice, _full=True)
```

The template sees `{{ invoice }}`, `{{ total }}`, `{{ download_url }}`.

### `MAILER_DEFAULT_OPTIONS`

App-wide defaults live in `config/main.py`:

```python
MAILER_DEFAULT_OPTIONS = {
    "from": "no-reply@example.com",
    "reply_to": ["support@example.com"],
    "headers": {"X-App": "MyApp"},
}
```

Any field not supplied by the constructor or by a class default falls back to this dict. So `from_email` typically lives here, once - no email class needs to repeat it. The accepted keys are `from`, `subject`, `body`, `to`, `bcc`, `cc`, `reply_to`, and `headers`.

### Adjusting after construction

`update()` lets you tweak a message after it's built - useful when the sender decides the recipient, not the email class:

```python
email = WelcomeEmail(user)
email.update(to=user.email, headers={"X-Tenant": tenant.id})
email.send()
```

`send()` and `send_later()` both accept the same keyword arguments and call `update()` internally, so the more common form is the one-liner you saw earlier:

```python
WelcomeEmail(user).send_later(to=user.email)
```

---

## Templates

Setting `body=` explicitly works, but the usual path is to let the email auto-render a template. When `send()` (or the worker behind `send_later()`) sees an empty `body`, it goes looking for templates by class-module name.

### The discovery rule

For a class in `emails/welcome_email.py`, Proper strips the `_email` suffix from the module name and looks under `views/emails/`:

- `views/emails/welcome.jx` - the HTML version
- `views/emails/welcome.txt.jx` - the plain text version

You can have one, both, or neither:

HTML present | Text present | Result
------------ | ------------ | ------------------------------------------------------
yes          | yes          | multipart/alternative with both
yes          | no           | multipart/alternative; the text part is auto-generated
no           | yes          | plain text only
no           | no           | body comes from the constructor or class default

The auto-generated text fallback runs the HTML body through a small HTML-to-text converter. It's serviceable for simple transactional mail; for newsletters and rich HTML, write the text template yourself - it almost always reads better.

If your class doesn't follow the `_email` suffix convention (say, `emails/welcome.py` instead of `emails/welcome_email.py`), the lookup just uses the module name unchanged. The suffix rule is a strip, not a requirement.

### What the template sees

Every instance attribute on the email becomes a template variable. There's no separate "assigns" step:

```python
class WelcomeEmail(BaseEmail):
    subject = "Welcome to MyApp"

    def __init__(self, user, **kwargs):
        super().__init__(**kwargs)
        self.user = user
        self.dashboard_url = app.url_for("Dashboard.index", _full=True)
```

```html+jinja
{#import "layouts/email.jx" as Layout #}

{#def user, dashboard_url #}

<Layout>
  <p>Hi {{ user.name }},</p>
  <p>Your account is ready. <a href="{{ dashboard_url }}">Go to your dashboard</a>.</p>
</Layout>
```

The `{#def ... #}` line declares the variables the template expects, which is also how Jx forces you to acknowledge them - omitting a variable from `{#def #}` and referencing it in the template is an error, not a silent `None`.

### The layout

Email templates almost always wrap in `views/layouts/email.jx`, the document shell. The generated layout is intentionally minimal - no styles, no header, no footer - because what looks tasteful in your app isn't necessarily what an email client will accept. Edit it freely.

Two things to know about the layout in practice:

- **Styles must be inline.** Gmail, Outlook, and most webmail clients strip or scope `<style>` blocks. Write `style="..."` attributes on individual elements, or write a small set of utility classes that you then inline. A render-time CSS inliner is an obvious future addition - see [Where this could grow](#where-this-could-grow).
- **Always use `_full=True` for URLs.** `app.url_for("X.show", obj)` returns `/things/42`; in an inbox, that's a 404. `app.url_for("X.show", obj, _full=True)` returns `https://yourapp.com/things/42`, which is what the recipient needs. The full URL is built from your config's `PROTOCOL` and `HOST`, so set those correctly per environment.

---

## Attachments and alternatives

### Attaching files

`attach_file()` adds a file from disk. The MIME type is guessed from the extension; pass `mimetype=` to override:

```python
email = InvoiceEmail(invoice)
email.attach_file("/path/to/invoice.pdf")
email.attach_file("/path/to/data.csv", mimetype="text/csv")
email.send_later(to=customer.email)
```

The resulting message is `multipart/mixed`, with the body as the first part and each attachment as a sibling. Attaching one or more files turns *every* outgoing message into multipart, even if the body is a single short paragraph - that's fine, every client handles it.

### Alternative content parts

`attach_alternative(content, mimetype)` adds an alternative representation of the body - the same content in a different format, not a separate file. The classic use is offering a plain-text fallback alongside HTML:

```python
email = NewsletterEmail()
email.body = "<h1>This week</h1><p>...</p>"
email.content_subtype = "html"
email.attach_alternative("This week\n========\n\n...", "text/plain")
```

In normal use you don't reach for this directly - the template auto-discovery in the previous section calls `attach_alternative()` for you when both an HTML and a text template exist.

### Inline images

Inline images (the `<img src="cid:logo">` pattern, where the image data travels with the message and renders inside the body) require a `multipart/related` structure that `EmailMessage` does not yet expose. The framework's `attach_file()` produces an attached file, not an inline part; `attach_alternative()` produces an alternative body, not a related resource.

The pragmatic workarounds today are:

1. **Host the image externally.** Reference it with a normal `https://` URL. Most modern clients block remote images by default, but they let users opt in - and for transactional mail this is usually fine.
2. **Inline as a data URI.** `<img src="data:image/png;base64,...">`. Bigger payload, but no server hop.
3. **Drop to the stdlib `email` package** for that specific message and assemble the `multipart/related` yourself, then send it through `app.mailer.send_now()`.

First-class CID support is on the list - see [Where this could grow](#where-this-could-grow).

---

## Sending: now vs. later

Two methods send a message; pick by whether the caller is willing to wait.

### `send()` - synchronous

`EmailMessage.send()` hands the message straight to the configured mailer:

```python
WelcomeEmail(user).send(to=user.email)
```

The call blocks until the mailer returns. In production with the SMTP backend, that means waiting on a TCP round-trip and an SMTP conversation - usually a fraction of a second, sometimes longer if the server is slow or refuses to connect. If it happens inside a request handler, the user waits with it.

`send()` is the right call for: tests, scripts, scheduled jobs already running in a worker, and any place where blocking is not a problem.

### `send_later()` - asynchronous

`BaseEmail.send_later()` enqueues a background task that sends the message:

```python
WelcomeEmail(user).send_later(to=user.email)
```

The call returns immediately. The actual SMTP work happens in the worker process, off the request path. For email triggered by a web request - the password reset, the welcome message, the receipt - this is the default. Users get their redirect; the email lands a few seconds later.

`send_later()` is defined in your app's `BaseEmail`:

```python
# emails/base_email.py
import proper

from ..tasks import send_email_task


class BaseEmail(proper.EmailMessage):
    def send_later(self, **options):
        self.update(**options)
        send_email_task(message=self.serialize())
```

And the task it calls is one of the few things shipped in `tasks/__init__.py`:

```python
# tasks/__init__.py
from proper.emails import EmailMessageDict

from ..main import app


@app.queue.task()
def send_email_task(message: EmailMessageDict):
    app.mailer.send_now(message)
```

Both files are in the generated app from day one. If you need to do something extra around sending - retries, tagging, multi-tenant routing - this is where to edit.

### What happens in dev and tests

In dev and test, the queue runs in **immediate mode**: `send_email_task(...)` runs synchronously, in the calling process, the moment you invoke it. So `send_later()` behaves like `send()` - the message goes through the mailer right away, no worker needed. Your test assertions see the email immediately; your dev console prints it without you starting `workers.py`.

In production, where the queue points at Redis (or another real backend), `send_later()` enqueues a task message and a separate worker process picks it up. The worker must actually be running; see [Background Tasks → Running Workers](/docs/tasks#running-workers) for how to keep one alive.

---

## Backends

The `MAILER` config in `config/main.py` decides which backend the app sends through. The `type` key names the class; every other key is passed to its constructor.

### `ToConsoleMailer` - development

```python
MAILER = {"type": "proper.emails.ToConsoleMailer"}
```

Writes the full rendered RFC 5322 message to stdout, with a `---` separator between messages. Useful for "did the right thing get composed" - you can verify the subject, recipients, headers, and body without standing up an SMTP server or copying real addresses into your dev environment.

Pass `stream=` to redirect somewhere other than `sys.stdout`:

```python
import sys
MAILER = {"type": "proper.emails.ToConsoleMailer", "stream": sys.stderr}
```

### `ToMemoryMailer` - tests

```python
MAILER = {"type": "proper.emails.ToMemoryMailer"}
```

Stores sent messages in an in-memory list at `app.mailer.outbox` instead of sending them. This is what powers the testing pattern in the next section. Each entry is a fully rendered `email.message.EmailMessage` (the stdlib class), so you inspect its headers and parts the way you would any other Python email.

### `SMTPMailer` - production

```python
MAILER = {
    "type": "proper.emails.SMTPMailer",
    "host": "smtp.example.com",
    "port": 587,
    "username": os.getenv("SMTP_USERNAME"),
    "password": os.getenv("SMTP_PASSWORD"),
    "use_tls": True,
}
```

The full option set:

Option         | Default       | Description
-------------- | ------------- | --------------------------------------------------------
`host`         | `"localhost"` | SMTP server hostname
`port`         | `587`         | SMTP server port
`username`     | `None`        | Authentication username
`password`     | `None`        | Authentication password
`use_tls`      | `False`       | STARTTLS - upgrade a plaintext connection
`use_ssl`      | `False`       | Implicit SSL/TLS - encrypted from the start (port 465)
`timeout`      | `None`        | Connection timeout in seconds
`ssl_keyfile`  | `None`        | Path to client SSL key
`ssl_certfile` | `None`        | Path to client SSL certificate
`fail_silently` | `False`      | Swallow SMTP errors instead of raising

`use_tls` and `use_ssl` are mutually exclusive - constructing the mailer with both set raises `ValueError`. Use `use_tls=True` on port 587 (the modern default); use `use_ssl=True` on port 465 for legacy "SMTPS" servers.

The SMTPMailer is thread-safe and pools its connection: a single `send_now()` call with multiple messages reuses one TCP connection for all of them.

### Per-environment configuration

The generated `config/main.py` switches backend by environment:

```python
import os

env = os.getenv("APP_ENV", "dev")

# Default - print to console in dev
MAILER = {"type": "proper.emails.ToConsoleMailer"}

MAILER_DEFAULT_OPTIONS = {
    "from": "no-reply@example.com",
}

if env == "test":
    MAILER = {"type": "proper.emails.ToMemoryMailer"}

if env == "prod":
    MAILER = {
        "type": "proper.emails.SMTPMailer",
        "host": "smtp.example.com",
        "port": 587,
        "username": os.getenv("SMTP_USERNAME"),
        "password": os.getenv("SMTP_PASSWORD"),
        "use_tls": True,
    }
```

This is the only switch you need: the same email classes, the same `send_later()` calls, just a different backend behind them.

### Writing a custom backend

If you send through an HTTP API (Resend, Postmark, SendGrid, SES) rather than SMTP, you write a small class that subclasses `BaseMailer` and overrides `send_now()`. Everything else - rendering, attachments, headers, address encoding - is inherited.

The sketch:

```python
# myapp/mailers/resend_mailer.py
import httpx

from proper.emails import BaseMailer
from proper.emails.message import EmailMessageDict


class ResendMailer(BaseMailer):
    def __init__(self, *, api_key: str, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key
        self.client = httpx.Client(
            base_url="https://api.resend.com",
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def send_now(self, *messages: EmailMessageDict) -> int:
        sent = 0
        for message in messages:
            rendered = self.render(message)  # inherited - returns a stdlib EmailMessage
            response = self.client.post("/emails", json={
                "from": rendered["From"],
                "to": message["to"],
                "subject": rendered["Subject"],
                "html": message["body"] if message["content_subtype"] == "html" else None,
                "text": message["body"] if message["content_subtype"] == "plain" else None,
            })
            if response.is_success:
                sent += 1
            elif not self.fail_silently:
                response.raise_for_status()
        return sent
```

Then point `MAILER` at it:

```python
MAILER = {
    "type": "myapp.mailers.resend_mailer.ResendMailer",
    "api_key": os.getenv("RESEND_API_KEY"),
}
```

The `render()` method on `BaseMailer` does the heavy lifting (multipart assembly, attachments, IDNA encoding); your `send_now()` only has to translate the result into whatever shape your provider expects. A real implementation would also serialize attachments and alternatives into the provider's payload - the sketch above is just enough to show the seam.

---

## Testing

In tests, `MAILER` is `ToMemoryMailer`, and `send_email_task` runs in immediate mode. Together that means: anything your code sends ends up in `app.mailer.outbox`, synchronously, by the time the call returns. No waiting, no worker, no SMTP server.

A typical assertion:

```python
def test_reset_request_sends_email(client, user):
    response = client.post("/password-reset", data={"login": user.email})

    assert response.status_code == 302
    assert len(app.mailer.outbox) == 1

    email = app.mailer.outbox[0]
    assert email["Subject"] == "Reset your password"
    assert email["To"] == user.email
    assert "Reset" in email.get_body(("plain", "html")).get_content()
```

A few things worth knowing:

- **Outbox entries are stdlib `email.message.EmailMessage` objects.** Headers are accessed by name (`email["Subject"]`, `email["To"]`) and are case-insensitive. Bodies come back through `get_body()` and `get_content()`.
- **`Bcc` is not in the headers.** The SMTP backend treats `bcc` as a routing instruction - it includes the address in `RCPT TO` but strips it from the visible message, exactly as a mail server would. Assert against `message["bcc"]` on the *unrendered* dict if you need to check it. (For pure-stdlib `EmailMessage` outbox entries, `Bcc` is `None`.)
- **The outbox accumulates across the test.** Reset it between tests if you assert lengths - either with a fixture that clears it, or by asserting on the *new* messages since a saved index.

For testing an email class in isolation - render its template, check the output, without going through a controller - construct and `send()` it directly:

```python
def test_welcome_email_includes_dashboard_link(user):
    WelcomeEmail(user).send(to=user.email)

    email = app.mailer.outbox[-1]
    assert "/dashboard" in email.get_content()
```

If you specifically want to exercise the *queued* path - serialization round-trip, the worker - that's an integration test, not a unit test. Point `QUEUE` at `SqliteHuey` and run a real consumer. For the everyday question of "did my email get sent and did it say the right thing," immediate mode plus `ToMemoryMailer` is the answer.

---

## Internationalized addresses

Email addresses with non-ASCII domain names get encoded to punycode automatically. `user@münchen.de` becomes `user@xn--mnchen-3ya.de` on the way out. You don't need to do anything; addresses you store as Unicode in your database are fine.

For servers that accept Unicode addresses natively (SMTPUTF8), set the policy on the mailer:

```python
import email.policy
from proper.emails import SMTPMailer

class UTF8SMTPMailer(SMTPMailer):
    policy = email.policy.SMTPUTF8
```

Non-ASCII local-parts (the part before `@`) are rejected by default because most SMTP servers can't handle them. To accept them under SMTPUTF8, call `prep_address(..., force_ascii=False)` in your subclass.

---

## Where this could grow

Email in Proper covers the basics well: a class-per-message convention, template auto-discovery, background sending, the three standard backends, working tests. Several features common in mature email systems aren't here yet. None of them are blockers - workarounds exist - but they're the obvious places the framework will grow.

- **Browser previews.** A dev-only route where you can preview your email templates with fixture data.This is probably the highest-ROI feature on the list.
- **First-party HTTP backends.** Most production traffic in 2026 goes through Resend, Postmark, SendGrid, or SES rather than SMTP - they handle deliverability, bounces, and metrics that SMTP doesn't. The custom-backend recipe above works, but a curated set of provider mailers (and addons that ship them) would save every app re-implementing the same thing.
- **CSS inlining at render time.** Today the email layout has an empty `<style>` block with a comment noting that styles must be inline. A premailer-style pass would let users write normal CSS and have it inlined into `style="..."` attributes automatically.
- **Inline images (CIDs).** `attach_file(path, inline=True)` returning a `cid:` reference for `<img src="cid:...">`. Requires `multipart/related` handling that the current code doesn't expose.
- **Mail interceptors.** A `MAILER_INTERCEPT_TO = "staging@example.com"` config that rewrites all outgoing `to/cc/bcc` to a single address on non-production environments. This is the safest cure for the "we accidentally emailed 50,000 production users from staging" class of incident.
- **Bounce and complaint webhooks.** A small interface for receiving provider webhooks and flagging the corresponding `User.email` as bounced or complained, so the app stops trying to send to dead addresses.
- **Per-call backend override.** Sending one specific message through a different backend than the default - useful for "send this transactional mail through Postmark even though bulk goes through SES."

If you build any of these against the current code, the framework would love a PR.

---

## What's next

Email touches several other parts of Proper. A few places to go from here:

- [Background Tasks](/docs/tasks) - `send_later()` is built on the task queue; that guide covers the worker process, retries, scheduling, and the immediate-mode behavior the testing section relies on.
- [Jx Components](/docs/jx_components) - email templates *are* Jx components. The `{#def ... #}` declaration and `<Layout>` import work the same way they do anywhere else in your views.
- [Authentication](/docs/authentication) - the auth addon's password-reset flow is the canonical example threaded through this guide; the auth guide covers the surrounding token model and controller setup.
- [Deployment](/docs/deployment) - running the worker process in production, configuring environment variables for your SMTP or provider credentials, and the operational side of email sending.
