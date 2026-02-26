title: Emails
----

# Emails

Proper includes a complete email system with an `EmailMessage` class for composing messages, pluggable mailer backends for sending them, and integration with the background task queue for asynchronous delivery.


## 1. Composing Emails

The `EmailMessage` class is the core container for email data:

```python
from proper import EmailMessage

msg = EmailMessage(
    from_email="hello@example.com",
    subject="Welcome!",
    body="Thanks for signing up.",
    to="alice@example.com",
)
msg.send()
```

All parameters are keyword-only. The `to`, `bcc`, `cc`, and `reply_to` fields accept a single string or a list of strings:

```python
msg = EmailMessage(
    subject="Announcement",
    body="Big news!",
    to=["alice@example.com", "bob@example.com"],
    cc=["manager@example.com"],
    bcc=["admin@example.com"],
    reply_to=["support@example.com"],
)
```

### 1.1 Default Options

Values not provided fall back to `MAILER_DEFAULT_OPTIONS` from config:

```python
# config/main.py
MAILER_DEFAULT_OPTIONS = {
    "from": "no-reply@example.com",
}
```

With this config, you can omit `from_email` and it defaults to `"no-reply@example.com"`.

### 1.2 Attachments

Attach files from the filesystem. MIME types are auto-detected:

```python
msg = EmailMessage(
    subject="Invoice",
    body="See attached.",
    to="customer@example.com",
)
msg.attach_file("/path/to/invoice.pdf")
msg.attach_file("/path/to/data.csv", mimetype="text/csv")
msg.send()
```

### 1.3 HTML Emails and Alternatives

Set `content_subtype = "html"` on a subclass for HTML emails. Use `generate_text_alternative()` to auto-create a plain text version from the HTML body:

```python
class NewsletterEmail(EmailMessage):
    content_subtype = "html"
    subject = "Weekly Newsletter"

    def __init__(self, html_body, **kwargs):
        super().__init__(body=html_body, **kwargs)
        self.generate_text_alternative()
```

You can also manually attach alternative representations:

```python
msg.attach_alternative("<h1>Hello</h1>", "text/html")
```

### 1.4 Custom Headers

Pass a `headers` dict for custom email headers:

```python
msg = EmailMessage(
    subject="Urgent",
    body="Please respond.",
    to="alice@example.com",
    headers={"X-Priority": "1", "X-Custom": "value"},
)
```

### 1.5 Sending

`send()` delivers the email immediately through the configured mailer:

```python
msg.send()

# You can also override recipients at send time
msg.send(to="override@example.com", bcc=["extra@example.com"])
```


## 2. The BaseEmail Pattern

The generated app includes a `BaseEmail` class in `emails/base_email.py` that adds `send_later()` for background delivery:

```python
import proper

from ..tasks import send_email_task


class BaseEmail(proper.EmailMessage):
    def send_later(self, **options):
        self.update(**options)
        send_email_task(message=self.serialize())
```

This serializes the email to a dictionary and queues it as a background task. The worker process calls `app.mailer.send_now()` to deliver it.

### 2.1 Creating Custom Emails

Subclass `BaseEmail` for specific email types:

```python
from ..main import app
from ..config import main as config
from .base_email import BaseEmail


class PasswordResetEmail(BaseEmail):
    subject = "Reset your password"

    def __init__(self, user, **kwargs):
        super().__init__(**kwargs)
        token = user.get_token()
        validate_url = app.url_for("PasswordReset.edit", token=token)
        reset_url = app.url_for("PasswordReset.new")
        self.body = app.catalog.render(
            "emails/password_reset.jinja",
            validate_url=f"{config.PROTOCOL}://{config.HOST}{validate_url}",
            reset_url=f"{config.PROTOCOL}://{config.HOST}{reset_url}",
        )
        self.generate_text_alternative()
```

Key patterns:

- Set class-level attributes like `subject` for defaults
- Use `app.catalog.render()` to render Jinja templates for the body
- Call `generate_text_alternative()` to auto-create a plain text version from HTML
- Use `app.url_for()` to generate URLs

### 2.2 Sending Emails

