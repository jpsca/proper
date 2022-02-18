from mailshake import ToConsoleMailer


mailer = ToConsoleMailer()

def send_email(to, subject, **kw):
    kw.setdefault("from_email", config.mailer_default_from)
    mailer.send(to=to, subject=subject, **kw)