```python
# Send immediately (blocks until delivered)
email = PasswordResetEmail(user)
email.send(to=user.email)

# Send via background queue (returns immediately)
email = PasswordResetEmail(user)
email.send_later(to=user.email)
```

### 2.3 Email Templates

Email templates are Jinja files in the `views/emails/` directory. They use a layout defined in `views/layouts/email.jinja`:

```html+jinja
{#def title='', lang='en' #}
<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
    <meta charset="utf-8">
    <title>{{ title }}</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style></style>
</head>
<body>
    {{ content }}
</body>
</html>
```

Use it in your email templates:

```html+jinja
{#import "layouts/email.jinja" as Layout #}
{#def validate_url, reset_url #}

<Layout title="Reset your password">
  <p>Click the link to reset your password:
    <a href="{{ validate_url }}">{{ validate_url }}</a>.</p>
  <p>This link expires in 3 hours.</p>
</Layout>
```


## 3. Mailer Backends

The `MAILER` config in `config/main.py` controls which backend sends emails. The `type` key specifies the mailer class; remaining keys are passed to its constructor.

### 3.1 ToConsoleMailer (Development)

Prints emails to stdout. This is the default:

```python
MAILER = {"type": "proper.emails.ToConsoleMailer"}
```

Useful during development to see what emails would be sent without actually delivering them.

### 3.2 ToMemoryMailer (Testing)

Stores emails in an in-memory list instead of sending them:

```python
MAILER = {"type": "proper.emails.ToMemoryMailer"}
```

Access sent emails in tests via `app.mailer.outbox`:

```python
def test_sends_welcome_email():
    # trigger the action that sends an email...

    assert len(app.mailer.outbox) == 1
    email = app.mailer.outbox[0]
    assert email["subject"] == "Welcome!"
```

### 3.3 SMTPMailer (Production)

Sends emails via SMTP:

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

All SMTPMailer options:

| Option         | Default       | Description                          |
|----------------|---------------|--------------------------------------|
| `host`         | `"localhost"` | SMTP server hostname                 |
| `port`         | `587`         | SMTP server port                     |
| `username`     | `None`        | Authentication username              |
| `password`     | `None`        | Authentication password              |
| `use_tls`      | `False`       | Use STARTTLS                         |
| `use_ssl`      | `False`       | Use implicit SSL/TLS                 |
| `timeout`      | `None`        | Connection timeout (seconds)         |
| `ssl_keyfile`  | `None`        | Path to SSL key file                 |
| `ssl_certfile` | `None`        | Path to SSL certificate file         |

`use_tls` and `use_ssl` are mutually exclusive. `use_tls` upgrades a plain connection with STARTTLS, while `use_ssl` connects over SSL/TLS from the start (typically port 465).

The SMTPMailer is thread-safe and reuses connections when sending multiple messages.


## 4. Configuration

### 4.1 Per-Environment Setup

The generated config switches mailers by environment:

```python
# config/main.py
import os

env = os.getenv("APP_ENV", "dev")

# Development (default) — print to console
MAILER = {"type": "proper.emails.ToConsoleMailer"}

MAILER_DEFAULT_OPTIONS = {
    "from": "no-reply@example.com",
}

# Testing — store in memory
if env == "test":
    MAILER = {"type": "proper.emails.ToMemoryMailer"}

# Production — send via SMTP
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

### 4.2 Default Options

`MAILER_DEFAULT_OPTIONS` provides fallback values for all emails:

```python
MAILER_DEFAULT_OPTIONS = {
    "from": "no-reply@example.com",
    "reply_to": ["support@example.com"],
    "headers": {"X-App": "MyApp"},
}
```

Available keys: `from` (mapped to `default_from`), `subject`, `body`, `to`, `bcc`, `cc`, `reply_to`, `headers`.


## 5. Internationalized Domains

Email addresses with non-ASCII domain names are automatically encoded to punycode for SMTP compatibility. For example, `user@münchen.de` is encoded to `user@xn--mnchen-3ya.de` when sending.

The SMTPMailer also supports SMTPUTF8 for servers that accept internationalized addresses natively.
